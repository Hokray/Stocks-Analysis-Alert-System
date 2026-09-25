"""
Volume window sweep.

Two changes were proposed to the screener's volume condition:

    recent window   10 days -> 5 days     ("catch the wave earlier")
    baseline window 63 days -> 20 days    ("only 1 month")

The first addresses a real defect. The volume event study measured the spike
around a 10% move as lasting roughly two days (day -2 at 2.18x, day -1 at
3.03x, everything before that flat). A 10-day trailing average dilutes a
two-day spike with eight ordinary days, which is why the live metric reads 1.13
around real moves while requiring 1.50 to fire.

The second works against the first. The recent window sits INSIDE the baseline,
so shortening the baseline lets the spike inflate its own denominator. At 10/63
the recent window is 16% of the baseline; at 5/20 it is 25%.

This sweeps window combinations and measures two things for each:

    SENSITIVITY   how often it fires at all
    DIRECTION     does it fire more before RISES than before FALLS

The second is the one that matters. A metric that fires equally on both is
detecting that something is about to happen, not what. Previous studies found
volume elevation before a 10% fall was roughly three times that before a 10%
rise, which would make a better-tuned metric worse in practice, not better.

If some combination genuinely separates rises from falls, that is a real
finding and the config should change. If none does, the question is settled
with data instead of argument.

    python research/phase2_metric_search/volume_window_sweep.py
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
sys.path.insert(0, ROOT)
os.chdir(ROOT)

warnings.filterwarnings("ignore")

RESULTS_DIR = "results/phase2"
CACHE_PATH = "cache/universe178_history.pkl"
UNIVERSE_FILE = "data/tickers_universe.csv"

MOVE_THRESHOLD = 0.10
MOVE_WINDOW = 10          # a 10% move over this many trading days

# Window pairs to test. Includes the current setting, the proposed one, and
# the combinations that isolate which half of the proposal does the work.
COMBOS = [
    (10, 63),   # current
    (5, 63),    # shorter recent only
    (3, 63),    # shorter still
    (2, 63),
    (10, 30),   # shorter baseline only
    (10, 20),
    (5, 30),
    (5, 20),    # the full proposal
    (3, 30),
    (3, 20),
    (2, 20),
]

TRIGGERS = [1.20, 1.35, 1.50, 1.75]

# Evaluate on the same six quarters used in the multi-period test, so the
# result is not another two-period coincidence.
PERIODS = [
    ("Mar-May 2024", "2024-03-01", "2024-05-31"),
    ("Jun-Aug 2024", "2024-06-01", "2024-08-31"),
    ("Sep-Nov 2024", "2024-09-01", "2024-11-30"),
    ("Mar-May 2025", "2025-03-01", "2025-05-31"),
    ("Jun-Aug 2025", "2025-06-01", "2025-08-31"),
    ("Sep-Nov 2025", "2025-09-01", "2025-11-30"),
]


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
        print(f"Downloading history for {len(tickers)} tickers...")
        os.makedirs("cache", exist_ok=True)
        data = yf.download(tickers, start="2023-06-01", interval="1d",
                           auto_adjust=True, group_by="ticker",
                           progress=True, threads=True)
        data.to_pickle(CACHE_PATH)

    frames = {}
    for t in tickers:
        try:
            df = data[t][["Close", "Volume"]].dropna()
        except (KeyError, TypeError):
            continue
        if len(df) < 150:
            continue
        out = pd.DataFrame(index=df.index)
        out["close"] = df["Close"]
        out["dollar_volume"] = df["Close"] * df["Volume"]
        # What the stock does over the NEXT MOVE_WINDOW days -- the outcome
        out["fwd_move"] = df["Close"].shift(-MOVE_WINDOW) / df["Close"] - 1
        frames[t] = out

    return frames


def add_ratio(df, recent_n, base_n):
    dv = df["dollar_volume"]
    return dv.rolling(recent_n).mean() / dv.rolling(base_n).mean()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(frames, recent_n, base_n, trigger):
    """
    For every (ticker, day) in the six periods, ask two questions:
      did the volume metric fire that day?
      did the stock rise 10%, fall 10%, or neither over the next 10 days?

    Then compare the fire rate before rises against the fire rate before falls.
    """
    fired_rise = fired_fall = fired_flat = 0
    n_rise = n_fall = n_flat = 0

    for ticker, df in frames.items():
        ratio = add_ratio(df, recent_n, base_n)

        for _, start, end in PERIODS:
            window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
            if window.empty:
                continue

            r = ratio.loc[window.index]
            fwd = window["fwd_move"]

            valid = r.notna() & fwd.notna()
            if not valid.any():
                continue

            fires = (r[valid] >= trigger)
            moves = fwd[valid]

            rise = moves >= MOVE_THRESHOLD
            fall = moves <= -MOVE_THRESHOLD
            flat = ~rise & ~fall

            n_rise += int(rise.sum())
            n_fall += int(fall.sum())
            n_flat += int(flat.sum())

            fired_rise += int((fires & rise).sum())
            fired_fall += int((fires & fall).sum())
            fired_flat += int((fires & flat).sum())

    total = n_rise + n_fall + n_flat
    fired = fired_rise + fired_fall + fired_flat
    if total == 0 or n_rise == 0 or n_fall == 0:
        return None

    rate_rise = fired_rise / n_rise * 100
    rate_fall = fired_fall / n_fall * 100
    rate_flat = fired_flat / n_flat * 100

    # Of everything the metric flagged, what share preceded a rise?
    precision = fired_rise / fired * 100 if fired else np.nan
    # Base rate: what share of ALL days preceded a rise?
    base_rate = n_rise / total * 100

    return {
        "recent": recent_n,
        "baseline": base_n,
        "trigger": trigger,
        "fire_rate_pct": round(fired / total * 100, 2),
        "before_rise_pct": round(rate_rise, 2),
        "before_fall_pct": round(rate_fall, 2),
        "before_flat_pct": round(rate_flat, 2),
        "rise_minus_fall": round(rate_rise - rate_fall, 2),
        "precision_pct": round(precision, 2),
        "base_rate_pct": round(base_rate, 2),
        "edge_pp": round(precision - base_rate, 2),
        "n_fired": fired,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    frames = load_frames()
    print(f"\nUsable: {len(frames)} tickers")
    print(f"Testing {len(COMBOS)} window pairs x {len(TRIGGERS)} triggers "
          f"across {len(PERIODS)} quarters...\n")

    rows = []
    for recent_n, base_n in COMBOS:
        for trigger in TRIGGERS:
            res = evaluate(frames, recent_n, base_n, trigger)
            if res:
                rows.append(res)

    df = pd.DataFrame(rows)
    if df.empty:
        print("No results.")
        return

    # ------------------------------------------------------------------
    print("=" * 104)
    print("SENSITIVITY -- how often does each combination fire?")
    print("=" * 104 + "\n")

    pivot = df.pivot_table(index=["recent", "baseline"], columns="trigger",
                           values="fire_rate_pct")
    print(pivot.round(1).to_string())
    print("""
  % of all (ticker, day) observations where the metric fired.
  The current setting is recent=10, baseline=63, trigger=1.50.""")

    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("DIRECTION -- does it fire more before RISES than before FALLS?")
    print("=" * 104 + "\n")

    at_150 = df[df["trigger"] == 1.50].sort_values("rise_minus_fall",
                                                   ascending=False)
    print(at_150[["recent", "baseline", "fire_rate_pct", "before_rise_pct",
                  "before_fall_pct", "before_flat_pct", "rise_minus_fall"]]
          .to_string(index=False))
    print("""
  before_rise_pct: of days that preceded a 10% RISE, what share fired?
  before_fall_pct: of days that preceded a 10% FALL, what share fired?
  rise_minus_fall: the gap. Positive means the metric leans toward rises.

  A metric with no directional content fires at the same rate before both,
  giving a gap near zero.""")

    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("EDGE -- is a fired signal more likely to precede a rise than a "
          "random day is?")
    print("=" * 104 + "\n")

    best = df.sort_values("edge_pp", ascending=False).head(12)
    print(best[["recent", "baseline", "trigger", "n_fired", "precision_pct",
                "base_rate_pct", "edge_pp"]].to_string(index=False))
    print("""
  precision_pct: of the days the metric fired, what share preceded a rise?
  base_rate_pct: of ALL days, what share preceded a rise?
  edge_pp:       the difference. This is the number that matters.

  edge_pp near zero means the metric picks out days no better than choosing at
  random. Positive means it genuinely leans toward rises.""")

    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)

    current = df[(df["recent"] == 10) & (df["baseline"] == 63)
                 & (df["trigger"] == 1.50)]
    proposed = df[(df["recent"] == 5) & (df["baseline"] == 20)
                  & (df["trigger"] == 1.50)]

    if not current.empty and not proposed.empty:
        c, p = current.iloc[0], proposed.iloc[0]
        print(f"""
  Current  (10/63 @ 1.50): fires on {c['fire_rate_pct']}% of days, """
              f"""edge {c['edge_pp']:+.2f} pp
  Proposed ( 5/20 @ 1.50): fires on {p['fire_rate_pct']}% of days, """
              f"""edge {p['edge_pp']:+.2f} pp""")

    best_row = df.loc[df["edge_pp"].idxmax()]
    print(f"""
  Best edge of all {len(df)} combinations tested:
    recent={int(best_row['recent'])}, baseline={int(best_row['baseline'])}, """
          f"""trigger={best_row['trigger']}
    fires on {best_row['fire_rate_pct']}% of days, edge {best_row['edge_pp']:+.2f} pp
    ({int(best_row['n_fired'])} signals)""")

    if best_row["edge_pp"] < 2:
        print("""
  -> No combination produces a meaningful edge.

     Tuning the windows changes HOW OFTEN the metric fires, not WHAT it fires
     on. Every combination flags days that precede a rise at roughly the same
     rate as picking a day at random.

     The proposed change would make the screener less strict. It would not
     make it more informative.""")
    else:
        print("""
  -> One or more combinations show an edge worth investigating.

     Before changing the config: check the edge holds in EVERY quarter, not
     just on average. Phase 1 Study 4 and the multi-period test both killed
     findings that looked solid in aggregate and reversed on a different
     slice.""")

    df.to_csv(f"{RESULTS_DIR}/volume_window_sweep.csv", index=False)
    print(f"\n\nWritten to {RESULTS_DIR}/volume_window_sweep.csv")

    print("""
WHAT THIS DOES AND DOES NOT TEST

Tests: whether any recent/baseline/trigger combination flags days that precede
a 10% rise more often than chance, and whether it distinguishes rises from
falls.

Does not test: whether the resulting signals are profitable after costs, or
whether they hold out of sample. Those come later and only if something here
clears the bar.

Same universe, same regime, same known survivorship limitation as every other
study here.
""")


if __name__ == "__main__":
    main()