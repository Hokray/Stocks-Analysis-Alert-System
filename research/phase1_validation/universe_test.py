"""
Universe bias test.

Every result so far was produced on 60 tickers hand-picked in 2026 because they
are the recognisable names in AI infrastructure. Those companies are prominent
BECAUSE they did well over 2023-2026 -- the same period the backtest covers.
That is survivorship bias, and it should inflate every finding.

This runs the identical pipeline on a wider universe (124 tickers) that
deliberately includes laggards, distributors, unrelated industrials and
companies with no AI story at all. If the persistence effect survives there, it
is much harder to dismiss as an artefact of how the ticker list was built.

Three possible outcomes:

  edge holds        real evidence -- the universe was not selected to produce it
  edge disappears   the finding was an artefact of universe selection
  edge weakens      the truth sits between, which is the likeliest result

    python backtest/universe_test.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

import csv
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

import config

warnings.filterwarnings("ignore")

CONTROL_FILE = "data/tickers_control.csv"
CACHE_PATH = "cache/control_history.pkl"
RESULTS_DIR = "backtest_results"

HISTORY_YEARS = 3
HORIZON = 20
SIGNAL_GAP_DAYS = 10
PERSISTENCE_MIN = config.PERSISTENT_STREAK_MIN


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_control_universe():
    with open(CONTROL_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def download(tickers):
    os.makedirs("cache", exist_ok=True)
    if os.path.exists(CACHE_PATH):
        print(f"Loading cached history from {CACHE_PATH}")
        return pd.read_pickle(CACHE_PATH)

    print(f"Downloading {HISTORY_YEARS}y for {len(tickers)} tickers...")
    data = yf.download(tickers, period=f"{HISTORY_YEARS}y", interval="1d",
                       auto_adjust=True, group_by="ticker",
                       progress=True, threads=True)
    data.to_pickle(CACHE_PATH)
    return data


def prepare(data, ticker):
    """Rolling metrics plus forward returns and persistence count."""
    try:
        df = data[ticker][["Close", "Volume"]].dropna()
    except (KeyError, TypeError):
        return None
    if len(df) < config.BASELINE_WINDOW_DAYS + HORIZON + 20:
        return None

    dv = df["Close"] * df["Volume"]
    out = pd.DataFrame(index=df.index)
    out["close"] = df["Close"]
    out["volume_ratio"] = (dv.rolling(config.RECENT_WINDOW_DAYS).mean()
                           / dv.rolling(config.BASELINE_WINDOW_DAYS).mean())
    out["price_change"] = df["Close"].pct_change(config.RECENT_WINDOW_DAYS)
    out[f"fwd_{HORIZON}d"] = df["Close"].shift(-HORIZON) / df["Close"] - 1

    qualifies = ((out["volume_ratio"] >= config.VOLUME_SURGE_THRESHOLD)
                 & (out["price_change"] >= config.PRICE_CHANGE_THRESHOLD))
    out["qualifies"] = qualifies
    # Trading-day proxy for the 14 calendar-day streak window
    out["persistence"] = qualifies.rolling(10).sum()

    return out


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

def find_signals(df):
    dates = df.index[df["qualifies"].fillna(False)]
    if len(dates) == 0:
        return []
    kept = [dates[0]]
    for d in dates[1:]:
        if len(df.loc[kept[-1]:d]) - 1 >= SIGNAL_GAP_DAYS:
            kept.append(d)
    return kept


def build_baseline(frames):
    col = f"fwd_{HORIZON}d"
    panel = pd.concat([f[col].rename(t) for t, f in frames.items()], axis=1)
    return panel.mean(axis=1)


def collect(frames, meta, baseline, label):
    records = []
    for ticker, df in frames.items():
        for date in find_signals(df):
            row = df.loc[date]
            fwd = row[f"fwd_{HORIZON}d"]
            base = baseline.get(date, np.nan)
            if pd.isna(fwd) or pd.isna(base):
                continue
            records.append({
                "universe": label,
                "ticker": ticker,
                "category": meta.get(ticker, {}).get("category", ""),
                "in_original": meta.get(ticker, {}).get("in_original", ""),
                "date": date.date().isoformat(),
                "volume_ratio": round(row["volume_ratio"], 2),
                "persistence": int(row["persistence"])
                if pd.notna(row["persistence"]) else 0,
                "fwd_pct": round(fwd * 100, 2),
                "base_pct": round(base * 100, 2),
                "excess_pct": round((fwd - base) * 100, 2),
            })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def stats(df, label):
    if df.empty:
        return None
    exc = df["excess_pct"]
    return {
        "group": label,
        "signals": len(df),
        "tickers": df["ticker"].nunique(),
        "mean_excess_pp": round(exc.mean(), 2),
        "median_excess_pp": round(exc.median(), 2),
        "beat_baseline_pct": round((exc > 0).mean() * 100, 1),
    }


def bootstrap_ci(df, n=5000, seed=42):
    """Clustered bootstrap by ticker, as used in significance_testing.py."""
    if df.empty or df["ticker"].nunique() < 3:
        return None, None
    rng = np.random.default_rng(seed)
    groups = {t: g["excess_pct"].values for t, g in df.groupby("ticker")}
    keys = list(groups)
    means = np.array([
        np.concatenate([groups[t] for t in rng.choice(keys, len(keys), True)]).mean()
        for _ in range(n)
    ])
    return round(float(np.percentile(means, 2.5)), 2), \
           round(float(np.percentile(means, 97.5)), 2)


def main():
    universe = load_control_universe()
    meta = {r["ticker"]: r for r in universe}
    tickers = [r["ticker"] for r in universe]

    data = download(tickers)

    frames, skipped = {}, []
    for t in tickers:
        f = prepare(data, t)
        if f is None:
            skipped.append(t)
        else:
            frames[t] = f

    print(f"\nUsable: {len(frames)} of {len(tickers)} tickers")
    if skipped:
        print(f"No data (delisted or insufficient history): {', '.join(skipped)}")

    baseline = build_baseline(frames)
    signals = collect(frames, meta, baseline, "control")

    if signals.empty:
        print("No signals found.")
        return

    orig = signals[signals["in_original"] == "yes"]
    added = signals[signals["in_original"] == "no"]

    print("\n" + "=" * 78)
    print(f"ALL SIGNALS ON THE CONTROL UNIVERSE   ({HORIZON}-day horizon)")
    print("=" * 78 + "\n")

    rows = [r for r in [
        stats(signals, "control universe (all 124)"),
        stats(orig, "  of which: original 60"),
        stats(added, "  of which: newly added 64"),
    ] if r]
    print(pd.DataFrame(rows).to_string(index=False))

    print("""
