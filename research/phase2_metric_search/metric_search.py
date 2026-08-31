"""
Study 5 -- broad metric search.

The three screening conditions are known not to work. This searches much wider:
roughly 30 metrics spanning volume, momentum, volatility, trend quality and
accumulation, asking which ones actually separated stocks that went on to rise
10% from those that did not.

Two controls are built in, because a wide search without them is a machine for
manufacturing false positives.

CONTROL 1 -- THE MIRROR TEST
    Every metric is also evaluated against stocks that FELL 10%. A metric that
    separates winners from the field should NOT separate losers equally well.
    If it does, it predicts how far a stock moves, not which direction, and is
    useless as a buy signal. This is what likely explains the volatility result
    in the earlier study.

CONTROL 2 -- THE PERMUTATION TEST
    Winner labels are shuffled at random and the entire search is re-run, many
    times. That measures how many metrics clear the bar by chance alone. If
    random labels yield as many hits as the real ones, the search found nothing
    -- regardless of how convincing any individual metric looks.

    python research/phase2_metric_search/metric_search.py
"""

import os
import sys

# Scripts live in research/<phase>/ but import config.py from the repo root.
# Walk up until we find it, then run from there so relative paths resolve.
ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(ROOT, "config.py")):
    ROOT = os.path.dirname(ROOT)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import csv
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

RESULTS_DIR = "results/phase2"
CACHE_PATH = "cache/universe178_history.pkl"
UNIVERSE_FILE = "data/tickers_universe.csv"

MOVE_THRESHOLD = 0.10
SEPARATION_BAR = 0.30        # minimum |SD| to count as meaningful
N_PERMUTATIONS = 500

PERIODS = [
    ("Sep-Nov 2024", "2024-09-01", "2024-11-30"),
    ("Sep-Nov 2025", "2025-09-01", "2025-11-30"),
]


# ---------------------------------------------------------------------------
# Metric library
# ---------------------------------------------------------------------------

def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def rolling_r2(series, window):
    """
    How straight the price path has been. High R-squared means a smooth trend;
    low means the same net move happened chaotically.
    """
    x = np.arange(window)
    xm = x - x.mean()
    denom = (xm ** 2).sum()

    def fit(y):
        ym = y - y.mean()
        slope = (xm * ym).sum() / denom
        pred = slope * xm
        ss_res = ((ym - pred) ** 2).sum()
        ss_tot = (ym ** 2).sum()
        return 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    return series.rolling(window).apply(fit, raw=True)


