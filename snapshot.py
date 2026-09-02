"""
Daily metric snapshot collector.

Purpose: build an out-of-sample dataset.

Every study in this project was run on data that had already been examined. The
metrics were chosen after seeing the results, which is why two findings looked
robust and then collapsed. The only clean test is data no analysis has seen --
and that data does not exist yet. It has to be collected going forward.

This runs alongside the screener and archives, once per trading day, ALL 31
metrics for ALL tickers in the universe. Not just matches. The non-matching
tickers are the control group, and their absence is what made the original
"look at the winners" framing unanswerable.

Nothing here is displayed. The screener's behaviour and emails are unchanged.
The output is written to data/snapshots/ and committed so it survives the
ephemeral runner.

Why record rather than recompute later
--------------------------------------
Prices could be re-downloaded in a year and the metrics recalculated, so why
store them?

  1. yfinance revises history. Splits, dividends and corrections change past
     values. A snapshot taken today records what was actually knowable today;
     a recomputation records what the provider currently believes.
  2. Tickers vanish. Companies delisted or acquired return no data afterwards,
     which is precisely the survivorship bias documented throughout this
     project. A stored snapshot keeps them.
  3. It removes any possibility of lookahead in the metric values themselves.

Storage: ~178 rows x ~35 columns per day, gzipped, roughly 30-50 KB. Under
15 MB per year.

    python snapshot.py          # standalone
    (or called from screener.py after the run completes)
"""

import csv
import gzip
import os
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

import config

warnings.filterwarnings("ignore")

SNAPSHOT_DIR = "data/snapshots"
UNIVERSE_FILE = "data/tickers_universe.csv"   # the 178, not the live 60
HISTORY_PERIOD = "2y"                          # enough for a 252-day lookback
REQUEST_DELAY = 0.0                            # bulk download, no per-ticker delay


# ---------------------------------------------------------------------------
# Metric library
#
# Deliberately duplicated from research/phase2_metric_search/metric_search.py
# rather than imported. The research scripts are free to change as analysis
# evolves; this archive must stay stable, because a column that changes meaning
# halfway through a year of snapshots is worse than no column at all.
# ---------------------------------------------------------------------------

def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def rolling_r2(series, window):
    x = np.arange(window)
    xm = x - x.mean()
    denom = (xm ** 2).sum()

    def fit(y):
        ym = y - y.mean()
        slope = (xm * ym).sum() / denom
        ss_res = ((ym - slope * xm) ** 2).sum()
        ss_tot = (ym ** 2).sum()
        return 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    return series.rolling(window).apply(fit, raw=True)


