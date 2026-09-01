"""
Multi-period robustness test.

The metric search found eight metrics separating future winners from
non-winners, consistently across Sep-Nov 2024 and Sep-Nov 2025.

Two periods is two observations, and both fell in the same season. A pattern
that appears only in autumn is a seasonal artefact, not a market effect. This
re-runs the identical search across six non-overlapping quarters spanning 2024
and 2025 to find out which metrics survive.

The bar rises with the number of periods. Passing two windows by chance is easy;
passing six in the same direction is not. The permutation control measures
exactly how much harder, by shuffling the winner labels and re-running the whole
search.

    python research/phase2_metric_search/multi_period_test.py
"""

import csv
import os
import sys
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(ROOT, "config.py")):
    ROOT = os.path.dirname(ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from metric_search import compute_all_metrics   # reuse the metric library

warnings.filterwarnings("ignore")

RESULTS_DIR = "results/phase2"
UNIVERSE_FILE = "data/tickers_universe.csv"

# Longer history than the 2-period run: metrics need ~252 trading days of
# lookback, so covering early 2024 requires data from at least early 2023.
CACHE_PATH = "cache/multiperiod_history.pkl"
HISTORY_START = "2022-06-01"

MOVE_THRESHOLD = 0.10
SEPARATION_BAR = 0.30
N_PERMUTATIONS = 300

# Six non-overlapping quarters. Sep-Nov appears twice so the original finding
# can be compared directly against the other seasons.
PERIODS = [
    ("Mar-May 2024", "2024-03-01", "2024-05-31"),
    ("Jun-Aug 2024", "2024-06-01", "2024-08-31"),
    ("Sep-Nov 2024", "2024-09-01", "2024-11-30"),
    ("Mar-May 2025", "2025-03-01", "2025-05-31"),
    ("Jun-Aug 2025", "2025-06-01", "2025-08-31"),
    ("Sep-Nov 2025", "2025-09-01", "2025-11-30"),
]

AUTUMN = {"Sep-Nov 2024", "Sep-Nov 2025"}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_frames():
    with open(UNIVERSE_FILE, newline="", encoding="utf-8") as f:
        tickers = [r["ticker"] for r in csv.DictReader(f)]

    if os.path.exists(CACHE_PATH):
        print(f"Loading cached history from {CACHE_PATH}")
        data = pd.read_pickle(CACHE_PATH)
    else:
        print(f"Downloading history from {HISTORY_START} "
              f"for {len(tickers)} tickers...")
        os.makedirs("cache", exist_ok=True)
        data = yf.download(tickers, start=HISTORY_START, interval="1d",
                           auto_adjust=True, group_by="ticker",
                           progress=True, threads=True)
        data.to_pickle(CACHE_PATH)

    frames = {}
    for t in tickers:
        m = compute_all_metrics(data, t)
        if m is not None:
            frames[t] = m
    return frames


def snapshot(frames, metric_cols, start, end):
    """Metrics on the period's first day; label by the period's outcome."""
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    rows = []

    for ticker, df in frames.items():
        window = df.loc[start_ts:end_ts]
        if len(window) < 20:
            continue
        entry = window.iloc[0]
        ret = window["close"].iloc[-1] / entry["close"] - 1

        row = {"ticker": ticker, "period_return_pct": ret * 100,
               "rose": ret >= MOVE_THRESHOLD}
        for c in metric_cols:
            row[c] = entry.get(c, np.nan)
        rows.append(row)

    return pd.DataFrame(rows)


def separations(df, metric_cols, label_col="rose"):
    grp, rest = df[df[label_col]], df[~df[label_col]]
    if len(grp) < 8 or len(rest) < 8:
        return None

    out = {}
    for c in metric_cols:
        a, b = grp[c].dropna(), rest[c].dropna()
        if len(a) < 8 or len(b) < 8:
            out[c] = np.nan
            continue
        pooled = np.sqrt((a.var() + b.var()) / 2)
        out[c] = (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0
    return pd.Series(out)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(table, min_meaningful):
    """
    A metric passes if it points the same direction in EVERY period and clears
    the separation bar in at least `min_meaningful` of them.

    Direction consistency is the strict half. A metric that flips sign between
    periods is describing noise regardless of how large the individual gaps
    look.
    """
    signs = np.sign(table)
    out = pd.DataFrame(index=table.index)
    out["same_direction"] = signs.apply(
        lambda r: r.dropna().nunique() == 1, axis=1)
    out["n_meaningful"] = (table.abs() >= SEPARATION_BAR).sum(axis=1)
    out["mean_sep"] = table.mean(axis=1)
    out["worst_abs"] = table.abs().min(axis=1)
    out["passes"] = out["same_direction"] & (out["n_meaningful"] >= min_meaningful)
    return out


def permutation_null(snapshots, metric_cols, min_meaningful,
                     n_perm=N_PERMUTATIONS, seed=7):
    rng = np.random.default_rng(seed)
    counts = []

    for _ in range(n_perm):
        seps = []
        ok = True
        for snap in snapshots:
            sh = snap.copy()
            sh["rose"] = rng.permutation(sh["rose"].values)
            s = separations(sh, metric_cols)
            if s is None:
                ok = False
                break
            seps.append(s)
        if not ok:
            continue
        tbl = pd.concat(seps, axis=1)
        counts.append(int(score(tbl, min_meaningful)["passes"].sum()))

    return np.array(counts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    frames = load_frames()
    metric_cols = [c for c in next(iter(frames.values())).columns
                   if c != "close"]
    print(f"\nUsable: {len(frames)} tickers, {len(metric_cols)} metrics")

    snapshots, seps, labels = [], [], []

    for label, start, end in PERIODS:
        snap = snapshot(frames, metric_cols, start, end)
        if snap.empty:
            print(f"  {label}: no data, skipped")
            continue
        s = separations(snap, metric_cols)
        if s is None:
            print(f"  {label}: groups too small, skipped")
            continue

        n_up = int(snap["rose"].sum())
        print(f"  {label}: {len(snap)} tickers, {n_up} rose "
              f"{MOVE_THRESHOLD:.0%}+ ({n_up / len(snap) * 100:.0f}%)")

        snapshots.append(snap)
        seps.append(s)
        labels.append(label)

    if len(seps) < 4:
        print("\nNeed at least four usable periods.")
        return

    table = pd.concat(seps, axis=1)
    table.columns = labels

    min_meaningful = max(2, int(np.ceil(len(labels) * 2 / 3)))
    scored = score(table, min_meaningful)

    combined = table.round(2).join(scored)
    combined = combined.sort_values(
        ["passes", "n_meaningful", "worst_abs"], ascending=False)

    print("\n" + "=" * 100)
    print(f"SEPARATION BY PERIOD (SD) -- {len(labels)} periods")
    print(f"Pass = same direction in all periods AND >= {SEPARATION_BAR} SD "
          f"in at least {min_meaningful} of {len(labels)}")
    print("=" * 100 + "\n")
    print(combined.to_string())

    hits = combined[combined["passes"]]

    print("\n" + "=" * 100)
    print(f"METRICS SURVIVING ALL {len(labels)} PERIODS: {len(hits)}")
    print("=" * 100)
    print("\n" + (hits.to_string() if len(hits) else "None."))

    # ------------------------------------------------------------------
    # Which of the original eight survived?
    # ------------------------------------------------------------------
    original_eight = [
        "atr_pct", "volatility_20d_pct", "volatility_60d_pct",
        "bollinger_width_pct", "gap_freq_21", "pct_above_52w_low",
        "ma50_vs_ma200", "momentum_accel",
    ]

    print("\n" + "=" * 100)
    print("THE EIGHT FROM THE TWO-PERIOD SEARCH -- do they hold up?")
    print("=" * 100 + "\n")

    check = combined.loc[[m for m in original_eight if m in combined.index]]
    print(check.to_string())

    survived = [m for m in original_eight if m in hits.index]
    print(f"\n  Survived: {len(survived)} of {len(original_eight)}")
    if survived:
        print(f"  -> {', '.join(survived)}")
    dropped = [m for m in original_eight if m not in hits.index]
    if dropped:
        print(f"  Dropped:  {', '.join(dropped)}")

    # ------------------------------------------------------------------
    # Seasonality
    # ------------------------------------------------------------------
    autumn_cols = [c for c in labels if c in AUTUMN]
    other_cols = [c for c in labels if c not in AUTUMN]

    if autumn_cols and other_cols:
        print("\n" + "=" * 100)
        print("SEASONALITY -- is the effect specific to Sep-Nov?")
        print("=" * 100 + "\n")

        seasonal = pd.DataFrame({
            "autumn_mean": table[autumn_cols].mean(axis=1).round(2),
            "other_mean": table[other_cols].mean(axis=1).round(2),
        })
        seasonal["gap"] = (seasonal["autumn_mean"]
                           - seasonal["other_mean"]).round(2)
        seasonal["autumn_only"] = (
            (seasonal["autumn_mean"].abs() >= SEPARATION_BAR)
            & (seasonal["other_mean"].abs() < SEPARATION_BAR / 2)
        )
        print(seasonal.reindex(combined.index).to_string())

        autumn_only = seasonal[seasonal["autumn_only"]]
        if len(autumn_only):
            print(f"\n  Metrics that separate ONLY in autumn: "
                  f"{', '.join(autumn_only.index)}")
            print("  -> These are seasonal artefacts, not market effects.")
        else:
            print("\n  No metric separates only in autumn.")

    # ------------------------------------------------------------------
    # Permutation control
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"PERMUTATION CONTROL -- {N_PERMUTATIONS} runs with shuffled labels")
    print("=" * 100)

    null = permutation_null(snapshots, metric_cols, min_meaningful)
    if len(null):
        p = (null >= len(hits)).mean()
        print(f"\n  Real search found:             {len(hits)} metric(s)")
        print(f"  Random labels find on average: {null.mean():.2f}")
        print(f"  95th percentile of random:     {np.percentile(null, 95):.0f}")
        print(f"  Chance of {len(hits)}+ by luck:            {p * 100:.1f}%")

        if p > 0.05:
            print("\n  -> Consistent with chance.")
        else:
            print("\n  -> Beyond what random labels produce.")

    combined.to_csv(f"{RESULTS_DIR}/multi_period_test.csv")
    print(f"\n\nWritten to {RESULTS_DIR}/multi_period_test.csv")

    print(f"""
HOW TO READ THIS

The two-period search found eight metrics. Passing two windows in the same
direction happens by chance reasonably often; passing {len(labels)} does not.
Whatever survives here is substantially better supported than the earlier
result.

Check the base rates printed at the top. A period where 70%+ of the universe
rose 10% is a melt-up, and "which stocks rose" barely discriminates in it. Those
periods carry less weight than their row in the table suggests.

Metrics that separate only in autumn are seasonal artefacts. That is the
specific failure this test exists to detect.

Even surviving all {len(labels)} periods is not confirmation. These are
overlapping observations from one sector in one regime, and the metrics were
selected by looking at this data. A neutral-universe test and out-of-sample
data are still required -- Phase 1 Study 4 is the reason.
""")


if __name__ == "__main__":
    main()