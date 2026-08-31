"""
Volume timing event study.

Every test so far shows volume does not PREDICT a move. None of them show
whether volume rises DURING one. Those are different claims, and the second one
is the objection raised against all the negative results:

    "Volume goes up a couple of days after the first and second day of the
     price wave."

If that is right, then measuring volume before a move correctly shows nothing,
and volume is a CONFIRMATION signal rather than an ENTRY signal. That would
explain every negative finding in this project without volume being meaningless.

It would also mean the live screener is structurally wrong rather than badly
tuned: it waits for a volume surge before alerting, so it would necessarily
alert after the move has already begun.

Method
------
Find every case where a stock began a 10%+ move. Anchor day 0 at the start.
Then average relative volume across all such events, from 20 trading days
before through 20 days after.

Relative volume is each day's dollar volume divided by that ticker's average
daily dollar volume over a FIXED pre-event window (days -83 to -21). Using a
fixed baseline rather than a rolling one matters: a trailing average would
blend pre- and post-event days together and blur exactly the timing this study
is trying to measure.

Two controls:

    down-moves    the same curve for stocks that FELL 10%. If volume rises
                  around both, it responds to movement, not direction.
    random days   randomly chosen dates with no move. Should be flat at 1.0.
                  If it is not, the measurement itself is biased.

    python research/phase2_metric_search/volume_event_study.py
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

import config

warnings.filterwarnings("ignore")

RESULTS_DIR = "results/phase2"
CACHE_PATH = "cache/universe178_history.pkl"
UNIVERSE_FILE = "data/tickers_universe.csv"

MOVE_THRESHOLD = 0.10      # what counts as a "move"
MOVE_WINDOW = 10           # over this many trading days
WINDOW_BEFORE = 20         # days charted before the move starts
WINDOW_AFTER = 20          # days charted after
# Fixed baseline window, relative to day 0.
# Originally -83 to -21, which sat 3-4 months before the event. Sector volume
# grew steadily over 2023-2026, so that distant baseline made EVERY window look
# elevated -- the random-day control came out at 1.35 instead of 1.0, meaning
# the measurement was picking up the growth trend rather than the events.
# A closer window reduces that contamination. Watch the random control: if it
# is not near 1.0, the absolute numbers cannot be read at face value and every
# curve must be compared against the control instead.
BASELINE_START = -40
BASELINE_END = -21
EVENT_GAP = 30             # min trading days between events for one ticker
N_RANDOM_PER_TICKER = 3


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_history():
    with open(UNIVERSE_FILE, newline="", encoding="utf-8") as f:
        tickers = [r["ticker"] for r in csv.DictReader(f)]

    if os.path.exists(CACHE_PATH):
        print(f"Loading cached history from {CACHE_PATH}")
        return pd.read_pickle(CACHE_PATH), tickers

    print(f"Downloading history for {len(tickers)} tickers...")
    data = yf.download(tickers, start="2023-06-01", interval="1d",
                       auto_adjust=True, group_by="ticker",
                       progress=True, threads=True)
    data.to_pickle(CACHE_PATH)
    return data, tickers


def prepare(data, ticker):
    try:
        df = data[ticker][["Close", "Volume"]].dropna()
    except (KeyError, TypeError):
        return None
    if len(df) < 200:
        return None

    out = pd.DataFrame(index=df.index)
    out["close"] = df["Close"]
    out["dollar_volume"] = df["Close"] * df["Volume"]
    # The screener's own metric, kept for comparison
    out["vol_ratio_10_63"] = (out["dollar_volume"].rolling(10).mean()
                              / out["dollar_volume"].rolling(63).mean())
    out["fwd_move"] = df["Close"].shift(-MOVE_WINDOW) / df["Close"] - 1
    return out


# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------

def find_events(df, direction="up"):
    """
    Day 0 is the first day of a window over which the stock moved 10%+.

    Events are spaced at least EVENT_GAP apart so one long run does not
    contribute twenty overlapping events that all describe the same episode.
    """
    if direction == "up":
        mask = df["fwd_move"] >= MOVE_THRESHOLD
    else:
        mask = df["fwd_move"] <= -MOVE_THRESHOLD

    candidates = np.where(mask.fillna(False).values)[0]
    if len(candidates) == 0:
        return []

    kept = [candidates[0]]
    for i in candidates[1:]:
        if i - kept[-1] >= EVENT_GAP:
            kept.append(i)

    lo = -BASELINE_START
    hi = WINDOW_AFTER + MOVE_WINDOW
    return [i for i in kept if i >= lo and i + hi < len(df)]


def random_days(df, n, rng):
    lo = -BASELINE_START
    hi = WINDOW_AFTER + MOVE_WINDOW
    if len(df) - hi <= lo:
        return []
    return list(rng.integers(lo, len(df) - hi, size=n))


def extract_curve(df, idx):
    """
    Relative volume from day -20 to +20, normalised by a FIXED pre-event
    baseline. Returns None if the baseline is unusable.
    """
    dv = df["dollar_volume"].values

    base = dv[idx + BASELINE_START: idx + BASELINE_END]
    base_mean = np.nanmean(base)
    if not np.isfinite(base_mean) or base_mean <= 0:
        return None, None

    window = dv[idx - WINDOW_BEFORE: idx + WINDOW_AFTER + 1]
    if len(window) != WINDOW_BEFORE + WINDOW_AFTER + 1:
        return None, None

    rel = window / base_mean

    # The screener's rolling metric over the same span, for comparison
    sr = df["vol_ratio_10_63"].values[
        idx - WINDOW_BEFORE: idx + WINDOW_AFTER + 1]

    return rel, sr


def build_event_curves(frames, direction, rng=None, random_mode=False):
    curves, screener_curves, n_events = [], [], 0

    for ticker, df in frames.items():
        if random_mode:
            idxs = random_days(df, N_RANDOM_PER_TICKER, rng)
        else:
            idxs = find_events(df, direction)

        for idx in idxs:
            rel, sr = extract_curve(df, idx)
            if rel is None:
                continue
            curves.append(rel)
            screener_curves.append(sr)
            n_events += 1

    if not curves:
        return None, None, 0

    return (np.nanmean(np.vstack(curves), axis=0),
            np.nanmean(np.vstack(screener_curves), axis=0),
            n_events)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def sparkline(values, lo=None, hi=None, height=9):
    """Rough ASCII chart so the shape is visible in the terminal."""
    blocks = " .:-=+*#%@"
    lo = np.nanmin(values) if lo is None else lo
    hi = np.nanmax(values) if hi is None else hi
    if hi <= lo:
        return " " * len(values)
    scaled = np.clip((values - lo) / (hi - lo), 0, 1)
    return "".join(blocks[int(s * (len(blocks) - 1))] for s in scaled)


def summarise(curve, label):
    """Average relative volume before, at, and after day 0."""
    zero = WINDOW_BEFORE
    before = np.nanmean(curve[zero - 10: zero])       # days -10 to -1
    at = np.nanmean(curve[zero: zero + 3])            # days 0 to +2
    after = np.nanmean(curve[zero + 3: zero + 13])    # days +3 to +12

    print(f"\n  {label}")
    print(f"    Days -10 to -1 (before): {before:.2f}x baseline")
    print(f"    Days  0 to +2  (start):  {at:.2f}x baseline")
    print(f"    Days +3 to +12 (after):  {after:.2f}x baseline")
    print(f"    Rise from before to after: {(after / before - 1) * 100:+.1f}%")

    return before, at, after


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    rng = np.random.default_rng(42)

    data, tickers = load_history()

    frames = {}
    for t in tickers:
        f = prepare(data, t)
        if f is not None:
            frames[t] = f
    print(f"\nUsable: {len(frames)} tickers")

    up_curve, up_screener, n_up = build_event_curves(frames, "up")
    down_curve, _, n_down = build_event_curves(frames, "down")
    rand_curve, _, n_rand = build_event_curves(
        frames, None, rng=rng, random_mode=True)

    if up_curve is None:
        print("No events found.")
        return

    days = np.arange(-WINDOW_BEFORE, WINDOW_AFTER + 1)

    print(f"\nEvents found: {n_up} up-moves, {n_down} down-moves, "
          f"{n_rand} random days")

    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"RELATIVE DOLLAR VOLUME AROUND A {MOVE_THRESHOLD:.0%} MOVE")
    print("=" * 78)
    print("\nDay 0 = first day of the move. Values are multiples of the "
          "stock's own\npre-event average (days -83 to -21).\n")

    table = pd.DataFrame({
        "day": days,
        "up_moves": np.round(up_curve, 3),
        "down_moves": np.round(down_curve, 3) if down_curve is not None else np.nan,
        "random_days": np.round(rand_curve, 3) if rand_curve is not None else np.nan,
    })
    print(table.to_string(index=False))

    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("SHAPE")
    print("=" * 78)

    lo = min(np.nanmin(up_curve), np.nanmin(rand_curve))
    hi = max(np.nanmax(up_curve), np.nanmax(rand_curve))

    marker = " " * WINDOW_BEFORE + "0"
    print(f"\n  day -20 {' ' * (WINDOW_BEFORE - 8)}day 0"
          f"{' ' * (WINDOW_AFTER - 6)}day +20")
    print(f"  up      |{sparkline(up_curve, lo, hi)}|")
    if down_curve is not None:
        print(f"  down    |{sparkline(down_curve, lo, hi)}|")
    if rand_curve is not None:
        print(f"  random  |{sparkline(rand_curve, lo, hi)}|")
    print(f"           {marker}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("BEFORE VS AFTER")
    print("=" * 78)

    ub, ua, uaf = summarise(up_curve, "UP-MOVES (10%+ gain)")
    if down_curve is not None:
        db, da, daf = summarise(down_curve, "DOWN-MOVES (10%+ loss) -- control")
    if rand_curve is not None:
        rb, ra, raf = summarise(rand_curve,
                                "RANDOM DAYS -- control, should be flat at 1.0")

        drift = abs(rb - 1.0)
        if drift > 0.10:
            print(f"""
  WARNING: the random-day control reads {rb:.2f}x, not 1.0.
  The baseline is contaminated -- most likely by sector-wide volume growth over
  the period. Absolute values above are inflated for every curve. Read the
  net-of-control figures below instead.""")

        print("\n" + "-" * 74)
        print("  NET OF THE RANDOM-DAY CONTROL (this is the honest comparison)")
        print("-" * 74)
        print(f"    {'':<22}{'before':>10}{'start':>10}{'after':>10}")
        print(f"    {'up-moves':<22}{ub - rb:>+10.2f}{ua - ra:>+10.2f}"
              f"{uaf - raf:>+10.2f}")
        if down_curve is not None:
            print(f"    {'down-moves':<22}{db - rb:>+10.2f}{da - ra:>+10.2f}"
                  f"{daf - raf:>+10.2f}")

        if down_curve is not None and (db - rb) > (ub - rb):
            print("""
    Note: volume before DOWN-moves exceeds volume before UP-moves. Elevated
    volume precedes large moves in both directions, and historically more so
    before falls. It signals that something is about to happen, not which way.""")

    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)

    # Measured against the random-day control, not against 1.0, because the
    # control shows the baseline itself is not neutral.
    ctrl_b = rb if rand_curve is not None else 1.0
    ctrl_a = raf if rand_curve is not None else 1.0

    lead = (ub - ctrl_b)              # elevation BEFORE, net of control
    lag = (uaf - ctrl_a) - lead       # additional rise AFTER, net of control

    print(f"\n  All figures net of the random-day control.")
    print(f"  Elevation before the move: {lead:+.2f}x")
    print(f"  Additional rise after:     {lag:+.2f}x")

    if lag > 0.15 and abs(lead) < 0.10:
        print("""
  -> VOLUME LAGS THE PRICE MOVE.

     Volume was normal before the move began and rose only once it was
     underway. This supports the objection: volume is a CONFIRMATION signal,
     not an entry signal.

     Consequence: the live screener requires a volume surge before alerting, so
     it can only fire after a move is already in progress. That is a structural
     problem with the design, not a threshold that needs tuning.""")
    elif lead > 0.10:
        print("""
  -> VOLUME LEADS THE PRICE MOVE.

     Volume was already elevated before the move began. The screener's timing
     is therefore sound, and the negative results elsewhere mean the signal
     simply carries no predictive information -- not that it was measured at
     the wrong moment.""")
    else:
        print("""
  -> NO CLEAR RELATIONSHIP.

     Volume is roughly flat before and after. In this universe volume does not
     appear to track price moves in either direction.""")

    # The screener's own metric, for reference
    zero = WINDOW_BEFORE
    print(f"""
  For reference, the screener's own vol_ratio_10_63 around these events:
    day -10: {up_screener[zero - 10]:.2f}    day 0: {up_screener[zero]:.2f}    """
          f"""day +10: {up_screener[zero + 10]:.2f}
    (This is a 10-day trailing average, so it responds more slowly than the
     daily figures above and blurs the timing. That is why the fixed-baseline
     measure is the primary one here.)""")

    table.to_csv(f"{RESULTS_DIR}/volume_event_study.csv", index=False)
    print(f"\n\nWritten to {RESULTS_DIR}/volume_event_study.csv")

    print("""
CAVEATS

Day 0 is defined as the start of a window over which a 10% move occurred. That
is a reasonable proxy for "when the move began" but not an exact one -- a move
may build gradually rather than starting on a single identifiable day.

The random-day control is the check on the method itself. If that curve is not
close to flat at 1.0, the measurement is picking up something other than the
events, and the up-move curve should not be trusted.
""")


if __name__ == "__main__":
    main()