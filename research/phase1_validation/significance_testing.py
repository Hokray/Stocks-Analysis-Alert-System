"""
Significance testing and persistence threshold optimisation.

Two questions:

  1. IS THE EDGE REAL? The backtest found +2.54pp mean excess return. That
     number means nothing on its own -- a screener with zero skill would still
     produce a non-zero result through luck. This estimates how much of the
     result could be luck.

  2. WHERE SHOULD THE PERSISTENCE THRESHOLD SIT? The live screener uses
     PERSISTENT_STREAK_MIN = 4. That was a guess. This sweeps every threshold
     from 2 to 14 and reports where the edge actually concentrates.

Requires backtest_results/signals_enriched.csv (run backtest_analysis.py first).

    python significance_test.py
"""

import os

import numpy as np
import pandas as pd

RESULTS_DIR = "backtest_results"
SIGNALS_PATH = f"{RESULTS_DIR}/signals_enriched.csv"

FOCUS_HORIZON = 20
N_BOOTSTRAP = 10000
RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def bootstrap_by_ticker(df, col, n_iterations=N_BOOTSTRAP, seed=RANDOM_SEED):
    """
    Resample TICKERS with replacement, not individual signals.

    This matters more than it sounds. TSSI contributed 24 signals, all from the
    same stock over the same period, driven by the same underlying move. They
    are not 24 independent pieces of evidence -- they are closer to one.

    Resampling individual signals would treat them as independent and produce a
    confidence interval that is far too narrow, making a fragile result look
    solid. Resampling whole tickers keeps each stock's signals together and
    reflects the real uncertainty: what if this universe had contained a
    different set of companies?
    """
    rng = np.random.default_rng(seed)

    tickers = df["ticker"].unique()
    by_ticker = {t: df.loc[df["ticker"] == t, col].dropna().values
                 for t in tickers}
    by_ticker = {t: v for t, v in by_ticker.items() if len(v) > 0}
    ticker_list = list(by_ticker.keys())

    means = np.empty(n_iterations)
    for i in range(n_iterations):
        picked = rng.choice(ticker_list, size=len(ticker_list), replace=True)
        pooled = np.concatenate([by_ticker[t] for t in picked])
        means[i] = pooled.mean()

    return means


def bootstrap_naive(df, col, n_iterations=N_BOOTSTRAP, seed=RANDOM_SEED):
    """Resample individual signals -- shown only for contrast."""
    rng = np.random.default_rng(seed)
    values = df[col].dropna().values
    idx = rng.integers(0, len(values), size=(n_iterations, len(values)))
    return values[idx].mean(axis=1)


def summarise_bootstrap(means, observed, label):
    lo, hi = np.percentile(means, [2.5, 97.5])
    p_le_zero = (means <= 0).mean()

    print(f"\n{label}")
    print(f"  Observed mean excess:      {observed:+.2f} pp")
    print(f"  95% confidence interval:   {lo:+.2f} pp to {hi:+.2f} pp")
    print(f"  Share of resamples <= 0:   {p_le_zero * 100:.1f}%")

    if lo > 0:
        print("  -> Interval excludes zero. Evidence of a real effect.")
    elif hi < 0:
        print("  -> Interval is entirely negative. Evidence of a NEGATIVE effect.")
    else:
        print("  -> Interval INCLUDES zero. Cannot distinguish this from luck.")

    return {"lo": lo, "hi": hi, "p_le_zero": p_le_zero}


# ---------------------------------------------------------------------------
# Persistence sweep
# ---------------------------------------------------------------------------

def sweep_persistence(df, col_exc, col_fwd, min_group=25):
    """
    For each candidate threshold k, split signals into those with >= k
    qualifying days and those below, and compare.

    The number that matters is the GAP between the two groups. A threshold is
    only useful if signals above it behave differently from signals below it.
    """
    rows = []

    for k in range(2, 15):
        above = df[df["persistence_days"] >= k]
        below = df[df["persistence_days"] < k]

        a_exc = above[col_exc].dropna()
        b_exc = below[col_exc].dropna()

        if len(a_exc) < min_group or len(b_exc) < min_group:
            continue

        rows.append({
            "threshold": k,
            "n_above": len(a_exc),
            "n_below": len(b_exc),
            "excess_above_pp": round(a_exc.mean(), 2),
            "excess_below_pp": round(b_exc.mean(), 2),
            "gap_pp": round(a_exc.mean() - b_exc.mean(), 2),
            "beat_above_pct": round((a_exc > 0).mean() * 100, 1),
            "beat_below_pct": round((b_exc > 0).mean() * 100, 1),
            "median_above_pp": round(a_exc.median(), 2),
        })

    return pd.DataFrame(rows)


