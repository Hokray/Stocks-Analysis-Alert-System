"""
Factor study -- data fetch for the 2,477-name universe.

Two stages, each cached per ticker and independently resumable:

    1  PRICES        5 years of daily adjusted closes, batch-downloaded
    2  FUNDAMENTALS  income statement, balance sheet, cash flow (annual)

    python research/factor_study/fetch_data.py

Run it standalone. It takes roughly 45 minutes -- about 3 of those are stage 1,
the rest is stage 2 at one request per ticker. Interrupt with Ctrl-C and run it
again: it skips everything already on disk and tells you how many it skipped.

This script FETCHES AND CACHES ONLY. It computes no factor, ranks nothing and
makes no judgement about any name. Factor construction is a separate step, so
that a bad decision there costs a rerun of the analysis and not 45 minutes of
network.

What is stored, and why in this shape
-------------------------------------
Prices are written one CSV per ticker (date, close). Daily rather than
month-end even though every factor in DESIGN.md is computed on month-ends,
because downsampling at fetch time would bake a choice into the cache and make
any later change to the rebalance convention a 45-minute refetch instead of a
reread.

Fundamentals are written one JSON per ticker holding EVERY row of all three
statements, not just the handful DESIGN.md names. Same reason: the curated
list is a decision belonging to the analysis step. Storing the full statement
costs disk and saves a refetch if a definition moves.

Neither stage writes into universe.csv. The universe is fixed and committed.

Coverage reporting
------------------
DESIGN.md commits to reporting per-factor coverage as counts rather than
percentages. The end-of-run summary therefore counts, across the tickers
fetched, how many actually carry each line item the factors need -- so the real
per-decile sample size is visible before the analysis runs rather than after.

See DESIGN.md for the pre-registered scope, the factor definitions, the
negative/undefined rule and the four biases.
"""

import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

# The builder's helpers are shared rather than copied. DESIGN.md's
# "copied, not imported" decision is about phases 1-4, whose edits must never
# reach this study. universe_builder.py IS this study, and two drifting copies
# of a retry loop would be worse than the coupling.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from universe_builder import (                                  # noqa: E402
    CACHE_DIR,
    OUTPUT_CSV,
    PROGRESS_EVERY,
    DelayController,
    JsonlWriter,
    read_jsonl,
    save_failures,
    with_retries,
)

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

PRICES_DIR = f"{CACHE_DIR}/prices"
FUNDAMENTALS_DIR = f"{CACHE_DIR}/fundamentals"

PRICE_FAILURES = f"{CACHE_DIR}/failures_price_history.json"
FUNDAMENTAL_FAILURES = f"{CACHE_DIR}/failures_fundamentals.json"
MANIFEST = f"{CACHE_DIR}/fetch_manifest.jsonl"

PRICE_PERIOD = "5y"
PRICE_CHUNK = 200

# Line items the factors in DESIGN.md need. Used ONLY to report coverage --
# the cache stores every row regardless, so this list can change without a
# refetch.
NEEDED_ROWS = {
    "income": ["EBIT", "Operating Income", "Gross Profit", "Total Revenue"],
    "balance": ["Total Assets", "Total Debt", "Cash And Cash Equivalents",
                "Ordinary Shares Number", "Share Issued"],
    "cashflow": ["Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"],
}

FACTOR_REQUIREMENTS = {
    "value (EBIT/EV)": [("income", "EBIT"), ("balance", "Total Debt"),
                        ("balance", "Cash And Cash Equivalents")],
    "value (FCF/EV)": [("cashflow", "Free Cash Flow"), ("balance", "Total Debt"),
                       ("balance", "Cash And Cash Equivalents")],
    "quality (GP/assets)": [("income", "Gross Profit"), ("balance", "Total Assets")],
    "size + dilution": [("balance", "Ordinary Shares Number")],
}


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def load_universe():
    if not os.path.exists(OUTPUT_CSV):
        sys.exit(f"{OUTPUT_CSV} not found -- run universe_builder.py first.")
    df = pd.read_csv(OUTPUT_CSV)
    symbols = sorted(df["symbol"].astype(str).tolist())
    print(f"  universe: {len(symbols):,} symbols from {OUTPUT_CSV}")
    return symbols


