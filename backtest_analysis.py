"""
Second-stage analysis of backtest results.

Two questions the first backtest raised but did not answer:

  1. SIZE. The biggest winners (TSSI at $0.81, BTDR at $4.55, BE at $10.67)
     were all small companies at the time they signalled. Is the entire edge
     concentrated in small caps? If so, turning on MIN_MARKET_CAP would delete
     the only part of the strategy that works.

  2. PERSISTENCE. The live screener tracks stocks that qualify day after day
     and flags them as stronger signals. That assumption has never been tested.
     Do repeat qualifiers actually outperform one-day hits?

Reads backtest_results/signals.csv and cache/backtest_history.pkl, so run
backtest.py first.

    python backtest_analysis.py
"""

import os

import numpy as np
import pandas as pd

import config

RESULTS_DIR = "backtest_results"
SIGNALS_PATH = f"{RESULTS_DIR}/signals.csv"
HISTORY_PATH = "cache/backtest_history.pkl"

FOCUS_HORIZON = 20  # the horizon used for all comparisons below


# ---------------------------------------------------------------------------
# Question 1: does size explain the edge?
# ---------------------------------------------------------------------------

def estimate_market_cap_at_signal(signals, shares_outstanding):
    """
    Approximate market cap on the signal date as price x current share count.

    This is imperfect -- share counts change through buybacks and issuance, and
    several of these companies diluted heavily. It is good enough to separate
    "microcap" from "megacap", which is the only distinction being tested.
    """
    caps = []
    for _, row in signals.iterrows():
        shares = shares_outstanding.get(row["ticker"])
        if shares and pd.notna(row["price"]):
            caps.append(row["price"] * shares / 1e9)
        else:
            caps.append(np.nan)
    return caps


def size_bucket(cap_busd):
    if pd.isna(cap_busd):
        return "unknown"
    if cap_busd < 2:
        return "1. under $2B"
    if cap_busd < 10:
        return "2. $2B - $10B"
    if cap_busd < 50:
        return "3. $10B - $50B"
    return "4. over $50B"


def analyse_by_size(signals):
    col_fwd = f"fwd_{FOCUS_HORIZON}d_pct"
    col_exc = f"excess_{FOCUS_HORIZON}d_pct"

    valid = signals.dropna(subset=[col_exc, "size_bucket"])

    grouped = valid.groupby("size_bucket").agg(
        signals=("ticker", "count"),
        mean_return_pct=(col_fwd, "mean"),
        median_return_pct=(col_fwd, "median"),
        mean_excess_pct=(col_exc, "mean"),
        median_excess_pct=(col_exc, "median"),
        beat_baseline_pct=(col_exc, lambda s: (s > 0).mean() * 100),
        best_pct=(col_fwd, "max"),
        worst_pct=(col_fwd, "min"),
    ).round(2)

    return grouped.reset_index()


def analyse_excluding_outlier_tickers(signals, n=3):
    """
    Recompute the headline number with the biggest contributors removed.

    If the whole result rests on two or three tickers, that is not a strategy,
    it is a story about those tickers.
    """
    col_exc = f"excess_{FOCUS_HORIZON}d_pct"
    valid = signals.dropna(subset=[col_exc])

    contribution = (
        valid.groupby("ticker")[col_exc]
        .sum()
        .sort_values(ascending=False)
    )

    top = contribution.head(n).index.tolist()
    without = valid[~valid["ticker"].isin(top)]

    return {
        "top_contributors": top,
        "overall_mean_excess": round(valid[col_exc].mean(), 2),
        "overall_signals": len(valid),
        "excl_mean_excess": round(without[col_exc].mean(), 2),
        "excl_signals": len(without),
        "excl_beat_baseline_pct": round((without[col_exc] > 0).mean() * 100, 1),
        "contribution_table": contribution.head(10).round(1),
    }


# ---------------------------------------------------------------------------
# Question 2: does persistence predict anything?
# ---------------------------------------------------------------------------

def compute_persistence(history, signals):
    """
    For each signal, count how many of the previous N trading days ALSO met both
    technical conditions.

    This reconstructs what the live screener's streak counter would have shown
    on that date -- using only backward-looking data.
    """
    window = config.STREAK_WINDOW_DAYS
    counts = []

    for _, row in signals.iterrows():
        ticker = row["ticker"]

        try:
            df = history[ticker][["Close", "Volume"]].dropna()
        except (KeyError, TypeError):
            counts.append(np.nan)
            continue

        dv = df["Close"] * df["Volume"]
        ratio = (dv.rolling(config.RECENT_WINDOW_DAYS).mean()
                 / dv.rolling(config.BASELINE_WINDOW_DAYS).mean())
        chg = df["Close"].pct_change(config.RECENT_WINDOW_DAYS)

        qualifying = (
            (ratio >= config.VOLUME_SURGE_THRESHOLD)
            & (chg >= config.PRICE_CHANGE_THRESHOLD)
        )

        signal_date = pd.Timestamp(row["date"])
        try:
            idx = qualifying.index.get_indexer([signal_date], method="nearest")[0]
        except Exception:
            counts.append(np.nan)
            continue

        start = max(0, idx - window + 1)
        counts.append(int(qualifying.iloc[start:idx + 1].sum()))

    return counts


def persistence_bucket(count):
    if pd.isna(count):
        return "unknown"
    if count <= 2:
        return "1. brief (1-2 days)"
    if count <= 5:
        return "2. building (3-5 days)"
    if count <= 9:
        return "3. persistent (6-9 days)"
    return "4. very persistent (10+ days)"


