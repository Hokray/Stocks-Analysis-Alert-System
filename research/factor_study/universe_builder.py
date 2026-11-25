"""
Factor study -- staged universe funnel.

Builds the study universe from the full US symbol list down to common stocks in
the pre-registered $100m-$10bn band, caching every stage to disk so the run is
resumable.

    python research/factor_study/universe_builder.py

Run it standalone. It takes a couple of hours and prints progress as it goes.
Interrupt it with Ctrl-C and run it again -- it skips everything already
cached and tells you how many it skipped.

Stages
------
    A  symbol list            NASDAQ Trader (no contact header required)
    A2 security-type filter   drop warrants, units, rights, preferreds, funds
    B  batch price download   5 years daily, in chunks
    C  liquidity              median daily dollar volume, STORED not just filtered
    D  market cap             one .info call per surviving symbol
    E  quoteType net          secondary filter on top of A2
       scope band             $100m to $10bn, mega caps excluded

Why A2 exists
-------------
The timed trial drew 50 random symbols and got back warrants (CAIIW, OABIW,
RVMDW, TLNCW), units (SUMAU), rights (MCAHR), preferreds (WRB$H, HPP$C, DTW,
REGCO) and closed-end funds (PFD, PMO). yfinance returned `quoteType == EQUITY`
for ALL of them, and NASDAQ's own ETF flag caught none of them either. Ranking a
warrant on EBIT/EV is meaningless and closed-end funds would pollute every
decile, so the filter is driven by the NASDAQ Security Name text plus symbol
structure, and runs BEFORE any price request rather than after.

Liquidity is a field, not only a threshold
------------------------------------------
`median_dollar_volume` is written for every surviving name. The floor here is
deliberately permissive -- it removes names that barely trade at all, nothing
more. The real liquidity question is answered in the analysis step by re-running
every factor result with the bottom liquidity quintile excluded and reporting
whether any decile spread moves materially. A strict floor here would pre-empt
that check by throwing away the very names it is meant to test.

See DESIGN.md for the pre-registered scope and the three biases.
"""

import csv
import io
import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf

try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:                                  # older yfinance
    class YFRateLimitError(Exception):
        pass

# Run from the repo root so relative paths resolve the same way the other
# research scripts do.
ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(ROOT, "config.py")):
    ROOT = os.path.dirname(ROOT)
os.chdir(ROOT)

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

STUDY_DIR = "research/factor_study"
CACHE_DIR = f"{STUDY_DIR}/cache"
OUTPUT_CSV = f"{STUDY_DIR}/universe.csv"

SYMBOLS_CACHE = f"{CACHE_DIR}/symbols_raw.json"
PRICES_CACHE = f"{CACHE_DIR}/prices_summary.jsonl"
PROFILE_CACHE = f"{CACHE_DIR}/profile.jsonl"
PRICE_FAILURES = f"{CACHE_DIR}/failures_prices.json"
PROFILE_FAILURES = f"{CACHE_DIR}/failures_profile.json"

NASDAQ_SOURCES = [
    ("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqtraded.txt", "Symbol"),
    ("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", "ACT Symbol"),
]

# --- pre-registered scope, see DESIGN.md -----------------------------------
CAP_MIN = 100_000_000          # $100m floor
CAP_MAX = 10_000_000_000       # $10bn ceiling, mega caps excluded

# Permissive by design -- see the module docstring. One constant to change.
MIN_MEDIAN_DOLLAR_VOLUME = 100_000      # $100k/day

PRICE_PERIOD = "5y"
PRICE_CHUNK = 200              # symbols per batch download
MIN_SESSIONS = 252             # need at least a year of history to rank on

PROGRESS_EVERY = 50

# --- adaptive delay controller --------------------------------------------
DELAY_START = 0.5
DELAY_FLOOR = 0.5
DELAY_CEILING = 4.0
RATE_ERRORS_WINDOW = 100       # look at the last N requests
RATE_ERRORS_TRIGGER = 3        # more than this many -> escalate
CLEAN_RUN_TO_RELAX = 200       # consecutive clean requests -> relax