def test_best_threshold(df, k, col_exc):
    """Bootstrap the above-threshold group at the chosen k."""
    above = df[df["persistence_days"] >= k]
    observed = above[col_exc].dropna().mean()
    means = bootstrap_by_ticker(above, col_exc)
    return observed, means, above


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(SIGNALS_PATH):
        print(f"{SIGNALS_PATH} not found. Run backtest_analysis.py first.")
        return

    df = pd.read_csv(SIGNALS_PATH)
    col_exc = f"excess_{FOCUS_HORIZON}d_pct"
    col_fwd = f"fwd_{FOCUS_HORIZON}d_pct"

    df = df.dropna(subset=[col_exc])
    print(f"Loaded {len(df)} signals across {df['ticker'].nunique()} tickers")

    # =======================================================================
    # PART 1: is the overall edge real?
    # =======================================================================
    print("\n" + "=" * 74)
    print("PART 1: IS THE OVERALL EDGE DISTINGUISHABLE FROM ZERO?")
    print("=" * 74)

    observed = df[col_exc].mean()

    naive = bootstrap_naive(df, col_exc)
    summarise_bootstrap(naive, observed,
                        "Naive bootstrap (resampling individual signals):")
    print("  NOTE: this treats every signal as independent, which they are not.")
    print("  It understates uncertainty. Shown only for comparison.")

    clustered = bootstrap_by_ticker(df, col_exc)
    result = summarise_bootstrap(
        clustered, observed,
        "Clustered bootstrap (resampling tickers) -- THIS IS THE HONEST ONE:"
    )

    naive_width = np.percentile(naive, 97.5) - np.percentile(naive, 2.5)
    clust_width = result["hi"] - result["lo"]
    print(f"\n  The clustered interval is {clust_width / naive_width:.1f}x wider.")
    print("  That gap is how much the naive version would have flattered you.")

    # =======================================================================
    # PART 2: where should the persistence threshold sit?
    # =======================================================================
    print("\n\n" + "=" * 74)
    print("PART 2: PERSISTENCE THRESHOLD SWEEP")
    print("=" * 74 + "\n")

    if "persistence_days" not in df.columns:
        print("No persistence_days column. Re-run backtest_analysis.py.")
        return

    sweep = sweep_persistence(df, col_exc, col_fwd)

    if sweep.empty:
        print("Not enough data on either side of any threshold.")
        return

    print(sweep.to_string(index=False))

    best = sweep.loc[sweep["gap_pp"].idxmax()]
    k = int(best["threshold"])

    print(f"\n\nLargest gap at threshold = {k}:")
    print(f"  {int(best['n_above'])} signals at or above: "
          f"{best['excess_above_pp']:+.2f} pp excess, "
          f"{best['beat_above_pct']}% beat baseline")
    print(f"  {int(best['n_below'])} signals below:       "
          f"{best['excess_below_pp']:+.2f} pp excess, "
          f"{best['beat_below_pct']}% beat baseline")
    print(f"  Gap: {best['gap_pp']:+.2f} pp")

    # =======================================================================
    # PART 3: is THAT group's edge real?
    # =======================================================================
    print("\n\n" + "=" * 74)
    print(f"PART 3: IS THE EDGE AT THRESHOLD {k} DISTINGUISHABLE FROM ZERO?")
    print("=" * 74)

    obs_k, means_k, above = test_best_threshold(df, k, col_exc)
    summarise_bootstrap(means_k, obs_k,
                        f"Signals with >= {k} qualifying days "
                        f"({len(above)} signals, "
                        f"{above['ticker'].nunique()} tickers):")

    contrib = (above.groupby("ticker")[col_exc].sum()
               .sort_values(ascending=False).head(5))
    print("\n  Top contributors within this group:")
    for t, v in contrib.items():
        print(f"    {t:<6} {v:+.1f} pp")

    top3 = contrib.head(3).index.tolist()
    without = above[~above["ticker"].isin(top3)]
    if len(without) > 20:
        print(f"\n  Excluding {', '.join(top3)}: "
              f"{without[col_exc].mean():+.2f} pp "
              f"({len(without)} signals, "
              f"{(without[col_exc] > 0).mean() * 100:.1f}% beat baseline)")

    # --- save ---
    sweep.to_csv(f"{RESULTS_DIR}/persistence_sweep.csv", index=False)

    pd.DataFrame([{
        "group": "all signals",
        "n": len(df),
        "mean_excess_pp": round(observed, 2),
        "ci_low_pp": round(result["lo"], 2),
        "ci_high_pp": round(result["hi"], 2),
        "significant": result["lo"] > 0,
    }, {
        "group": f"persistence >= {k}",
        "n": len(above),
        "mean_excess_pp": round(obs_k, 2),
        "ci_low_pp": round(np.percentile(means_k, 2.5), 2),
        "ci_high_pp": round(np.percentile(means_k, 97.5), 2),
        "significant": np.percentile(means_k, 2.5) > 0,
    }]).to_csv(f"{RESULTS_DIR}/significance.csv", index=False)

    print(f"\n\nWritten to {RESULTS_DIR}/")

    print("""
HOW TO READ THIS

A 95% confidence interval that includes zero means a screener with no skill
could plausibly have produced this result. It does not prove there is no edge --
it means this data cannot tell the difference.

If Part 3's interval excludes zero while Part 1's includes it, that is the
useful finding: the base signal is indistinguishable from luck, but filtering
on persistence produces something measurable.

Two caveats that no amount of resampling fixes:

  - The threshold was chosen by looking at these same results. Picking the best
    of 13 candidates and then testing it overstates significance. Proper
    validation needs data this analysis has never seen.
  - Survivorship bias in the universe is baked in and cannot be bootstrapped
    away.
""")


if __name__ == "__main__":
    main()