The 'newly added' row is the one that matters. Those companies were chosen
without regard to whether they performed well -- distributors, laggards,
unrelated industrials. If their numbers resemble the original 60, the earlier
results were not merely an artefact of picking winners.
""")

    print("\n" + "=" * 78)
    print(f"PERSISTENCE EFFECT (>= {PERSISTENCE_MIN} qualifying days)")
    print("=" * 78 + "\n")

    persist_rows = []
    for label, subset in [("control universe (all 124)", signals),
                          ("  of which: original 60", orig),
                          ("  of which: newly added 64", added)]:
        hi = subset[subset["persistence"] >= PERSISTENCE_MIN]
        lo = subset[subset["persistence"] < PERSISTENCE_MIN]
        if len(hi) < 10 or len(lo) < 10:
            continue
        persist_rows.append({
            "group": label,
            "n_persistent": len(hi),
            "persistent_excess_pp": round(hi["excess_pct"].mean(), 2),
            "persistent_median_pp": round(hi["excess_pct"].median(), 2),
            "persistent_beat_pct": round((hi["excess_pct"] > 0).mean() * 100, 1),
            "n_brief": len(lo),
            "brief_excess_pp": round(lo["excess_pct"].mean(), 2),
            "brief_beat_pct": round((lo["excess_pct"] > 0).mean() * 100, 1),
            "gap_pp": round(hi["excess_pct"].mean() - lo["excess_pct"].mean(), 2),
        })

    if persist_rows:
        print(pd.DataFrame(persist_rows).to_string(index=False))
    else:
        print("Not enough signals on either side of the threshold.")

    print("\n" + "=" * 78)
    print("CLUSTERED BOOTSTRAP ON THE PERSISTENT GROUP")
    print("=" * 78)

    for label, subset in [("Control universe", signals),
                          ("Newly added only", added)]:
        hi = subset[subset["persistence"] >= PERSISTENCE_MIN]
        if len(hi) < 20:
            print(f"\n{label}: only {len(hi)} persistent signals, skipping")
            continue
        lo_ci, hi_ci = bootstrap_ci(hi)
        obs = hi["excess_pct"].mean()
        print(f"\n{label}  ({len(hi)} signals, {hi['ticker'].nunique()} tickers)")
        print(f"  Observed mean excess: {obs:+.2f} pp")
        if lo_ci is not None:
            print(f"  95% interval:         {lo_ci:+.2f} to {hi_ci:+.2f} pp")
            print("  -> Excludes zero." if lo_ci > 0
                  else "  -> Includes zero. Cannot distinguish from luck.")

    signals.to_csv(f"{RESULTS_DIR}/control_signals.csv", index=False)
    print(f"\n\nWritten to {RESULTS_DIR}/control_signals.csv")

    print("""
WHAT THIS TEST DOES AND DOES NOT FIX

Fixes: the original 60 were selected for prominence, which correlates with
having performed well. The added 64 were selected mechanically by category
membership, including companies with no AI exposure whatsoever.

Does NOT fix: companies delisted or acquired at a loss during 2023-2026 return
no data from yfinance, so genuine failures remain absent from both universes.
The list is also limited to what could be enumerated by hand rather than pulled
from a full exchange listing. Some selection bias survives.
""")


if __name__ == "__main__":
    main()