MAX_RETRIES = 4
BACKOFF_BASE = 2.0             # seconds; doubles each attempt


# ---------------------------------------------------------------------------
# Adaptive delay
# ---------------------------------------------------------------------------

class DelayController:
    """
    Sleeps between requests, and adjusts itself when the provider pushes back.

    Escalate: more than RATE_ERRORS_TRIGGER rate-limit errors inside the last
    RATE_ERRORS_WINDOW requests doubles the delay, capped at DELAY_CEILING.
    Relax:    CLEAN_RUN_TO_RELAX consecutive clean requests halves it, floored
              at DELAY_FLOOR.

    Every change is logged with the request count at which it happened, and the
    whole history is printed in the end-of-run summary. A run that quietly
    throttled itself for two hours should say so.
    """

    def __init__(self):
        self.delay = DELAY_START
        self.requests = 0
        self.clean_streak = 0
        self.recent = []          # bools, last RATE_ERRORS_WINDOW requests
        self.rate_errors = 0
        self.history = []

    def _log(self, direction, old, new):
        entry = {
            "request": self.requests,
            "direction": direction,
            "from": round(old, 2),
            "to": round(new, 2),
            "rate_errors_so_far": self.rate_errors,
        }
        self.history.append(entry)
        print(f"    [delay] {direction} {old:.2f}s -> {new:.2f}s "
              f"at request {self.requests} "
              f"({self.rate_errors} rate errors so far)")

    def record(self, rate_limited):
        self.requests += 1
        self.recent.append(bool(rate_limited))
        if len(self.recent) > RATE_ERRORS_WINDOW:
            self.recent.pop(0)

        if rate_limited:
            self.rate_errors += 1
            self.clean_streak = 0
            if sum(self.recent) > RATE_ERRORS_TRIGGER and self.delay < DELAY_CEILING:
                old = self.delay
                self.delay = min(self.delay * 2, DELAY_CEILING)
                self._log("escalate", old, self.delay)
                # Start the window fresh so one bad patch does not escalate
                # repeatedly on the same errors.
                self.recent.clear()
        else:
            self.clean_streak += 1
            if self.clean_streak >= CLEAN_RUN_TO_RELAX and self.delay > DELAY_FLOOR:
                old = self.delay
                self.delay = max(self.delay / 2, DELAY_FLOOR)
                self._log("relax", old, self.delay)
                self.clean_streak = 0

    def sleep(self):
        time.sleep(self.delay)


def is_rate_limit(exc):
    if isinstance(exc, YFRateLimitError):
        return True
    text = str(exc).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def with_retries(fn, label, delays, max_retries=MAX_RETRIES):
    """
    Call fn(), retrying with exponential backoff. Returns (value, error_type).

    A failure returns rather than raises: one dead ticker in 7,000 must not end
    a two-hour run.
    """
    last = None
    for attempt in range(max_retries):
        try:
            value = fn()
            delays.record(rate_limited=False)
            return value, None
        except Exception as e:                       # noqa: BLE001
            last = e
            rate_limited = is_rate_limit(e)
            delays.record(rate_limited=rate_limited)
            if attempt < max_retries - 1:
                wait = BACKOFF_BASE * (2 ** attempt)
                if rate_limited:
                    wait *= 2
                time.sleep(wait)
    return None, type(last).__name__ if last else "Unknown"


# ---------------------------------------------------------------------------
# Cache helpers -- append-only JSONL, one record per ticker
# ---------------------------------------------------------------------------