def compute_metrics(data, ticker):
    """All 31 metrics, rolling, using only data up to each row."""
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
    m["volume"] = v

    # Volume and liquidity
    m["vol_ratio_10_63"] = dv.rolling(10).mean() / dv.rolling(63).mean()
    m["vol_ratio_5_21"] = dv.rolling(5).mean() / dv.rolling(21).mean()
    m["vol_ratio_21_126"] = dv.rolling(21).mean() / dv.rolling(126).mean()
    m["dollar_vol_musd"] = dv.rolling(10).mean() / 1e6
    m["share_vol_ratio"] = v.rolling(10).mean() / v.rolling(63).mean()

    up_dv = dv.where(ret > 0, 0)
    m["up_volume_share"] = (up_dv.rolling(21).sum()
                            / dv.rolling(21).sum().replace(0, np.nan))

    obv = (np.sign(ret).fillna(0) * v).cumsum()
    m["obv_slope_21"] = obv.diff(21) / dv.rolling(21).mean().replace(0, np.nan)

    rng = (h - l).replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / rng
    ad = (mfm.fillna(0) * v).cumsum()
    m["ad_slope_21"] = ad.diff(21) / v.rolling(21).mean().replace(0, np.nan)

    # Momentum
    for n in (5, 10, 21, 63, 126):
        m[f"return_{n}d_pct"] = c.pct_change(n) * 100
    m["momentum_accel"] = (c.pct_change(10) - c.pct_change(21)) * 100

    # Position in range
    m["pct_off_52w_high"] = (c / c.rolling(252, min_periods=60).max() - 1) * 100
    m["pct_above_52w_low"] = (c / c.rolling(252, min_periods=60).min() - 1) * 100
    m["pct_vs_ma50"] = (c / c.rolling(50).mean() - 1) * 100
    m["pct_vs_ma200"] = (c / c.rolling(200).mean() - 1) * 100
    m["ma50_vs_ma200"] = (c.rolling(50).mean() / c.rolling(200).mean() - 1) * 100
    m["close_in_21d_range"] = ((c - l.rolling(21).min())
                               / (h.rolling(21).max()
                                  - l.rolling(21).min()).replace(0, np.nan))

    # Volatility
    m["volatility_20d_pct"] = ret.rolling(20).std() * np.sqrt(252) * 100
    m["volatility_60d_pct"] = ret.rolling(60).std() * np.sqrt(252) * 100
    m["vol_of_vol"] = (ret.rolling(20).std()
                       / ret.rolling(60).std().replace(0, np.nan))
    tr = pd.concat([h - l, (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    m["atr_pct"] = tr.rolling(14).mean() / c * 100
    m["bollinger_width_pct"] = (ret.rolling(20).std() * 4) * 100

    # Shape and trend quality
    m["rsi_14"] = rsi(c)
    m["pct_up_days_21"] = (ret > 0).rolling(21).mean() * 100
    m["max_dd_63d_pct"] = (c / c.rolling(63).max() - 1) * 100
    m["return_skew_63"] = ret.rolling(63).skew()
    m["trend_r2_63"] = rolling_r2(np.log(c), 63)
    m["gap_freq_21"] = (ret.abs() > 0.05).rolling(21).mean() * 100

    return m


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def load_universe():
    with open(UNIVERSE_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def snapshot_path(date):
    return os.path.join(SNAPSHOT_DIR, f"{date}.csv.gz")


def take_snapshot(force=False):
    """
    Fetch the universe, compute all metrics, write the latest row per ticker.

    Returns the path written, or None if skipped.
    """
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    universe = load_universe()
    meta = {r["ticker"]: r for r in universe}
    tickers = [r["ticker"] for r in universe]

    print(f"Snapshot: downloading {len(tickers)} tickers...")
    data = yf.download(tickers, period=HISTORY_PERIOD, interval="1d",
                       auto_adjust=True, group_by="ticker",
                       progress=False, threads=True)

    rows, skipped = [], []
    as_of = None

    for t in tickers:
        m = compute_metrics(data, t)
        if m is None or m.empty:
            skipped.append(t)
            continue

        last_date = m.index[-1]
        if as_of is None:
            as_of = last_date.date().isoformat()

        row = {
            "as_of": last_date.date().isoformat(),
            "ticker": t,
            "category": meta[t].get("category", ""),
            "exchange": meta[t].get("exchange", ""),
            "in_original_60": meta[t].get("in_original", ""),
        }
        row.update({k: (None if pd.isna(val) else float(val))
                    for k, val in m.iloc[-1].items()})
        rows.append(row)

    if not rows:
        print("Snapshot: no usable data, nothing written.")
        return None

    df = pd.DataFrame(rows)

    # File is named for the latest bar, not the run date. A run delayed past
    # midnight UTC would otherwise create a file dated a day after the data it
    # contains -- and scheduled runs here have been observed 10 hours late.
    path = snapshot_path(as_of)

    if os.path.exists(path) and not force:
        print(f"Snapshot: {path} already exists, skipping "
              f"(bar date {as_of} unchanged since last run).")
        return None

    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        df.to_csv(f, index=False)

    size_kb = os.path.getsize(path) / 1024
    print(f"Snapshot: wrote {len(df)} rows to {path} ({size_kb:.0f} KB)")
    if skipped:
        print(f"Snapshot: no data for {len(skipped)} tickers "
              f"({', '.join(skipped[:8])}{'...' if len(skipped) > 8 else ''})")

    return path


# ---------------------------------------------------------------------------
# Reading the archive back, a year from now
# ---------------------------------------------------------------------------

def load_all_snapshots(start=None, end=None):
    """
    Concatenate every snapshot into one long DataFrame.

    Columns: as_of, ticker, category, exchange, in_original_60, then all
    metrics. One row per ticker per trading day.

    Forward returns are NOT stored -- compute them at analysis time from the
    close column, which is exactly what the backtests already do.
    """
    if not os.path.isdir(SNAPSHOT_DIR):
        return pd.DataFrame()

    frames = []
    for fn in sorted(os.listdir(SNAPSHOT_DIR)):
        if not fn.endswith(".csv.gz"):
            continue
        date = fn[:-7]
        if start and date < start:
            continue
        if end and date > end:
            continue
        with gzip.open(os.path.join(SNAPSHOT_DIR, fn), "rt",
                       encoding="utf-8") as f:
            frames.append(pd.read_csv(f))

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["as_of"] = pd.to_datetime(out["as_of"])
    return out.sort_values(["as_of", "ticker"]).reset_index(drop=True)


def archive_summary():
    files = ([f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".csv.gz")]
             if os.path.isdir(SNAPSHOT_DIR) else [])
    if not files:
        print("No snapshots yet.")
        return

    total_kb = sum(os.path.getsize(os.path.join(SNAPSHOT_DIR, f))
                   for f in files) / 1024
    print(f"{len(files)} snapshots, {sorted(files)[0][:-7]} to "
          f"{sorted(files)[-1][:-7]}, {total_kb:.0f} KB total")


if __name__ == "__main__":
    take_snapshot()
    archive_summary()