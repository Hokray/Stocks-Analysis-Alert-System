"""
Exit rule comparison.

The screener answers "when to look at a stock". It says nothing about when to
stop. This tests several exit rules against historical signals to see whether
any of them beat simply holding for a fixed period.

Rules tested
------------
  fixed_N          hold exactly N trading days (the baseline the earlier
                   backtests used)
  volume_decay     exit when the dollar-volume ratio falls back below 1.0 --
                   the money that justified the entry has stopped arriving
  signal_death     exit when the stock no longer meets BOTH entry conditions
  trailing_N       exit when price falls N% from its peak since entry
  ma20_break       exit when the close drops below its 20-day moving average

Every open-ended rule is capped at MAX_HOLD_DAYS so a trade cannot run forever.

Comparison method
-----------------
Holding periods differ between rules, so raw returns are not comparable -- a
rule that holds 60 days gets more market exposure than one holding 10. Each
trade is therefore measured against the universe's average return over that
trade's OWN entry-to-exit window.

Requires cache/backtest_history.pkl and backtest_results/signals_enriched.csv.

    python research/phase1_validation/exit_rules.py
"""

import os
import sys


import numpy as np
import pandas as pd

# Scripts live in research/<phase>/ but import config.py from the repo root.
# Walk up until we find it, then run from there so relative paths resolve.
ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(ROOT, "config.py")):
    ROOT = os.path.dirname(ROOT)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config

RESULTS_DIR = "results/phase1"
SIGNALS_PATH = f"{RESULTS_DIR}/signals_enriched.csv"
HISTORY_PATH = "cache/backtest_history.pkl"

MAX_HOLD_DAYS = 90
PERSISTENCE_FILTER = 8   # matches PERSISTENT_STREAK_MIN


# ---------------------------------------------------------------------------
# Panel construction
# ---------------------------------------------------------------------------

def build_panel(history, tickers):
    """Close prices for every ticker on a shared date index."""
    frames = {}
    for t in tickers:
        try:
            s = history[t]["Close"].dropna()
        except (KeyError, TypeError):
            continue
        if len(s) > config.BASELINE_WINDOW_DAYS:
            frames[t] = s
    return pd.DataFrame(frames)


def build_metrics(history, ticker):
    """Per-ticker volume ratio, price change and 20-day MA."""
    try:
        df = history[ticker][["Close", "Volume"]].dropna()
    except (KeyError, TypeError):
        return None
    if len(df) < config.BASELINE_WINDOW_DAYS + 5:
        return None

    dv = df["Close"] * df["Volume"]
    out = pd.DataFrame(index=df.index)
    out["close"] = df["Close"]
    out["volume_ratio"] = (dv.rolling(config.RECENT_WINDOW_DAYS).mean()
                           / dv.rolling(config.BASELINE_WINDOW_DAYS).mean())
    out["price_change"] = df["Close"].pct_change(config.RECENT_WINDOW_DAYS)
    out["ma20"] = df["Close"].rolling(20).mean()
    return out


# ---------------------------------------------------------------------------
# Exit rules
#
# Each takes the ticker's forward metrics from the day after entry and returns
# the integer offset at which to exit.
# ---------------------------------------------------------------------------

def exit_fixed(fwd, n):
    return min(n, len(fwd) - 1)


def exit_volume_decay(fwd, floor=1.0):
    below = np.where(fwd["volume_ratio"].values < floor)[0]
    return int(below[0]) if len(below) else len(fwd) - 1


def exit_signal_death(fwd):
    alive = ((fwd["volume_ratio"] >= config.VOLUME_SURGE_THRESHOLD)
             & (fwd["price_change"] >= config.PRICE_CHANGE_THRESHOLD))
    dead = np.where(~alive.values)[0]
    return int(dead[0]) if len(dead) else len(fwd) - 1


def exit_trailing(fwd, pct):
    closes = fwd["close"].values
    peak = closes[0]
    for i, c in enumerate(closes):
        peak = max(peak, c)
        if c <= peak * (1 - pct):
            return i
    return len(closes) - 1


def exit_ma_break(fwd):
    broken = np.where((fwd["close"] < fwd["ma20"]).values)[0]
    return int(broken[0]) if len(broken) else len(fwd) - 1


EXIT_RULES = {
    "fixed_10":      lambda f: exit_fixed(f, 10),
    "fixed_20":      lambda f: exit_fixed(f, 20),
    "fixed_30":      lambda f: exit_fixed(f, 30),
    "fixed_60":      lambda f: exit_fixed(f, 60),
    "volume_decay":  lambda f: exit_volume_decay(f, 1.0),
    "signal_death":  exit_signal_death,
    "trailing_10":   lambda f: exit_trailing(f, 0.10),
    "trailing_15":   lambda f: exit_trailing(f, 0.15),
    "trailing_20":   lambda f: exit_trailing(f, 0.20),
    "ma20_break":    exit_ma_break,
}


# ---------------------------------------------------------------------------
# Trade simulation
# ---------------------------------------------------------------------------