def read_jsonl(path):
    """Existing records keyed by symbol. Tolerates a truncated final line."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue                 # killed mid-write; it gets refetched
            if "symbol" in rec:
                out[rec["symbol"]] = rec
    return out


class JsonlWriter:
    """Append-only writer, flushed per record so a crash keeps what came before."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, "a", encoding="utf-8")

    def write(self, record):
        self.f.write(json.dumps(record) + "\n")
        self.f.flush()
        os.fsync(self.f.fileno())

    def close(self):
        self.f.close()


def save_failures(path, failures):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "written_at": datetime.now(timezone.utc).isoformat(),
            "count": len(failures),
            "failures": failures,
        }, f, indent=2)


# ---------------------------------------------------------------------------
# Stage A -- symbol list
# ---------------------------------------------------------------------------

def stage_a(force=False):
    if os.path.exists(SYMBOLS_CACHE) and not force:
        with open(SYMBOLS_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        print(f"  cached from {cached['fetched_at'][:10]}: "
              f"{len(cached['symbols']):,} symbols")
        return cached["symbols"]

    rows = {}
    for url, col in NASDAQ_SOURCES:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        n = 0
        for row in csv.DictReader(io.StringIO(r.text), delimiter="|"):
            sym = (row.get(col) or "").strip()
            if not sym or sym.startswith("File Creation"):
                continue
            if row.get("Test Issue") == "Y":
                continue
            rows[sym] = {
                "symbol_raw": sym,
                "name": (row.get("Security Name") or "").strip(),
                "exchange": (row.get("Listing Exchange")
                             or row.get("Exchange") or "").strip(),
                "is_etf_flag": row.get("ETF") == "Y",
            }
            n += 1
        print(f"  {url.rsplit('/', 1)[-1]}: {n:,} rows")

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SYMBOLS_CACHE, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "symbols": rows,
        }, f, indent=1)

    print(f"  total unique: {len(rows):,}  -> cached to {SYMBOLS_CACHE}")
    return rows


# ---------------------------------------------------------------------------
# Stage A2 -- security-type filter, before any price request
# ---------------------------------------------------------------------------

NAME_REJECT = (
    "warrant", "unit", " right", "rights", "preferred", "depositary",
    "depositry", "fund", "trust", "etn", "note", "debenture", "when issued",
    "liquidating", "convertible", "subordinated", "capital securities",
    "beneficial interest", "royalty", "partnership",
)

# Suffix letters NASDAQ appends for non-common classes.
SUFFIX_REJECT = ("W", "U", "R", "P")


def looks_like_common_stock(symbol, name):
    """
    True if this looks like ordinary common stock.

    Deliberately strict: a false reject costs one name out of thousands, a
    false accept puts a warrant or a closed-end fund into a decile.
    """
    low = name.lower()
    if any(word in low for word in NAME_REJECT):
        return False

    # Preferreds and similar carry '$' or '.' class markers in NASDAQ symbols.
    if "$" in symbol or "." in symbol:
        return False

    # A 5th letter on a 5-character symbol is a class marker. 'W' warrants,
    # 'U' units, 'R' rights, 'P' preferred. (Nasdaq 5th-letter convention.)
    if len(symbol) == 5 and symbol[-1] in SUFFIX_REJECT:
        return False

    return True


def stage_a2(symbols):
    kept, dropped = {}, {"etf_flag": 0, "name_or_suffix": 0}
    for sym, meta in symbols.items():
        if meta["is_etf_flag"]:
            dropped["etf_flag"] += 1
            continue
        if not looks_like_common_stock(sym, meta["name"]):
            dropped["name_or_suffix"] += 1
            continue
        # yfinance uses '-' for share classes where NASDAQ uses '.'
        kept[sym.replace(".", "-")] = meta

    print(f"  dropped ETF flag:          {dropped['etf_flag']:,}")
    print(f"  dropped name/suffix rules: {dropped['name_or_suffix']:,}")
    print(f"  surviving:                 {len(kept):,}")
    return kept


# ---------------------------------------------------------------------------
# Stage B/C -- prices and liquidity
# ---------------------------------------------------------------------------

