"""
Volume window validation -- Tests 1, 2 and 3.

Follow-up to volume_window_sweep.py, which found the strongest edges clustered
at recent=10 with a dose-response across triggers. Three problems had to be
resolved before that result could be believed.

TEST 1 -- WINDOW OVERLAP
    The sweep computed baseline as rolling(base_n), which INCLUDES the most
    recent recent_n days. At 10/20 half the denominator is the numerator, and
    the ratio is mathematically capped at 2.0 -- which is why 10/20 @ 1.75 had
    only 189 observations and broke the dose-response.

    Both definitions are computed here so the difference is visible:
        overlapping      baseline = mean of the last base_n days
        non-overlapping  baseline = mean of the base_n days ENDING recent_n
                                    days ago

TEST 2 -- DIRECTION
    The sweep reported precision and base rate for rises only, so it could not
    answer the question that matters: given that a big move is coming, does the
    metric predict WHICH WAY?

    Fall-side columns are added, plus the conditional test:
        P(rise | fired AND big move)  vs  P(rise | big move)
    If those are equal, the metric is a volatility detector with no directional
    content -- useful, but a long-only alert system would be the wrong thing to
    build on it.

TEST 3 -- PER-QUARTER STABILITY
    The headline edge was an average across six quarters. Study 4 and the
    multi-period test both died because an average concealed a reversal.

    Only the PRE-REGISTERED configurations below are tested, and the pass
    threshold is fixed before running. Sweeping again and picking a new winner
    is precisely what broke the previous two findings.

    python research/phase2_metric_search/volume_validation.py
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
MOVE_WINDOW = 10

# ===========================================================================
# PRE-REGISTRATION -- set before running, do not change after seeing results
# ===========================================================================

PREREGISTERED = [
    (10, 30, 1.75),      # best edge in the sweep
    (10, 20, 1.50),      # runner-up (affected by the overlap problem)
]

# A configuration passes only if BOTH hold:
MIN_POSITIVE_QUARTERS = 5     # positive edge in at least this many of 6
WORST_QUARTER_ABOVE = 0.0     # and the worst quarter still above this

# ===========================================================================

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
        out["dollar_volume"] = df["Close"] * df["Volume"]
        out["fwd_move"] = df["Close"].shift(-MOVE_WINDOW) / df["Close"] - 1
        frames[t] = out
    return frames


def add_ratio(df, recent_n, base_n, overlapping=False):
    """
    Volume ratio, with the baseline either including or excluding the recent
    window.

    Overlapping (the sweep's definition) caps the ratio at base_n / recent_n,
    so a 10/20 pair can never exceed 2.0 regardless of how large the spike is.
    Non-overlapping removes that ceiling and makes every window pair comparable.
    """
    dv = df["dollar_volume"]
    recent = dv.rolling(recent_n).mean()
    if overlapping:
        base = dv.rolling(base_n).mean()
    else:
        base = dv.shift(recent_n).rolling(base_n).mean()
    return recent / base


# ---------------------------------------------------------------------------
# Core evaluation -- both sides
# ---------------------------------------------------------------------------

def collect(frames, recent_n, base_n, trigger, periods, overlapping=False):
    """
    Returns counts of (fired, outcome) across the given periods.

    Outcomes: rise (>= +10%), fall (<= -10%), flat (neither).
    """
    fired_rise = fired_fall = fired_flat = 0
    n_rise = n_fall = n_flat = 0

    for _, df in frames.items():
        ratio = add_ratio(df, recent_n, base_n, overlapping)

        for _, start, end in periods:
            window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
            if window.empty:
                continue
            r = ratio.loc[window.index]
            fwd = window["fwd_move"]
            valid = r.notna() & fwd.notna()
            if not valid.any():
                continue

            fires = r[valid] >= trigger
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

    return dict(fired_rise=fired_rise, fired_fall=fired_fall,
                fired_flat=fired_flat, n_rise=n_rise, n_fall=n_fall,
                n_flat=n_flat)


def metrics(c):
    """Both-sided precision, base rates and the conditional direction test."""
    total = c["n_rise"] + c["n_fall"] + c["n_flat"]
    fired = c["fired_rise"] + c["fired_fall"] + c["fired_flat"]
    if total == 0 or fired == 0:
        return None

    rise_prec = c["fired_rise"] / fired * 100
    rise_base = c["n_rise"] / total * 100
    fall_prec = c["fired_fall"] / fired * 100
    fall_base = c["n_fall"] / total * 100

    # Conditional on a big move happening either way, what share were rises?
    fired_moves = c["fired_rise"] + c["fired_fall"]
    all_moves = c["n_rise"] + c["n_fall"]
    cond_fired = (c["fired_rise"] / fired_moves * 100) if fired_moves else np.nan
    cond_all = (c["n_rise"] / all_moves * 100) if all_moves else np.nan

    return {
        "n_fired": fired,
        "fire_rate_pct": round(fired / total * 100, 2),
        "rise_prec_pct": round(rise_prec, 2),
        "rise_base_pct": round(rise_base, 2),
        "rise_edge_pp": round(rise_prec - rise_base, 2),
        "fall_prec_pct": round(fall_prec, 2),
        "fall_base_pct": round(fall_base, 2),
        "fall_edge_pp": round(fall_prec - fall_base, 2),
        "cond_rise_share_pct": round(cond_fired, 2) if pd.notna(cond_fired) else None,
        "cond_base_share_pct": round(cond_all, 2) if pd.notna(cond_all) else None,
        "direction_edge_pp": (round(cond_fired - cond_all, 2)
                              if pd.notna(cond_fired) and pd.notna(cond_all)
                              else None),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    frames = load_frames()
    print(f"\nUsable: {len(frames)} tickers")
    print(f"Pre-registered configs: {PREREGISTERED}")
    print(f"Pass = positive edge in >= {MIN_POSITIVE_QUARTERS}/6 quarters "
          f"AND worst quarter > {WORST_QUARTER_ABOVE}\n")

    # ==================================================================
    # TEST 1
    # ==================================================================
    print("=" * 92)
    print("TEST 1 -- HOW MUCH DID THE WINDOW OVERLAP MATTER?")
    print("=" * 92 + "\n")

    rows = []
    for recent_n, base_n, trigger in PREREGISTERED:
        for overlapping in (True, False):
            m = metrics(collect(frames, recent_n, base_n, trigger,
                                PERIODS, overlapping))
            if m:
                rows.append({
                    "config": f"{recent_n}/{base_n} @ {trigger}",
                    "baseline": "overlapping" if overlapping else "separate",
                    "ceiling": (round(base_n / recent_n, 2)
                                if overlapping else "none"),
                    "n_fired": m["n_fired"],
                    "fire_rate_pct": m["fire_rate_pct"],
                    "rise_edge_pp": m["rise_edge_pp"],
                })
    print(pd.DataFrame(rows).to_string(index=False))
    print("""
  With an overlapping baseline the ratio cannot exceed base_n / recent_n.
  If n_fired changes sharply between the two rows of a config, the sweep's
  result for that pair was partly an artefact of the ceiling.

  Everything below uses the SEPARATE baseline.""")

    # ==================================================================
    # TEST 2
    # ==================================================================
    print("\n" + "=" * 92)
    print("TEST 2 -- DIRECTION: DOES IT PREDICT WHICH WAY, OR JUST THAT "
          "SOMETHING HAPPENS?")
    print("=" * 92 + "\n")

    rows = []
    for recent_n, base_n, trigger in PREREGISTERED:
        m = metrics(collect(frames, recent_n, base_n, trigger, PERIODS))
        if m:
            rows.append({"config": f"{recent_n}/{base_n} @ {trigger}", **m})

    d = pd.DataFrame(rows)
    print(d[["config", "n_fired", "fire_rate_pct",
             "rise_prec_pct", "rise_base_pct", "rise_edge_pp",
             "fall_prec_pct", "fall_base_pct", "fall_edge_pp"]]
          .to_string(index=False))

    print("\n  Conditional on a 10% move happening, what share were rises?\n")
    print(d[["config", "cond_rise_share_pct", "cond_base_share_pct",
             "direction_edge_pp"]].to_string(index=False))

    print("""
  cond_rise_share_pct: of the big moves the metric FIRED before, what share
                       were rises?
  cond_base_share_pct: of ALL big moves, what share were rises?
  direction_edge_pp:   the difference -- the only number that measures
                       DIRECTIONAL content.

  If rise_edge_pp is strongly positive but direction_edge_pp is near zero, the
  metric detects that a move is coming without predicting its sign. That is a
  volatility signal, and a long-only alert built on it would be firing equally
  before crashes.""")

    # ==================================================================
    # TEST 3
    # ==================================================================
    print("\n" + "=" * 92)
    print("TEST 3 -- PER-QUARTER STABILITY (pre-registered configs only)")
    print("=" * 92)

    verdicts = []
    for recent_n, base_n, trigger in PREREGISTERED:
        label = f"{recent_n}/{base_n} @ {trigger}"
        print(f"\n  {label}\n  " + "-" * 60)

        per_q = []
        for name, start, end in PERIODS:
            m = metrics(collect(frames, recent_n, base_n, trigger,
                                [(name, start, end)]))
            per_q.append({
                "quarter": name,
                "n_fired": m["n_fired"] if m else 0,
                "rise_edge_pp": m["rise_edge_pp"] if m else np.nan,
                "direction_edge_pp": m["direction_edge_pp"] if m else np.nan,
            })

        q = pd.DataFrame(per_q)
        print(q.to_string(index=False))

        edges = q["rise_edge_pp"].dropna()
        n_pos = int((edges > 0).sum())
        worst = edges.min() if len(edges) else np.nan
        passed = (n_pos >= MIN_POSITIVE_QUARTERS
                  and worst > WORST_QUARTER_ABOVE)

        print(f"\n    Positive quarters: {n_pos}/{len(edges)} "
              f"(need >= {MIN_POSITIVE_QUARTERS})")
        print(f"    Worst quarter:     {worst:+.2f} pp "
              f"(need > {WORST_QUARTER_ABOVE})")
        print(f"    -> {'PASS' if passed else 'FAIL'}")

        verdicts.append({"config": label, "positive_quarters": n_pos,
                         "worst_quarter_pp": round(float(worst), 2),
                         "passed": passed})
        q.insert(0, "config", label)
        q.to_csv(f"{RESULTS_DIR}/volume_stability_"
                 f"{recent_n}_{base_n}_{trigger}.csv", index=False)

    # ==================================================================
    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92 + "\n")
    v = pd.DataFrame(verdicts)
    print(v.to_string(index=False))

    d.to_csv(f"{RESULTS_DIR}/volume_direction.csv", index=False)
    v.to_csv(f"{RESULTS_DIR}/volume_stability_verdict.csv", index=False)

    if not v["passed"].any():
        print("""
  -> Neither pre-registered configuration passed.

     The sweep's headline edge was an average that concealed quarters where the
     effect was absent or reversed. That is the third finding withdrawn on the
     same failure mode, after the persistence effect and the eight metrics.

     Do not sweep again and pick a new winner. That is the move that produced
     the previous two.""")
    else:
        print("""
  -> At least one configuration passed the pre-registered threshold.

     Before any config change, check TEST 2. A strong rise_edge_pp with a
     direction_edge_pp near zero means the metric flags volatility, not
     direction, and a long-only screener is the wrong product for it.

     Note also that the pass threshold was set on the same six quarters used
     to select these configurations. Genuine confirmation still requires
     out-of-sample data -- which the daily snapshot archive is collecting.""")

    print(f"\n\nWritten to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()