def compute_all_metrics(data, ticker):
    """Every candidate metric, computed rolling so nothing looks ahead."""
    try:
        df = data[ticker][["Close", "Volume", "High", "Low"]].dropna()
    except (KeyError, TypeError):
        try:
            df = data[ticker][["Close", "Volume"]].dropna()
            df["High"] = df["Close"]
            df["Low"] = df["Close"]
        except (KeyError, TypeError):
            return None
    if len(df) < 260:
        return None

    c, v, h, l = df["Close"], df["Volume"], df["High"], df["Low"]
    dv = c * v
    ret = c.pct_change()
    m = pd.DataFrame(index=df.index)
    m["close"] = c

    # --- volume and liquidity ---
    m["vol_ratio_10_63"] = dv.rolling(10).mean() / dv.rolling(63).mean()
    m["vol_ratio_5_21"] = dv.rolling(5).mean() / dv.rolling(21).mean()
    m["vol_ratio_21_126"] = dv.rolling(21).mean() / dv.rolling(126).mean()
    m["dollar_vol_musd"] = dv.rolling(10).mean() / 1e6
    m["share_vol_ratio"] = v.rolling(10).mean() / v.rolling(63).mean()

    # Share of recent dollar volume occurring on up days. Above 0.5 suggests
    # buyers were the more aggressive side.
    up_dv = dv.where(ret > 0, 0)
    m["up_volume_share"] = (up_dv.rolling(21).sum()
                            / dv.rolling(21).sum().replace(0, np.nan))

    # On-balance-volume trend
    obv = (np.sign(ret).fillna(0) * v).cumsum()
    m["obv_slope_21"] = obv.diff(21) / dv.rolling(21).mean().replace(0, np.nan)

    # Accumulation/distribution: where the close sits within each day's range,
    # weighted by volume
    rng = (h - l).replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / rng
    ad = (mfm.fillna(0) * v).cumsum()
    m["ad_slope_21"] = ad.diff(21) / v.rolling(21).mean().replace(0, np.nan)

    # --- momentum ---
    for n in (5, 10, 21, 63, 126):
        m[f"return_{n}d_pct"] = c.pct_change(n) * 100

    m["momentum_accel"] = (c.pct_change(10) - c.pct_change(21)) * 100

    # --- position within range ---
    m["pct_off_52w_high"] = (c / c.rolling(252, min_periods=60).max() - 1) * 100
    m["pct_above_52w_low"] = (c / c.rolling(252, min_periods=60).min() - 1) * 100
    m["pct_vs_ma50"] = (c / c.rolling(50).mean() - 1) * 100
    m["pct_vs_ma200"] = (c / c.rolling(200).mean() - 1) * 100
    m["ma50_vs_ma200"] = (c.rolling(50).mean() / c.rolling(200).mean() - 1) * 100
    m["close_in_21d_range"] = ((c - l.rolling(21).min())
                               / (h.rolling(21).max()
                                  - l.rolling(21).min()).replace(0, np.nan))

    # --- volatility ---
    m["volatility_20d_pct"] = ret.rolling(20).std() * np.sqrt(252) * 100
    m["volatility_60d_pct"] = ret.rolling(60).std() * np.sqrt(252) * 100
    m["vol_of_vol"] = (ret.rolling(20).std()
                       / ret.rolling(60).std().replace(0, np.nan))
    tr = pd.concat([h - l, (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    m["atr_pct"] = tr.rolling(14).mean() / c * 100
    m["bollinger_width_pct"] = (ret.rolling(20).std() * 4) * 100

    # --- shape and trend quality ---
    m["rsi_14"] = rsi(c)
    m["pct_up_days_21"] = (ret > 0).rolling(21).mean() * 100
    m["max_dd_63d_pct"] = (c / c.rolling(63).max() - 1) * 100
    m["return_skew_63"] = ret.rolling(63).skew()
    m["trend_r2_63"] = rolling_r2(np.log(c), 63)
    m["gap_freq_21"] = (ret.abs() > 0.05).rolling(21).mean() * 100

    return m


METRIC_COLS = None   # populated at runtime


# ---------------------------------------------------------------------------
# Period snapshots
# ---------------------------------------------------------------------------

def snapshot(frames, label, start, end):
    """Metrics on the period's first day, plus the period's realised return."""
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    rows = []

    for ticker, df in frames.items():
        window = df.loc[start_ts:end_ts]
        if len(window) < 20:
            continue
        entry = window.iloc[0]
        period_return = window["close"].iloc[-1] / entry["close"] - 1

        row = {"period": label, "ticker": ticker,
               "period_return_pct": round(period_return * 100, 2),
               "rose": period_return >= MOVE_THRESHOLD,
               "fell": period_return <= -MOVE_THRESHOLD}
        for col in METRIC_COLS:
            row[col] = entry.get(col, np.nan)
        rows.append(row)

    return pd.DataFrame(rows)


def separations(df, label_col):
    """Standardised difference between the labelled group and everyone else."""
    grp = df[df[label_col]]
    rest = df[~df[label_col]]
    if len(grp) < 8 or len(rest) < 8:
        return None

    out = {}
    for col in METRIC_COLS:
        a, b = grp[col].dropna(), rest[col].dropna()
        if len(a) < 8 or len(b) < 8:
            out[col] = np.nan
            continue
        pooled = np.sqrt((a.var() + b.var()) / 2)
        out[col] = (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0
    return pd.Series(out)


# ---------------------------------------------------------------------------
# Permutation control
# ---------------------------------------------------------------------------

def permutation_hits(snapshots, n_perm=N_PERMUTATIONS, seed=42):
    """
    Shuffle the winner labels and count how many metrics pass the same
    screening criteria. This is the honest yardstick: a real result must beat
    what random labels produce.
    """
    rng = np.random.default_rng(seed)
    counts = []

    for _ in range(n_perm):
        seps = []
        ok = True
        for snap in snapshots:
            shuffled = snap.copy()
            shuffled["rose"] = rng.permutation(shuffled["rose"].values)
            s = separations(shuffled, "rose")
            if s is None:
                ok = False
                break
            seps.append(s)
        if not ok:
            continue

        combined = pd.concat(seps, axis=1)
        passes = (
            (combined.abs() >= SEPARATION_BAR).all(axis=1)
            & (np.sign(combined).nunique(axis=1) == 1)
        )
        counts.append(int(passes.sum()))

    return np.array(counts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global METRIC_COLS
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(UNIVERSE_FILE, newline="", encoding="utf-8") as f:
        tickers = [r["ticker"] for r in csv.DictReader(f)]

    if os.path.exists(CACHE_PATH):
        print(f"Loading cached history from {CACHE_PATH}")
        data = pd.read_pickle(CACHE_PATH)
    else:
        print(f"Downloading history for {len(tickers)} tickers...")
        data = yf.download(tickers, start="2023-06-01", interval="1d",
                           auto_adjust=True, group_by="ticker",
                           progress=True, threads=True)
        data.to_pickle(CACHE_PATH)

    frames = {}
    for t in tickers:
        m = compute_all_metrics(data, t)
        if m is not None:
            frames[t] = m

    METRIC_COLS = [c for c in next(iter(frames.values())).columns
                   if c != "close"]

    print(f"\nUsable: {len(frames)} tickers")
    print(f"Metrics under test: {len(METRIC_COLS)}")

    snapshots, up_seps, down_seps = [], [], []

    for label, start, end in PERIODS:
        snap = snapshot(frames, label, start, end)
        if snap.empty:
            continue
        snapshots.append(snap)

        n_up, n_down = int(snap["rose"].sum()), int(snap["fell"].sum())
        print(f"\n{label}: {len(snap)} tickers, "
              f"{n_up} rose {MOVE_THRESHOLD:.0%}+, "
              f"{n_down} fell {MOVE_THRESHOLD:.0%}+")

        up_seps.append(separations(snap, "rose"))
        d = separations(snap, "fell")
        down_seps.append(d if d is not None else pd.Series(dtype=float))

    if len(up_seps) < 2:
        print("Need two usable periods.")
        return

    up = pd.concat(up_seps, axis=1)
    up.columns = [p[0] for p in PERIODS]

    # ------------------------------------------------------------------
    # Ranked results
    # ------------------------------------------------------------------
    table = up.copy()
    table["consistent"] = (np.sign(table.iloc[:, 0])
                           == np.sign(table.iloc[:, 1]))
    table["min_abs"] = table.iloc[:, :2].abs().min(axis=1)
    table["passes"] = table["consistent"] & (table["min_abs"] >= SEPARATION_BAR)

    ranked = table.sort_values("min_abs", ascending=False)

    print("\n" + "=" * 84)
    print(f"ALL {len(METRIC_COLS)} METRICS -- separation of stocks that rose "
          f"{MOVE_THRESHOLD:.0%}+ (in SD)")
    print("=" * 84 + "\n")
    print(ranked.round(2).to_string())

    hits = ranked[ranked["passes"]]

    print("\n" + "=" * 84)
    print(f"METRICS PASSING BOTH PERIODS AT >= {SEPARATION_BAR} SD, "
          f"SAME DIRECTION: {len(hits)}")
    print("=" * 84)
    if len(hits):
        print("\n" + hits.round(2).to_string())
    else:
        print("\nNone.")

    # ------------------------------------------------------------------
    # Mirror test
    # ------------------------------------------------------------------
    if len(hits) and all(len(d) for d in down_seps):
        down = pd.concat(down_seps, axis=1)
        down.columns = [p[0] for p in PERIODS]

        print("\n" + "=" * 84)
        print("MIRROR TEST -- do these also separate stocks that FELL 10%?")
        print("=" * 84 + "\n")

        rows = []
        for metric in hits.index:
            u = hits.loc[metric, [p[0] for p in PERIODS]].mean()
            d = down.loc[metric].mean() if metric in down.index else np.nan
            rows.append({
                "metric": metric,
                "sep_for_risers": round(u, 2),
                "sep_for_fallers": round(d, 2),
                "same_sign": bool(np.sign(u) == np.sign(d)),
                "verdict": ("MAGNITUDE not direction"
                            if np.sign(u) == np.sign(d) and abs(d) >= 0.2
                            else "directional"),
            })
        print(pd.DataFrame(rows).to_string(index=False))
        print("""
A metric flagged MAGNITUDE separates risers AND fallers in the same direction.
It identifies stocks that move a lot, not stocks that move up. Useless as a
buy signal.
""")

    # ------------------------------------------------------------------
    # Permutation control
    # ------------------------------------------------------------------
    print("\n" + "=" * 84)
    print(f"PERMUTATION CONTROL -- {N_PERMUTATIONS} runs with shuffled labels")
    print("=" * 84)

    null = permutation_hits(snapshots)
    if len(null):
        print(f"\n  Real search found:              {len(hits)} metric(s)")
        print(f"  Random labels find on average:  {null.mean():.2f} metric(s)")
        print(f"  95th percentile of random:      {np.percentile(null, 95):.0f}")
        p = (null >= len(hits)).mean()
        print(f"  Chance of {len(hits)}+ hits by luck alone: {p * 100:.1f}%")

        if p > 0.05:
            print("\n  -> This result is consistent with chance. A search over "
                  f"{len(METRIC_COLS)}\n     metrics finds this many hits "
                  "routinely with random labels.")
        else:
            print("\n  -> More hits than random labels typically produce. "
                  "Worth\n     following up -- but see the caveats below.")

    ranked.round(3).to_csv(f"{RESULTS_DIR}/metric_search.csv")
    print(f"\n\nWritten to {RESULTS_DIR}/metric_search.csv")

    print(f"""
WHAT THIS CAN AND CANNOT SHOW

{len(METRIC_COLS)} metrics were tested across 2 periods. With that many
comparisons, some will separate impressively by chance -- which is exactly what
the permutation control measures. Judge any hit against the random baseline,
not against zero.

Surviving both controls still makes a metric a HYPOTHESIS. Two periods is two
observations, both drawn from the same sector during the same buildout. They
are not independent samples of market behaviour.

Confirming anything found here needs the treatment already applied to the
original signal: out-of-sample data, a neutrally-selected universe, and a
clustered significance test. Study 4 showed what happens when a pattern is
believed before that work is done.
""")


if __name__ == "__main__":
    main()