def run_rule(signals, metrics_cache, panel, rule_name, rule_fn):
    trades = []

    for _, sig in signals.iterrows():
        ticker = sig["ticker"]
        metrics = metrics_cache.get(ticker)
        if metrics is None:
            continue

        entry_date = pd.Timestamp(sig["date"])
        idx = metrics.index.get_indexer([entry_date], method="nearest")
        if len(idx) == 0 or idx[0] < 0:
            continue
        entry_i = int(idx[0])

        # Forward window, capped
        fwd = metrics.iloc[entry_i + 1: entry_i + 1 + MAX_HOLD_DAYS]
        if len(fwd) < 5:
            continue  # not enough future data (signal near end of history)

        offset = rule_fn(fwd)
        exit_i = entry_i + 1 + offset

        entry_price = metrics["close"].iloc[entry_i]
        exit_price = metrics["close"].iloc[exit_i]
        trade_return = exit_price / entry_price - 1

        entry_ts = metrics.index[entry_i]
        exit_ts = metrics.index[exit_i]

        # Universe return over this trade's OWN window
        try:
            start_row = panel.loc[:entry_ts].iloc[-1]
            end_row = panel.loc[:exit_ts].iloc[-1]
            uni = (end_row / start_row - 1).dropna()
            baseline = uni.mean() if len(uni) else np.nan
        except (KeyError, IndexError):
            baseline = np.nan

        # Worst drawdown experienced while holding
        path = metrics["close"].iloc[entry_i: exit_i + 1].values
        running_peak = np.maximum.accumulate(path)
        max_dd = float((path / running_peak - 1).min())

        trades.append({
            "rule": rule_name,
            "ticker": ticker,
            "entry": entry_ts.date().isoformat(),
            "exit": exit_ts.date().isoformat(),
            "hold_days": exit_i - entry_i,
            "return_pct": trade_return * 100,
            "baseline_pct": baseline * 100 if pd.notna(baseline) else np.nan,
            "excess_pct": ((trade_return - baseline) * 100
                           if pd.notna(baseline) else np.nan),
            "max_drawdown_pct": max_dd * 100,
        })

    return pd.DataFrame(trades)


def summarise(all_trades):
    rows = []
    for rule, grp in all_trades.groupby("rule", sort=False):
        exc = grp["excess_pct"].dropna()
        ret = grp["return_pct"].dropna()
        if len(exc) == 0:
            continue
        rows.append({
            "rule": rule,
            "trades": len(ret),
            "mean_hold_days": round(grp["hold_days"].mean(), 1),
            "mean_return_pct": round(ret.mean(), 2),
            "median_return_pct": round(ret.median(), 2),
            "mean_excess_pp": round(exc.mean(), 2),
            "median_excess_pp": round(exc.median(), 2),
            "beat_baseline_pct": round((exc > 0).mean() * 100, 1),
            "mean_max_dd_pct": round(grp["max_drawdown_pct"].mean(), 1),
            "worst_trade_pct": round(ret.min(), 1),
        })

    order = list(EXIT_RULES.keys())
    out = pd.DataFrame(rows)
    out["_o"] = out["rule"].apply(order.index)
    return out.sort_values("_o").drop(columns="_o").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(SIGNALS_PATH) or not os.path.exists(HISTORY_PATH):
        print("Run backtest.py and backtest_analysis.py first.")
        return

    signals = pd.read_csv(SIGNALS_PATH)
    history = pd.read_pickle(HISTORY_PATH)

    tickers = signals["ticker"].unique().tolist()
    panel = build_panel(history, tickers)
    metrics_cache = {t: build_metrics(history, t) for t in tickers}
    metrics_cache = {t: m for t, m in metrics_cache.items() if m is not None}

    print(f"{len(signals)} signals, {len(metrics_cache)} tickers with usable data")

    for label, subset in [
        ("ALL SIGNALS", signals),
        (f"PERSISTENT ONLY (>= {PERSISTENCE_FILTER} qualifying days)",
         signals[signals.get("persistence_days", pd.Series(dtype=float))
                 >= PERSISTENCE_FILTER]),
    ]:
        if len(subset) < 20:
            print(f"\n{label}: too few signals ({len(subset)}), skipping")
            continue

        print("\n\n" + "=" * 92)
        print(f"{label}   ({len(subset)} signals)")
        print("=" * 92 + "\n")

        frames = [run_rule(subset, metrics_cache, panel, name, fn)
                  for name, fn in EXIT_RULES.items()]
        all_trades = pd.concat([f for f in frames if not f.empty],
                               ignore_index=True)

        summary = summarise(all_trades)
        print(summary.to_string(index=False))

        best = summary.loc[summary["mean_excess_pp"].idxmax()]
        best_med = summary.loc[summary["median_excess_pp"].idxmax()]
        print(f"\n  Best mean excess:   {best['rule']} "
              f"({best['mean_excess_pp']:+.2f} pp, "
              f"{best['mean_hold_days']} day avg hold)")
        print(f"  Best median excess: {best_med['rule']} "
              f"({best_med['median_excess_pp']:+.2f} pp)")

        if best["rule"] != best_med["rule"]:
            print("  -> Mean and median disagree: the mean-best rule is likely"
                  " outlier-driven.")

        tag = "persistent" if "PERSISTENT" in label else "all"
        all_trades.to_csv(f"{RESULTS_DIR}/exit_trades_{tag}.csv", index=False)
        summary.to_csv(f"{RESULTS_DIR}/exit_summary_{tag}.csv", index=False)

    print(f"\n\nWritten to {RESULTS_DIR}/")

    print("""
HOW TO READ THIS

Compare median_excess_pp before mean_excess_pp. The mean is easily dominated by
one or two enormous winners -- the same problem that made the base signal look
better than it was.

mean_max_dd_pct is the average worst loss experienced WHILE holding. A rule with
good returns and a -35% average drawdown is one most people would abandon
partway through, which makes its backtest return unachievable in practice.

Compare every rule against fixed_20. If nothing beats simply holding 20 days,
that is the finding: the exit does not matter much, and effort belongs elsewhere.

CAVEAT: ten rules were tested on the same data used for everything else. One
will look best by chance alone. Trust a rule only if it wins on BOTH mean and
median, and its neighbours (e.g. trailing_10 and trailing_20 around
trailing_15) look similar -- a lone spike is noise.
""")


if __name__ == "__main__":
    main()