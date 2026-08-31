"""The purpose of this py file is to prove with historical data that our idea of the metrics
#actually shows that we can predict when a wave for a stock occurs"""

#What you're trying to prove

#The claim embedded in your screener is: "when these three conditions fire, the stock is more likely to keep rising than it otherwise would be."

#That's a testable prediction. Right now it's an assumption — reasonable-sounding, but unverified. The backtest checks whether history agrees.

#What the answer means

#If excess ≈ +6%: your three conditions genuinely identify better-than-average stocks. The screener works.

#If excess ≈ 0%: alerted stocks did exactly as well as randomly picking from your CSV. The screener adds nothing — you might as well buy the whole list.

#If excess is negative: the conditions systematically pick underperformers. Worth knowing.

"""
Backtest for the stock screener.

Answers the question the live screener cannot: over the last few years, did the
three conditions actually identify stocks that went on to rise?

Method
------
1. Download several years of daily history for the whole universe, once.
2. Walk through every historical date and compute the same three metrics the
   live screener uses, using ONLY data available up to that date.
3. Record every (ticker, date) where the conditions triggered.
4. Measure what each signal did over the following 5, 10, 20 and 30 trading
   days.
5. Compare that against a baseline: what the AVERAGE stock in the same universe
   did over the exact same period.

Step 5 is the point. A signal returning +4% means nothing if the whole sector
returned +6% -- that would make the screener worse than picking at random.

Run it:
    python research/phase1_validation/backtest.py
"""

import csv
import os
import sys
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

# Scripts live in research/<phase>/ but import config.py from the repo root.
# Walk up until we find it, then run from there so relative paths resolve.
ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(ROOT, "config.py")):
    ROOT = os.path.dirname(ROOT)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

HISTORY_YEARS = 3
CACHE_PATH = "cache/backtest_history.pkl"
RESULTS_DIR = "results/phase1"

# Forward-looking horizons, in trading days
HORIZONS = [5, 10, 20, 30]

# Signals within this many days of a previous signal for the same ticker are
# treated as continuations rather than new events. Without this, one two-week
# surge counts as ten separate signals and inflates the sample.
SIGNAL_GAP_DAYS = 10