def stage_bc(symbols, delays):
    done = read_jsonl(PRICES_CACHE)
    todo = [s for s in sorted(symbols) if s not in done]

    print(f"  cached already: {len(done):,}   to fetch: {len(todo):,}")
    if not todo:
        return done, {}

    writer = JsonlWriter(PRICES_CACHE)
    failures = {}
    started = time.time()
    processed = 0

    try:
        for i in range(0, len(todo), PRICE_CHUNK):
            chunk = todo[i:i + PRICE_CHUNK]

            data, err = with_retries(
                lambda: yf.download(chunk, period=PRICE_PERIOD, interval="1d",
                                    auto_adjust=True, group_by="ticker",
                                    progress=False, threads=True),
                f"prices[{i}]", delays,
            )

            if data is None:
                for s in chunk:
                    failures[s] = err or "download_failed"
                processed += len(chunk)
                continue

            for s in chunk:
                try:
                    df = data[s][["Close", "Volume"]].dropna()
                except (KeyError, TypeError):
                    failures[s] = "no_data"
                    continue

                if df.empty:
                    failures[s] = "no_data"
                    continue

                dv = df["Close"] * df["Volume"]
                writer.write({
                    "symbol": s,
                    "sessions": int(len(df)),
                    "first_date": df.index[0].date().isoformat(),
                    "last_date": df.index[-1].date().isoformat(),
                    "last_close": float(df["Close"].iloc[-1]),
                    "median_dollar_volume": float(dv.median()),
                    "mean_dollar_volume": float(dv.mean()),
                })

            processed += len(chunk)
            if processed % PROGRESS_EVERY < PRICE_CHUNK:
                el = time.time() - started
                rate = processed / el if el else 0
                left = (len(todo) - processed) / rate if rate else 0
                print(f"    {processed:,}/{len(todo):,} symbols  "
                      f"{el/60:.1f} min elapsed  "
                      f"~{left/60:.0f} min left  "
                      f"{len(failures):,} failed")

            delays.sleep()
    except KeyboardInterrupt:
        print("\n  interrupted -- everything fetched so far is cached")
    finally:
        writer.close()
        save_failures(PRICE_FAILURES, failures)

    return read_jsonl(PRICES_CACHE), failures


def apply_liquidity_and_history(prices):
    kept, reasons = {}, {"short_history": 0, "illiquid": 0}
    for s, rec in prices.items():
        if rec["sessions"] < MIN_SESSIONS:
            reasons["short_history"] += 1
            continue
        if rec["median_dollar_volume"] < MIN_MEDIAN_DOLLAR_VOLUME:
            reasons["illiquid"] += 1
            continue
        kept[s] = rec

    print(f"  dropped <{MIN_SESSIONS} sessions:        "
          f"{reasons['short_history']:,}")
    print(f"  dropped <${MIN_MEDIAN_DOLLAR_VOLUME/1e3:.0f}k median $vol: "
          f"{reasons['illiquid']:,}")
    print(f"  surviving:                      {len(kept):,}")
    return kept


# ---------------------------------------------------------------------------
# Stage D/E -- market cap, quoteType, scope band
# ---------------------------------------------------------------------------