def price_path(symbol):
    # '/' and other separators cannot appear after the a2 filter, but a
    # symbol is still untrusted input for a path.
    safe = "".join(c for c in symbol if c.isalnum() or c in "-_.")
    return f"{PRICES_DIR}/{safe}.csv"


def fundamental_path(symbol):
    safe = "".join(c for c in symbol if c.isalnum() or c in "-_.")
    return f"{FUNDAMENTALS_DIR}/{safe}.json"


# ---------------------------------------------------------------------------
# Stage 1 -- price history
# ---------------------------------------------------------------------------

def extract_frame(bulk, symbol, single):
    """Pull one symbol's Close series out of a batch download."""
    if single:
        df = bulk
    else:
        try:
            df = bulk[symbol]
        except (KeyError, TypeError):
            return None
    if df is None or "Close" not in df:
        return None
    out = df[["Close"]].dropna()
    return out if not out.empty else None


def stage_prices(symbols, delays):
    print()
    print("=" * 72)
    print("STAGE 1 -- price history (5y daily adjusted close)")
    print("=" * 72)
    os.makedirs(PRICES_DIR, exist_ok=True)

    todo = [s for s in symbols if not os.path.exists(price_path(s))]
    print(f"  cached already: {len(symbols) - len(todo):,}   "
          f"to fetch: {len(todo):,}")
    if not todo:
        return {}, 0

    failures, empty = {}, 0
    started = time.time()
    done = 0

    for i in range(0, len(todo), PRICE_CHUNK):
        chunk = todo[i:i + PRICE_CHUNK]
        single = len(chunk) == 1

        bulk, err = with_retries(
            lambda c=chunk: yf.download(
                c, period=PRICE_PERIOD, interval="1d", auto_adjust=True,
                group_by="ticker", progress=False, threads=True,
            ),
            f"prices[{chunk[0]}..]", delays,
        )

        if err is not None:
            # The whole chunk failed. Record each symbol so the summary is
            # per-ticker, and leave the files absent so a rerun retries them.
            for s in chunk:
                failures[s] = err
            done += len(chunk)
            continue

        for s in chunk:
            frame = extract_frame(bulk, s, single)
            if frame is None:
                # Write a header-only file so a rerun does not refetch a
                # symbol the provider has no data for. Analysis drops it.
                with open(price_path(s), "w", encoding="utf-8") as f:
                    f.write("date,close\n")
                empty += 1
            else:
                frame.index.name = "date"
                frame.columns = ["close"]
                frame.to_csv(price_path(s), date_format="%Y-%m-%d")
            done += 1

        if done % PROGRESS_EVERY < PRICE_CHUNK:
            elapsed = (time.time() - started) / 60
            rate = done / max(elapsed, 1e-9)
            left = (len(todo) - done) / max(rate, 1e-9)
            print(f"    {done:,}/{len(todo):,} symbols  "
                  f"{elapsed:.1f} min elapsed  ~{left:.0f} min left  "
                  f"{len(failures)} failed")

    print(f"    {done:,}/{len(todo):,} symbols  "
          f"{(time.time() - started) / 60:.1f} min elapsed  "
          f"{len(failures)} failed")
    if empty:
        print(f"  no price data returned: {empty:,} "
              f"(written as empty files, not retried)")
    save_failures(PRICE_FAILURES, failures)
    return failures, empty


# ---------------------------------------------------------------------------
# Stage 2 -- fundamentals
# ---------------------------------------------------------------------------