# Threshold sweep ranges
VOLUME_SWEEP = [1.20, 1.35, 1.50, 1.75, 2.00]
PRICE_SWEEP = [0.03, 0.05, 0.07, 0.10, 0.15]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_universe():
    with open(config.TICKER_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def download_history(tickers, years=HISTORY_YEARS):
    """
    Bulk-download daily history for every ticker in one call, then cache it.

    Downloading once and computing offline keeps this well inside rate limits --
    the alternative (a request per ticker per date) is not viable.
    """
    os.makedirs("cache", exist_ok=True)

    if os.path.exists(CACHE_PATH):
        print(f"Loading cached history from {CACHE_PATH}")
        return pd.read_pickle(CACHE_PATH)

    print(f"Downloading {years}y of history for {len(tickers)} tickers...")
    data = yf.download(
        tickers,
        period=f"{years}y",
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=True,
        threads=True,
    )

    data.to_pickle(CACHE_PATH)
    print(f"Cached to {CACHE_PATH}")
    return data


def extract_ticker_frame(data, ticker):
    """Pull one ticker's Close/Volume out of the multi-index download."""
    try:
        df = data[ticker][["Close", "Volume"]].copy()
    except (KeyError, TypeError):
        return None

    df = df.dropna()
    if len(df) < config.BASELINE_WINDOW_DAYS + max(HORIZONS) + 10:
        return None
    return df


# ---------------------------------------------------------------------------
# Metrics -- vectorised versions of what screener.py computes per-run
# ---------------------------------------------------------------------------

def compute_metrics(df):
    """
    Add the screener's metrics as columns, computed on a rolling basis.

    Every value at row i uses only rows <= i, which is what prevents lookahead
    bias: the backtest never sees the future when deciding to signal.
    """
    out = df.copy()

    dollar_volume = out["Close"] * out["Volume"]

    out["dollar_volume"] = dollar_volume
    out["recent_dv"] = dollar_volume.rolling(config.RECENT_WINDOW_DAYS).mean()
    out["baseline_dv"] = dollar_volume.rolling(config.BASELINE_WINDOW_DAYS).mean()
    out["volume_ratio"] = out["recent_dv"] / out["baseline_dv"]

    out["price_change"] = out["Close"].pct_change(config.RECENT_WINDOW_DAYS)

    # Forward returns -- these DO look ahead, deliberately. They are the
    # outcome being measured, never an input to the signal.
    for h in HORIZONS:
        out[f"fwd_{h}d"] = out["Close"].shift(-h) / out["Close"] - 1

    return out


def find_signals(df, volume_threshold, price_threshold, gap_days=SIGNAL_GAP_DAYS):
    """
    Rows where both technical conditions hold, de-duplicated so a single
    sustained surge counts once rather than ten times.
    """
    triggered = (
        (df["volume_ratio"] >= volume_threshold)
        & (df["price_change"] >= price_threshold)
    )

    signal_dates = df.index[triggered]
    if len(signal_dates) == 0:
        return df.iloc[0:0]

    kept = [signal_dates[0]]
    for d in signal_dates[1:]:
        gap = len(df.loc[kept[-1]:d]) - 1
        if gap >= gap_days:
            kept.append(d)

    return df.loc[kept]


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def build_baseline(frames):
    """
    For every date, the mean forward return across the entire universe.

    This is the comparison that makes the results meaningful. If the sector rose
    20% in a quarter, a signal returning 15% underperformed doing nothing.
    """
    baseline = {}
    for h in HORIZONS:
        col = f"fwd_{h}d"
        series = pd.concat(
            [f[col].rename(t) for t, f in frames.items()], axis=1
        )
        baseline[h] = series.mean(axis=1)
    return baseline


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest(frames, universe_meta, baseline,
                 volume_threshold=None, price_threshold=None,
                 verbose=True):
    volume_threshold = volume_threshold or config.VOLUME_SURGE_THRESHOLD
    price_threshold = price_threshold or config.PRICE_CHANGE_THRESHOLD

    records = []

    for ticker, df in frames.items():
        signals = find_signals(df, volume_threshold, price_threshold)

        for date, row in signals.iterrows():
            record = {
                "ticker": ticker,
                "category": universe_meta.get(ticker, {}).get("category", ""),
                "date": date.date().isoformat(),
                "price": round(row["Close"], 2),
                "volume_ratio": round(row["volume_ratio"], 2),
                "price_change_pct": round(row["price_change"] * 100, 1),
            }

            for h in HORIZONS:
                fwd = row[f"fwd_{h}d"]
                base = baseline[h].get(date, np.nan)

                record[f"fwd_{h}d_pct"] = (
                    round(fwd * 100, 2) if pd.notna(fwd) else None
                )
                record[f"base_{h}d_pct"] = (
                    round(base * 100, 2) if pd.notna(base) else None
                )
                record[f"excess_{h}d_pct"] = (
                    round((fwd - base) * 100, 2)
                    if pd.notna(fwd) and pd.notna(base) else None
                )

            records.append(record)

    results = pd.DataFrame(records)

    if verbose:
        print(f"\nFound {len(results)} signals "
              f"(volume >= {volume_threshold}, price >= {price_threshold:.0%})")

    return results


def summarise(results):
    """Headline numbers per horizon."""
    if results.empty:
        return pd.DataFrame()

    rows = []
    for h in HORIZONS:
        fwd = results[f"fwd_{h}d_pct"].dropna()
        base = results[f"base_{h}d_pct"].dropna()
        excess = results[f"excess_{h}d_pct"].dropna()

        if len(fwd) == 0:
            continue

        rows.append({
            "horizon": f"{h}d",
            "signals": len(fwd),
            "mean_return_pct": round(fwd.mean(), 2),
            "median_return_pct": round(fwd.median(), 2),
            "baseline_pct": round(base.mean(), 2),
            "excess_vs_baseline_pct": round(excess.mean(), 2),
            "hit_rate_pct": round((fwd > 0).mean() * 100, 1),
            "beat_baseline_pct": round((excess > 0).mean() * 100, 1),
            "best_pct": round(fwd.max(), 1),
            "worst_pct": round(fwd.min(), 1),
        })

    return pd.DataFrame(rows)


def sweep_thresholds(frames, universe_meta, baseline):
    """
    Run the backtest across a grid of thresholds.

    This is what turns 1.50 and 7% from judgement calls into a choice backed by
    evidence -- or reveals that the choice does not matter much.
    """
    rows = []
    focus = 20  # horizon used for ranking

    for v in VOLUME_SWEEP:
        for p in PRICE_SWEEP:
            res = run_backtest(frames, universe_meta, baseline,
                               volume_threshold=v, price_threshold=p,
                               verbose=False)
            if res.empty:
                continue

            excess = res[f"excess_{focus}d_pct"].dropna()
            fwd = res[f"fwd_{focus}d_pct"].dropna()
            if len(excess) < 10:
                continue  # too few signals to mean anything

            rows.append({
                "volume_threshold": v,
                "price_threshold_pct": round(p * 100, 1),
                "signals": len(fwd),
                "mean_return_pct": round(fwd.mean(), 2),
                "excess_vs_baseline_pct": round(excess.mean(), 2),
                "hit_rate_pct": round((fwd > 0).mean() * 100, 1),
            })

    return pd.DataFrame(rows).sort_values(
        "excess_vs_baseline_pct", ascending=False
    )


def by_category(results):
    if results.empty or "category" not in results:
        return pd.DataFrame()

    grouped = results.groupby("category").agg(
        signals=("ticker", "count"),
        mean_20d_pct=("fwd_20d_pct", "mean"),
        excess_20d_pct=("excess_20d_pct", "mean"),
        hit_rate=("fwd_20d_pct", lambda s: (s > 0).mean() * 100),
    ).round(2).sort_values("excess_20d_pct", ascending=False)

    return grouped.reset_index()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    universe = load_universe()
    tickers = [r["ticker"] for r in universe]
    universe_meta = {r["ticker"]: r for r in universe}

    data = download_history(tickers)

    print("\nPreparing per-ticker metrics...")
    frames = {}
    skipped = []
    for t in tickers:
        df = extract_ticker_frame(data, t)
        if df is None:
            skipped.append(t)
            continue
        frames[t] = compute_metrics(df)

    print(f"Usable: {len(frames)} tickers")
    if skipped:
        print(f"Skipped (insufficient history): {', '.join(skipped)}")

    baseline = build_baseline(frames)

    # --- main run at the live thresholds ---
    print("\n" + "=" * 72)
    print("BACKTEST AT LIVE THRESHOLDS")
    print("=" * 72)

    results = run_backtest(frames, universe_meta, baseline)

    if results.empty:
        print("No signals found. Try loosening the thresholds.")
        return

    summary = summarise(results)
    print("\nPerformance vs universe baseline:\n")
    print(summary.to_string(index=False))

    print("\n\nBy category (20-day horizon):\n")
    cats = by_category(results)
    print(cats.to_string(index=False))

    # --- threshold sweep ---
    print("\n\n" + "=" * 72)
    print("THRESHOLD SWEEP (ranked by 20-day excess return)")
    print("=" * 72 + "\n")

    sweep = sweep_thresholds(frames, universe_meta, baseline)
    print(sweep.head(15).to_string(index=False))

    # --- save ---
    results.to_csv(f"{RESULTS_DIR}/signals.csv", index=False)
    summary.to_csv(f"{RESULTS_DIR}/summary.csv", index=False)
    sweep.to_csv(f"{RESULTS_DIR}/threshold_sweep.csv", index=False)
    cats.to_csv(f"{RESULTS_DIR}/by_category.csv", index=False)

    print(f"\n\nWritten to {RESULTS_DIR}/")

    # --- interpretation ---
    focus = summary[summary["horizon"] == "20d"]
    if not focus.empty:
        row = focus.iloc[0]
        excess = row["excess_vs_baseline_pct"]
        print("\n" + "=" * 72)
        print("READ THIS BEFORE BELIEVING ANY OF THE ABOVE")
        print("=" * 72)
        print(f"""
At 20 days, signals averaged {row['mean_return_pct']}% while the universe
averaged {row['baseline_pct']}%. Excess: {excess:+.2f} percentage points.
{row['beat_baseline_pct']}% of signals beat the baseline.

Caveats that materially affect how much this means:

1. SURVIVORSHIP BIAS. The ticker list was chosen in 2026 partly because these
   companies did well. Backtesting them over 2023-2025 flatters any strategy.

2. NO POINT-IN-TIME FUNDAMENTALS. The TTM cash-flow condition is NOT applied
   here -- yfinance does not provide historical quarterly statements far
   enough back. These results reflect the two technical conditions only.

3. SAMPLE SIZE. {int(row['signals'])} signals across a single sector during one
   market regime (the AI buildout). This does not generalise to other sectors
   or other regimes.

4. NO COSTS. Spreads, slippage and taxes are ignored.

5. OVERLAPPING PERIODS. Signals close together in time share market conditions,
   so they are not independent observations.
""")


if __name__ == "__main__":
    main()