def stage_de(symbols, delays):
    done = read_jsonl(PROFILE_CACHE)
    todo = [s for s in sorted(symbols) if s not in done]

    print(f"  cached already: {len(done):,}   to fetch: {len(todo):,}")
    if not todo:
        return done, {}

    writer = JsonlWriter(PROFILE_CACHE)
    failures = {}
    started = time.time()

    def fetch(sym):
        info = yf.Ticker(sym).info or {}
        return {
            "symbol": sym,
            "market_cap": info.get("marketCap"),
            "quote_type": info.get("quoteType"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "currency": info.get("currency"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        for n, sym in enumerate(todo, start=1):
            rec, err = with_retries(lambda s=sym: fetch(s), sym, delays)

            if rec is None:
                failures[sym] = err or "info_failed"
            else:
                writer.write(rec)

            if n % PROGRESS_EVERY == 0:
                el = time.time() - started
                rate = n / el if el else 0
                left = (len(todo) - n) / rate if rate else 0
                print(f"    {n:,}/{len(todo):,}  "
                      f"{el/60:.1f} min elapsed  "
                      f"~{left/60:.0f} min left  "
                      f"{len(failures):,} failed  "
                      f"delay {delays.delay:.2f}s")

            delays.sleep()
    except KeyboardInterrupt:
        print("\n  interrupted -- everything fetched so far is cached")
    finally:
        writer.close()
        save_failures(PROFILE_FAILURES, failures)

    return read_jsonl(PROFILE_CACHE), failures


def apply_scope(profiles, prices, meta):
    rows, reasons = [], {
        "no_cap": 0, "below_floor": 0, "above_ceiling": 0,
        "quote_type": 0, "currency": 0,
    }

    for s, p in profiles.items():
        if s not in prices:
            continue

        if p.get("quote_type") not in (None, "EQUITY"):
            reasons["quote_type"] += 1
            continue
        if p.get("currency") not in (None, "USD"):
            reasons["currency"] += 1
            continue

        cap = p.get("market_cap")
        if not cap:
            reasons["no_cap"] += 1
            continue
        if cap < CAP_MIN:
            reasons["below_floor"] += 1
            continue
        if cap > CAP_MAX:
            reasons["above_ceiling"] += 1
            continue

        px = prices[s]
        m = meta.get(s, {})
        rows.append({
            "symbol": s,
            "name": m.get("name", ""),
            "exchange": m.get("exchange", ""),
            "sector": p.get("sector") or "",
            "industry": p.get("industry") or "",
            "market_cap": int(cap),
            "market_cap_musd": round(cap / 1e6, 1),
            "median_dollar_volume": round(px["median_dollar_volume"], 2),
            "median_dollar_volume_musd": round(px["median_dollar_volume"] / 1e6, 4),
            "sessions": px["sessions"],
            "first_date": px["first_date"],
            "last_date": px["last_date"],
            "last_close": round(px["last_close"], 4),
            "shares_outstanding": p.get("shares_outstanding"),
        })

    print(f"  dropped non-EQUITY quoteType: {reasons['quote_type']:,}")
    print(f"  dropped non-USD currency:     {reasons['currency']:,}")
    print(f"  dropped no market cap:        {reasons['no_cap']:,}")
    print(f"  dropped < ${CAP_MIN/1e6:.0f}m:              "
          f"{reasons['below_floor']:,}")
    print(f"  dropped > ${CAP_MAX/1e9:.0f}bn (mega caps):   "
          f"{reasons['above_ceiling']:,}")
    print(f"  FINAL UNIVERSE:               {len(rows):,}")

    return pd.DataFrame(rows).sort_values("market_cap", ascending=False)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def group_failures(*failure_dicts):
    grouped = {}
    for d in failure_dicts:
        for sym, reason in d.items():
            grouped.setdefault(reason, []).append(sym)
    return grouped


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    delays = DelayController()
    started = time.time()

    section("STAGE A -- symbol list")
    symbols = stage_a()

    section("STAGE A2 -- security-type filter (before any price request)")
    candidates = stage_a2(symbols)

    section("STAGE B -- batch price download (5y daily)")
    prices, price_failures = stage_bc(candidates, delays)

    section("STAGE C -- history and liquidity")
    liquid = apply_liquidity_and_history(prices)

    section("STAGE D/E -- market cap, quoteType, scope band")
    profiles, profile_failures = stage_de(liquid, delays)
    universe = apply_scope(profiles, liquid, candidates)

    if universe.empty:
        print("\nNo names survived. Nothing written.")
        return

    os.makedirs(STUDY_DIR, exist_ok=True)
    universe.to_csv(OUTPUT_CSV, index=False)

    # ----- funnel -----
    section("FUNNEL")
    print()
    funnel = pd.DataFrame([
        {"stage": "A  symbol list", "count": len(symbols)},
        {"stage": "A2 common stock only", "count": len(candidates)},
        {"stage": "B  priced", "count": len(prices)},
        {"stage": "C  history + liquidity", "count": len(liquid)},
        {"stage": "D/E cap band + quoteType", "count": len(universe)},
    ])
    funnel["pct_of_start"] = (funnel["count"] / len(symbols) * 100).round(1)
    print(funnel.to_string(index=False))

    # ----- distributions -----
    section("MARKET CAP DISTRIBUTION (final universe)")
    caps = universe["market_cap"] / 1e6
    print()
    for q in (0, 10, 25, 50, 75, 90, 100):
        print(f"  p{q:<3} ${np.percentile(caps, q):>10,.0f}m")
    print(f"\n  mean   ${caps.mean():>10,.0f}m")
    bands = [(100, 300), (300, 1000), (1000, 2000), (2000, 5000), (5000, 10000)]
    print()
    for lo, hi in bands:
        n = int(((caps >= lo) & (caps < hi)).sum())
        print(f"  ${lo:>5,}m - ${hi:>6,}m: {n:>5,}  "
              f"({n/len(caps)*100:4.1f}%)")

    section("LIQUIDITY DISTRIBUTION (median daily dollar volume)")
    dv = universe["median_dollar_volume"] / 1e6
    print()
    for q in (0, 10, 20, 25, 50, 75, 90, 100):
        print(f"  p{q:<3} ${np.percentile(dv, q):>10,.3f}M")
    print(f"\n  The p20 line is the bottom liquidity quintile boundary used by")
    print(f"  the analysis-step robustness check: ${np.percentile(dv, 20):,.3f}M")

    if "sector" in universe:
        section("SECTOR COUNTS")
        print()
        print(universe["sector"].replace("", "(unknown)")
              .value_counts().to_string())

    # ----- run summary -----
    section("RUN SUMMARY")
    grouped = group_failures(price_failures, profile_failures)
    total_failed = sum(len(v) for v in grouped.values())
    elapsed = time.time() - started

    print(f"""
  resolved (in final universe):  {len(universe):,}
  priced records cached:         {len(prices):,}
  profile records cached:        {len(profiles):,}
  failed this run:               {total_failed:,}
  elapsed:                       {elapsed/60:.1f} min
  requests made:                 {delays.requests:,}
  rate-limit errors:             {delays.rate_errors:,}
  final delay:                   {delays.delay:.2f}s
""")

    if grouped:
        print("  failure reasons, grouped:")
        for reason, syms in sorted(grouped.items(),
                                   key=lambda kv: -len(kv[1])):
            sample = ", ".join(syms[:8])
            more = f" ... +{len(syms)-8}" if len(syms) > 8 else ""
            print(f"    {reason:<28} {len(syms):>5,}   {sample}{more}")
        print(f"\n  full lists: {PRICE_FAILURES}, {PROFILE_FAILURES}")
    else:
        print("  no failures")

    if delays.history:
        print("\n  delay escalation history:")
        for h in delays.history:
            print(f"    request {h['request']:>6,}  {h['direction']:<9} "
                  f"{h['from']:.2f}s -> {h['to']:.2f}s  "
                  f"({h['rate_errors_so_far']} rate errors by then)")
    else:
        print(f"\n  delay never changed from {DELAY_START:.2f}s "
              f"(no rate-limit pressure)")

    print(f"\n  written to {OUTPUT_CSV}")
    print("\n  Re-running skips everything cached. Delete files in "
          f"{CACHE_DIR}/ to refetch a stage.")


if __name__ == "__main__":
    sys.exit(main())