def analyse_by_persistence(signals):
    col_fwd = f"fwd_{FOCUS_HORIZON}d_pct"
    col_exc = f"excess_{FOCUS_HORIZON}d_pct"

    valid = signals.dropna(subset=[col_exc, "persistence_bucket"])

    grouped = valid.groupby("persistence_bucket").agg(
        signals=("ticker", "count"),
        mean_return_pct=(col_fwd, "mean"),
        median_return_pct=(col_fwd, "median"),
        mean_excess_pct=(col_exc, "mean"),
        beat_baseline_pct=(col_exc, lambda s: (s > 0).mean() * 100),
    ).round(2)

    return grouped.reset_index()


def analyse_size_and_persistence(signals):
    """Both dimensions at once -- where does the edge actually live?"""
    col_exc = f"excess_{FOCUS_HORIZON}d_pct"
    valid = signals.dropna(subset=[col_exc, "size_bucket", "persistence_bucket"])

    pivot = valid.pivot_table(
        index="size_bucket",
        columns="persistence_bucket",
        values=col_exc,
        aggfunc="mean",
    ).round(1)

    counts = valid.pivot_table(
        index="size_bucket",
        columns="persistence_bucket",
        values=col_exc,
        aggfunc="count",
    )

    return pivot, counts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(SIGNALS_PATH):
        print(f"{SIGNALS_PATH} not found. Run backtest.py first.")
        return
    if not os.path.exists(HISTORY_PATH):
        print(f"{HISTORY_PATH} not found. Run backtest.py first.")
        return

    signals = pd.read_csv(SIGNALS_PATH)
    history = pd.read_pickle(HISTORY_PATH)

    print(f"Loaded {len(signals)} signals\n")

    # --- share counts, used to approximate historical market cap ---
    print("Fetching share counts...")
    import yfinance as yf
    shares_outstanding = {}
    for t in signals["ticker"].unique():
        try:
            s = yf.Ticker(t).fast_info.get("shares")
            if s:
                shares_outstanding[t] = float(s)
        except Exception:
            pass
    print(f"Got share counts for {len(shares_outstanding)} tickers\n")

    signals["market_cap_busd"] = estimate_market_cap_at_signal(
        signals, shares_outstanding
    )
    signals["size_bucket"] = signals["market_cap_busd"].apply(size_bucket)

    print("Reconstructing persistence counts...")
    signals["persistence_days"] = compute_persistence(history, signals)
    signals["persistence_bucket"] = signals["persistence_days"].apply(
        persistence_bucket
    )

    # --- Q1: size ---
    print("\n" + "=" * 78)
    print(f"QUESTION 1: DOES SIZE EXPLAIN THE EDGE?   ({FOCUS_HORIZON}-day horizon)")
    print("=" * 78 + "\n")

    by_size = analyse_by_size(signals)
    print(by_size.to_string(index=False))

    print("\n\nIf 'under $2B' shows a much larger mean_excess_pct than the")
    print("larger buckets, then enabling MIN_MARKET_CAP would remove the only")
    print("part of the strategy that works.\n")

    # --- outlier dependence ---
    print("\n" + "=" * 78)
    print("HOW MUCH RESTS ON A FEW TICKERS?")
    print("=" * 78 + "\n")

    out = analyse_excluding_outlier_tickers(signals, n=3)
    print("Largest total excess-return contributors:\n")
    print(out["contribution_table"].to_string())
    print(f"\nAll signals:        {out['overall_signals']:>4}  "
          f"mean excess {out['overall_mean_excess']:+.2f} pp")
    print(f"Excluding {', '.join(out['top_contributors']):<18} "
          f"{out['excl_signals']:>4}  mean excess {out['excl_mean_excess']:+.2f} pp")
    print(f"                          beat baseline: "
          f"{out['excl_beat_baseline_pct']}%")

    # --- Q2: persistence ---
    print("\n\n" + "=" * 78)
    print(f"QUESTION 2: DOES PERSISTENCE PREDICT ANYTHING?   "
          f"({FOCUS_HORIZON}-day horizon)")
    print("=" * 78 + "\n")

    by_persist = analyse_by_persistence(signals)
    print(by_persist.to_string(index=False))

    print("\n\nThe live screener assumes more qualifying days = stronger signal.")
    print("If mean_excess_pct does NOT rise across these buckets, that")
    print("assumption is wrong and the streak tag is decoration.\n")

    # --- combined ---
    print("\n" + "=" * 78)
    print("BOTH DIMENSIONS: mean excess return (pp)")
    print("=" * 78 + "\n")

    pivot, counts = analyse_size_and_persistence(signals)
    print(pivot.to_string())
    print("\nSignal counts per cell (ignore cells under ~10):\n")
    print(counts.to_string())

    # --- save ---
    signals.to_csv(f"{RESULTS_DIR}/signals_enriched.csv", index=False)
    by_size.to_csv(f"{RESULTS_DIR}/by_size.csv", index=False)
    by_persist.to_csv(f"{RESULTS_DIR}/by_persistence.csv", index=False)
    pivot.to_csv(f"{RESULTS_DIR}/size_x_persistence.csv")

    print(f"\n\nWritten to {RESULTS_DIR}/")
    print("""
Reminder on reading any of this: slicing 495 signals several ways produces
small subgroups, and small subgroups produce impressive-looking numbers by
chance. Treat any cell with fewer than ~30 signals as a hint, not a finding.
""")


if __name__ == "__main__":
    main()