def frame_to_dict(df):
    """{row label: {period: value}}, with NaN as null and dates as ISO days."""
    if df is None or not hasattr(df, "empty") or df.empty:
        return {}
    out = {}
    for label in df.index:
        row = {}
        for col in df.columns:
            value = df.at[label, col]
            if isinstance(value, (pd.Series, np.ndarray)):   # duplicate labels
                value = value[0] if len(value) else None
            try:
                value = float(value)
                if not np.isfinite(value):
                    value = None
            except (TypeError, ValueError):
                value = None
            row[str(col)[:10]] = value
        out[str(label)] = row
    return out


def fetch_one(symbol):
    tk = yf.Ticker(symbol)
    return {
        "symbol": symbol,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "income": frame_to_dict(tk.income_stmt),
        "balance": frame_to_dict(tk.balance_sheet),
        "cashflow": frame_to_dict(tk.cashflow),
    }


def stage_fundamentals(symbols, delays):
    print()
    print("=" * 72)
    print("STAGE 2 -- annual financial statements")
    print("=" * 72)
    os.makedirs(FUNDAMENTALS_DIR, exist_ok=True)

    todo = [s for s in symbols if not os.path.exists(fundamental_path(s))]
    print(f"  cached already: {len(symbols) - len(todo):,}   "
          f"to fetch: {len(todo):,}")
    if not todo:
        return {}

    manifest = JsonlWriter(MANIFEST)
    failures = {}
    started = time.time()

    try:
        for n, symbol in enumerate(todo, 1):
            record, err = with_retries(
                lambda s=symbol: fetch_one(s), f"fundamentals[{symbol}]", delays,
            )

            if err is not None:
                failures[symbol] = err
            else:
                # Write to a temp name then replace, so a Ctrl-C mid-write
                # cannot leave a half-written JSON that reads as cached.
                path = fundamental_path(symbol)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(record, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
                manifest.write({
                    "symbol": symbol,
                    "fetched_at": record["fetched_at"],
                    "income_periods": len(next(iter(record["income"].values()), {})),
                    "balance_periods": len(next(iter(record["balance"].values()), {})),
                    "cashflow_periods": len(next(iter(record["cashflow"].values()), {})),
                })

            if n % PROGRESS_EVERY == 0:
                elapsed = (time.time() - started) / 60
                rate = n / max(elapsed, 1e-9)
                left = (len(todo) - n) / max(rate, 1e-9)
                print(f"    {n:,}/{len(todo):,}  {elapsed:.1f} min elapsed  "
                      f"~{left:.0f} min left  {len(failures)} failed  "
                      f"delay {delays.delay:.2f}s")

            delays.sleep()
    finally:
        manifest.close()
        save_failures(FUNDAMENTAL_FAILURES, failures)

    print(f"    {len(todo):,}/{len(todo):,}  "
          f"{(time.time() - started) / 60:.1f} min elapsed  "
          f"{len(failures)} failed")
    return failures


# ---------------------------------------------------------------------------
# Coverage -- counts, not percentages (DESIGN.md)
# ---------------------------------------------------------------------------

def report_coverage(symbols):
    print()
    print("=" * 72)
    print("COVERAGE (counts, as pre-registered)")
    print("=" * 72)

    price_sessions, statement_periods = [], []
    have_rows = {(s, r): 0 for s, rows in NEEDED_ROWS.items() for r in rows}
    n_prices = n_statements = 0

    for symbol in symbols:
        p = price_path(symbol)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                rows = sum(1 for _ in f) - 1
            if rows > 0:
                n_prices += 1
                price_sessions.append(rows)

        f_path = fundamental_path(symbol)
        if not os.path.exists(f_path):
            continue
        try:
            with open(f_path, encoding="utf-8") as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        n_statements += 1

        periods = set()
        for stmt in ("income", "balance", "cashflow"):
            block = rec.get(stmt) or {}
            for label, series in block.items():
                periods.update(series.keys())
                key = (stmt, label)
                if key in have_rows and any(v is not None for v in series.values()):
                    have_rows[key] += 1
        statement_periods.append(len(periods))

    print(f"\n  tickers with price history:  {n_prices:,} / {len(symbols):,}")
    if price_sessions:
        print(f"  sessions per ticker: median {int(np.median(price_sessions)):,}  "
              f"min {min(price_sessions):,}  max {max(price_sessions):,}")

    print(f"\n  tickers with statements:     {n_statements:,} / {len(symbols):,}")
    if statement_periods:
        counts = pd.Series(statement_periods).value_counts().sort_index()
        print("  annual periods available:")
        for periods, n in counts.items():
            print(f"      {periods} periods: {n:,} tickers")
        print(f"  with >= 4 periods: "
              f"{sum(1 for p in statement_periods if p >= 4):,}")

    print("\n  line item present (at least one non-null period):")
    for stmt, rows in NEEDED_ROWS.items():
        for row in rows:
            print(f"      {stmt:<9} {row:<28} {have_rows[(stmt, row)]:>6,}")

    print("\n  NAMES RANKABLE PER FACTOR -- the number that matters:")
    for factor, needs in FACTOR_REQUIREMENTS.items():
        n = min(have_rows[k] for k in needs)
        print(f"      {factor:<22} {n:>6,}   ~{n // 10:,} per decile"
              f"{'   BELOW THE 30/DECILE FLOOR' if n // 10 < 30 else ''}")
    print(f"      {'momentum':<22} {n_prices:>6,}   ~{n_prices // 10:,} per decile")

    print("\n  These are totals across all periods. Per-rebalance-date coverage")
    print("  is thinner and is reported by the analysis step, which is where")
    print("  the 30-names-per-decile floor is actually checked.")


# ---------------------------------------------------------------------------

def summarise(started, delays, price_failures, empty, fundamental_failures):
    print()
    print("=" * 72)
    print("RUN SUMMARY")
    print("=" * 72)
    print(f"\n  elapsed:                {(time.time() - started) / 60:.1f} min")
    print(f"  requests made:          {delays.requests:,}")
    print(f"  rate-limit errors:      {delays.rate_errors:,}")
    print(f"  final delay:            {delays.delay:.2f}s")
    print(f"  price history failures: {len(price_failures):,}")
    print(f"  empty price responses:  {empty:,}")
    print(f"  fundamental failures:   {len(fundamental_failures):,}")

    for label, failures, path in (
        ("price history", price_failures, PRICE_FAILURES),
        ("fundamentals", fundamental_failures, FUNDAMENTAL_FAILURES),
    ):
        if not failures:
            print(f"\n  no {label} failures")
            continue
        grouped = {}
        for symbol, reason in failures.items():
            grouped.setdefault(reason, []).append(symbol)
        print(f"\n  {label} failures by reason:")
        for reason, syms in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
            print(f"      {reason:<28} {len(syms):>5}   "
                  f"e.g. {', '.join(sorted(syms)[:6])}")
        print(f"      full list: {path}")
        print("      rerun the script to retry these; cached names are skipped")

    if delays.history:
        print("\n  delay escalation history:")
        for entry in delays.history:
            print(f"      request {entry['request']:>6}  {entry['direction']:<8} "
                  f"{entry['from']:.2f}s -> {entry['to']:.2f}s "
                  f"({entry['rate_errors_so_far']} rate errors so far)")
    else:
        print(f"\n  delay never changed from {delays.delay:.2f}s "
              f"(no rate-limit pressure)")

    print(f"\n  prices:       {PRICES_DIR}/<SYMBOL>.csv")
    print(f"  fundamentals: {FUNDAMENTALS_DIR}/<SYMBOL>.json")
    print("\n  Re-running skips everything already cached.")


def main():
    started = time.time()
    print("=" * 72)
    print("FACTOR STUDY -- DATA FETCH")
    print("=" * 72)

    symbols = load_universe()
    delays = DelayController()

    price_failures, empty = stage_prices(symbols, delays)
    fundamental_failures = stage_fundamentals(symbols, delays)

    report_coverage(symbols)
    summarise(started, delays, price_failures, empty, fundamental_failures)


if __name__ == "__main__":
    main()
