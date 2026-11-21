"""
Path study -- does the SHAPE of a price move predict what happens next?

The live price filter measures (close_today - close_10_ago) / close_10_ago.
Endpoint-only, path-blind: a stock that rose 25% and fell back to +10% is
indistinguishable from one still climbing at +10%.

This measures two path metrics at the moment of each historical alert and asks
whether alerts whose 10-session high is RECENT behaved differently from alerts
whose high is STALE.

Everything testable here was fixed in advance. See PREREGISTRATION.md in this
directory -- the fresh/stale cut, the confirmatory horizon, the +2.0 pp
threshold and the sample-size floors are all read from constants below so the
preregistered values sit in one visible place.

This script PRINTS NUMBERS AND DOES NOT DECIDE ANYTHING. There is deliberately
no pass/fail verdict in the output: reading the result against the criterion is
a separate step, done once, by a human. A script that announces "PASS" is a
script that invites adjustment until it does.

Reuses the phase-1 pipeline rather than re-implementing it
----------------------------------------------------------
The alert set must be identical to the one phase 1 measured, so the trigger
logic is imported from research/phase1_validation/backtest.py and left alone.
This matters more than it looks: extract_ticker_frame drops any ticker with
less than BASELINE_WINDOW_DAYS + max(HORIZONS) + 10 sessions, so that module's
HORIZONS decides which tickers are eligible at all. Rebuilding that around this
study's horizons would quietly change the usable universe, the baseline and the
alert list. So its constants stay untouched: horizons 5 and 10 come from what it
already computes, and the 21-session forward return is added here.

Two inherited behaviours worth naming, both kept for comparability
-----------------------------------------------------------------
1. backtest.compute_metrics computes the volume baseline as a plain rolling
   mean, so the baseline window OVERLAPS the recent window. The live screener
   does not (config.BASELINE_EXCLUDES_RECENT is True). The alert set here is
   therefore phase-1-comparable but NOT identical to what the live screener
   fires on today.
2. build_baseline includes a date's own alerting tickers in that date's
   cross-sectional mean.

Neither is corrected here. Changing either would break comparability with every
phase-1 result and turn a measurement study into a redesign.

Run it:
    python research/phase2_path/path_analysis.py
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

import config

# The phase-1 backtest is the source of truth for what counts as an alert.
sys.path.insert(0, os.path.join(ROOT, "research", "phase1_validation"))
import backtest

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

RESULTS_DIR = "results/phase2_path"
UNIVERSE_FILE = "data/tickers_universe.csv"

# Both caches are strict subsets of UNIVERSE_FILE, so one metadata source
# covers both runs. Primary is declared here, not chosen after the fact.
RUNS = [
    ("primary (60-ticker)", "cache/backtest_history.pkl"),
    ("replication (178-ticker)", "cache/universe178_history.pkl"),
]

# --- preregistered values: see PREREGISTRATION.md -------------------------

RECENT_N = config.RECENT_WINDOW_DAYS     # 10 -- window the path is measured over

HORIZONS = [5, 10, 21]                   # sessions
CONFIRMATORY_HORIZON = 10                # and only this one

FRESH_MAX = 2                            # days_since_high 0-2
STALE_MIN = 5                            # days_since_high 5-9; 3-4 dropped

MIN_ALERTS_PER_GROUP = 100
MIN_TICKERS_PER_GROUP = 20
PASS_THRESHOLD_PP = 2.0

N_BOOTSTRAP = 10000
RANDOM_SEED = 42

# Candidate live filter whose cost is reported: reject stale alerts.
FILTER_VARIANTS = [STALE_MIN, 3]

# Power constants: 1.96 for a two-sided 95% interval, 2.80 = 1.96 + 0.84 for
# 80% power.
Z_CI = 1.96
Z_MDE = 2.80


# ---------------------------------------------------------------------------
# The two path metrics
#
# Pure functions over a sequence of closes, oldest first. The vectorised pass
# below calls these exact functions rather than reimplementing them, so the
# fencepost tests in test_path_metrics.py pin the code the study actually runs.
# ---------------------------------------------------------------------------

def days_since_high(closes, recent_n=RECENT_N):
    """
    Sessions since the highest close in the last `recent_n` closes.

    0 means the window peaked today; `recent_n - 1` means it peaked at the
    window start.

        days_since_high = (recent_n - 1) - argmax(closes)

    Ties go to the EARLIER bar, because np.argmax returns the first occurrence.
    Two bars at the same high therefore score as the staler of the two, so a tie
    never flatters the fresh group. That direction is a deliberate choice, not
    an accident of the implementation.
    """
    window = _window(closes, recent_n)
    return int(recent_n - 1 - int(np.argmax(window)))


def drawdown_from_high(closes, recent_n=RECENT_N):
    """
    How far below the window's high the final close sits, as a fraction.

        (max(closes) - closes[-1]) / max(closes)

    0 when today IS the high, positive otherwise. Never negative by
    construction. Returns nan on a non-positive high, which adjusted prices can
    in principle produce and which would otherwise divide by zero.
    """
    window = _window(closes, recent_n)
    high = window.max()
    if high <= 0:
        return np.nan
    return float((high - window[-1]) / high)


def _window(closes, recent_n):
    """The last `recent_n` closes, as a float array, oldest first."""
    if recent_n < 1:
        raise ValueError(f"recent_n must be >= 1, got {recent_n}")

    window = np.asarray(closes, dtype=float)
    if window.ndim != 1:
        raise ValueError("closes must be one-dimensional")
    if len(window) < recent_n:
        raise ValueError(
            f"need at least {recent_n} closes, got {len(window)}"
        )
    return window[-recent_n:]


def spearman(a, b):
    """
    Rank correlation, without scipy.

    pandas' own method="spearman" imports scipy, which this repo does not have
    and which this study is not allowed to add. Spearman is Pearson on ranks,
    so ranking first and taking the ordinary correlation is the same number.
    pandas' default ranking averages ties, which is the tie correction
    Spearman calls for.
    """
    ranked_a = pd.Series(np.asarray(a, dtype=float)).rank()
    ranked_b = pd.Series(np.asarray(b, dtype=float)).rank()
    return ranked_a.corr(ranked_b)


def classify(days):
    """fresh / stale / dropped, per the preregistered cut."""
    if days is None or (isinstance(days, float) and np.isnan(days)):
        return "unknown"
    if days <= FRESH_MAX:
        return "fresh"
    if days >= STALE_MIN:
        return "stale"
    return "dropped"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_universe_meta():
    with open(UNIVERSE_FILE, newline="", encoding="utf-8") as f:
        return {r["ticker"]: r for r in csv.DictReader(f)}


def build_frames(cache_path, tickers):
    """
    Per-ticker frames with the phase-1 metrics, this study's path metrics and
    its forward returns.

    extract_ticker_frame and compute_metrics are imported unchanged so the
    eligible universe and the trigger inputs match phase 1 exactly.
    """
    data = pd.read_pickle(cache_path)

    frames = {}
    skipped = []
    for ticker in tickers:
        df = backtest.extract_ticker_frame(data, ticker)
        if df is None:
            skipped.append(ticker)
            continue
        frames[ticker] = add_path_metrics(backtest.compute_metrics(df))

    return frames, skipped


def add_path_metrics(frame):
    """
    Add both path metrics and any horizon the phase-1 module does not compute.

    Both metrics are computed for every row by rolling the pure functions over
    the close series, then read off at alert dates. Computing them vectorised
    and reading them off -- rather than slicing per alert -- keeps the window
    arithmetic in exactly one place, which is the place the tests cover.

    A rolling window's last element is the current bar, so the window is the
    last RECENT_N closes with the alert day as closes[-1]. That is the
    definition in PREREGISTRATION.md.
    """
    out = frame.copy()
    closes = out["Close"]

    out["days_since_high"] = closes.rolling(RECENT_N).apply(
        lambda w: days_since_high(w, RECENT_N), raw=True
    )
    out["drawdown_from_high"] = closes.rolling(RECENT_N).apply(
        lambda w: drawdown_from_high(w, RECENT_N), raw=True
    )

    for h in HORIZONS:
        col = f"fwd_{h}d"
        if col not in out:
            out[col] = closes.shift(-h) / closes - 1

    return out


def build_baseline(frames):
    """
    Date-matched universe mean forward return, per horizon.

    Identical computation to backtest.build_baseline, restricted to this
    study's horizons -- that module iterates its own HORIZONS, which do not
    include 21. Concatenating every usable ticker's forward-return column and
    taking the row mean is the same operation on the same frames.
    """
    baseline = {}
    for h in HORIZONS:
        col = f"fwd_{h}d"
        series = pd.concat([f[col].rename(t) for t, f in frames.items()], axis=1)
        baseline[h] = series.mean(axis=1)
    return baseline


def collect_alerts(frames, baseline, meta):
    """One row per alert, with path metrics, forward returns and excess."""
    records = []

    for ticker, frame in frames.items():
        signals = backtest.find_signals(
            frame,
            config.VOLUME_SURGE_THRESHOLD,
            config.PRICE_CHANGE_THRESHOLD,
        )

        for date, row in signals.iterrows():
            days = row["days_since_high"]

            record = {
                "ticker": ticker,
                "category": meta.get(ticker, {}).get("category", ""),
                "date": date.date().isoformat(),
                "price": round(row["Close"], 2),
                "volume_ratio": round(row["volume_ratio"], 2),
                "price_change_pct": round(row["price_change"] * 100, 1),
                "days_since_high": None if pd.isna(days) else int(days),
                "drawdown_from_high_pct": (
                    None if pd.isna(row["drawdown_from_high"])
                    else round(row["drawdown_from_high"] * 100, 2)
                ),
                "group": classify(days),
            }

            for h in HORIZONS:
                fwd = row[f"fwd_{h}d"]
                base = baseline[h].get(date, np.nan)

                record[f"fwd_{h}d_pct"] = (
                    round(fwd * 100, 2) if pd.notna(fwd) else None
                )
                record[f"base_{h}d_pct"] = (
                    round(base * 100, 2) if pd.notna(base) else None
                )
                record[f"excess_{h}d_pct"] = (
                    round((fwd - base) * 100, 2)
                    if pd.notna(fwd) and pd.notna(base) else None
                )

            records.append(record)

    results = pd.DataFrame(records)
    if not results.empty:
        results = results.sort_values(["date", "ticker"]).reset_index(drop=True)
    return results


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def bootstrap_difference(df, col, n_iterations=N_BOOTSTRAP, seed=RANDOM_SEED):
    """
    Clustered bootstrap of the fresh-minus-stale difference.

    TICKERS are resampled, not alerts, and a resampled ticker brings BOTH of its
    groups along. One ticker contributed 24 alerts to the phase-1 sample, all
    from the same stock over overlapping periods and driven by the same
    underlying move; those are not 24 independent observations. Resampling
    alerts would treat them as independent and produce an interval far too
    narrow, making a fragile result look solid.

    Resamples in which either group comes up empty are discarded -- the
    difference is undefined there -- and counted, since many such resamples
    would itself say the sample is too thin to lean on.
    """
    rng = np.random.default_rng(seed)

    by_ticker = {}
    for ticker, chunk in df.groupby("ticker"):
        fresh = chunk.loc[chunk["group"] == "fresh", col].dropna().values
        stale = chunk.loc[chunk["group"] == "stale", col].dropna().values
        if len(fresh) or len(stale):
            by_ticker[ticker] = (fresh, stale)

    tickers = list(by_ticker)
    if not tickers:
        return np.array([]), 0

    diffs = []
    discarded = 0
    for _ in range(n_iterations):
        picked = rng.choice(tickers, size=len(tickers), replace=True)
        fresh = np.concatenate([by_ticker[t][0] for t in picked])
        stale = np.concatenate([by_ticker[t][1] for t in picked])

        if len(fresh) == 0 or len(stale) == 0:
            discarded += 1
            continue
        diffs.append(fresh.mean() - stale.mean())

    return np.asarray(diffs), discarded


def group_stats(df, col):
    """n, distinct tickers and mean of `col` for fresh and stale."""
    stats = {}
    for name in ("fresh", "stale"):
        chunk = df[(df["group"] == name) & df[col].notna()]
        stats[name] = {
            "n": len(chunk),
            "tickers": chunk["ticker"].nunique(),
            "mean": chunk[col].mean() if len(chunk) else np.nan,
            "median": chunk[col].median() if len(chunk) else np.nan,
            "sd": chunk[col].std(ddof=1) if len(chunk) > 1 else np.nan,
            "beat_pct": (chunk[col] > 0).mean() * 100 if len(chunk) else np.nan,
        }
    return stats


def realised_power(stats):
    """
    What this design could detect at the group sizes that actually occurred.

    The formula and the power constants were fixed in PREREGISTRATION.md; only
    n and the dispersion come from the data. Reported so a null can be told
    apart from a design that could never have found anything.
    """
    n1, n2 = stats["fresh"]["n"], stats["stale"]["n"]
    sd1, sd2 = stats["fresh"]["sd"], stats["stale"]["sd"]

    if n1 < 2 or n2 < 2 or not np.isfinite(sd1) or not np.isfinite(sd2):
        return None

    pooled_var = (((n1 - 1) * sd1 ** 2) + ((n2 - 1) * sd2 ** 2)) / (n1 + n2 - 2)
    pooled_sd = np.sqrt(pooled_var)
    scale = pooled_sd * np.sqrt(1 / n1 + 1 / n2)

    return {
        "pooled_sd": pooled_sd,
        "ci_half_width": Z_CI * scale,
        "mde_80": Z_MDE * scale,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def report_confirmatory(df, label):
    """The one preregistered comparison. Numbers only, no verdict."""
    col = f"excess_{CONFIRMATORY_HORIZON}d_pct"

    section(f"CONFIRMATORY TEST -- {label}")
    print(f"\nfresh = days_since_high 0-{FRESH_MAX}   "
          f"stale = days_since_high {STALE_MIN}-{RECENT_N - 1}   "
          f"dropped = {FRESH_MAX + 1}-{STALE_MIN - 1}")
    print(f"Quantity: fresh minus stale, mean excess return at "
          f"{CONFIRMATORY_HORIZON} sessions, in percentage points.\n")

    stats = group_stats(df, col)

    rows = []
    for name in ("fresh", "stale"):
        s = stats[name]
        rows.append({
            "group": name,
            "alerts": s["n"],
            "tickers": s["tickers"],
            "mean_excess_pp": round(s["mean"], 2) if np.isfinite(s["mean"]) else None,
            "median_excess_pp": round(s["median"], 2) if np.isfinite(s["median"]) else None,
            "sd_pp": round(s["sd"], 2) if np.isfinite(s["sd"]) else None,
            "beat_baseline_pct": round(s["beat_pct"], 1) if np.isfinite(s["beat_pct"]) else None,
        })
    print(pd.DataFrame(rows).to_string(index=False))

    # --- sample-size floors, fixed in advance and not moved ---
    print(f"\nPreregistered floors: >= {MIN_ALERTS_PER_GROUP} alerts "
          f"AND >= {MIN_TICKERS_PER_GROUP} tickers per group")
    for name in ("fresh", "stale"):
        s = stats[name]
        ok_alerts = s["n"] >= MIN_ALERTS_PER_GROUP
        ok_tickers = s["tickers"] >= MIN_TICKERS_PER_GROUP
        state = "meets floors" if (ok_alerts and ok_tickers) else "UNDERPOWERED"
        print(f"  {name:<6} {s['n']:>4} alerts "
              f"({'ok' if ok_alerts else 'below'}), "
              f"{s['tickers']:>3} tickers "
              f"({'ok' if ok_tickers else 'below'})  -> {state}")

    observed = stats["fresh"]["mean"] - stats["stale"]["mean"]
    if not np.isfinite(observed):
        print("\nOne group is empty. No difference to report.")
        return None

    diffs, discarded = bootstrap_difference(df, col)
    if len(diffs) == 0:
        print("\nBootstrap produced no usable resamples.")
        return None

    lo, hi = np.percentile(diffs, [2.5, 97.5])

    print(f"\nObserved difference:       {observed:+.2f} pp")
    print(f"95% CI (clustered by ticker, {len(diffs)} usable resamples): "
          f"{lo:+.2f} pp to {hi:+.2f} pp")
    print(f"Share of resamples <= 0:   {(diffs <= 0).mean() * 100:.1f}%")
    if discarded:
        print(f"Resamples discarded (a group came up empty): {discarded}")

    power = realised_power(stats)
    if power:
        print(f"\nRealised power at these group sizes "
              f"(pooled SD {power['pooled_sd']:.2f} pp):")
        print(f"  95% CI half-width:       {power['ci_half_width']:.2f} pp"
              "   <- smallest difference whose interval would clear zero")
        print(f"  MDE at 80% power:        {power['mde_80']:.2f} pp"
              "   <- smallest true effect this design would reliably catch")
        print(f"  Pass threshold:          {PASS_THRESHOLD_PP:.2f} pp")

    return {
        "label": label,
        "observed_pp": observed,
        "ci_low_pp": lo,
        "ci_high_pp": hi,
        "share_le_zero": (diffs <= 0).mean(),
        "n_fresh": stats["fresh"]["n"],
        "n_stale": stats["stale"]["n"],
        "tickers_fresh": stats["fresh"]["tickers"],
        "tickers_stale": stats["stale"]["tickers"],
        "ci_half_width_pp": power["ci_half_width"] if power else np.nan,
        "mde_80_pp": power["mde_80"] if power else np.nan,
    }


def report_supporting_horizons(df):
    """Horizons 5 and 21. No criterion attached -- direction check only."""
    section("SUPPORTING HORIZONS (no criterion -- direction check only)")
    print("\nA real effect should point the same way at every horizon.\n")

    rows = []
    for h in HORIZONS:
        col = f"excess_{h}d_pct"
        stats = group_stats(df, col)
        diff = stats["fresh"]["mean"] - stats["stale"]["mean"]
        rows.append({
            "horizon": f"{h}d" + (" (confirmatory)" if h == CONFIRMATORY_HORIZON else ""),
            "n_fresh": stats["fresh"]["n"],
            "n_stale": stats["stale"]["n"],
            "fresh_excess_pp": round(stats["fresh"]["mean"], 2),
            "stale_excess_pp": round(stats["stale"]["mean"], 2),
            "difference_pp": round(diff, 2) if np.isfinite(diff) else None,
        })
    print(pd.DataFrame(rows).to_string(index=False))


def report_buckets(df):
    """All ten days_since_high buckets. EXPLORATORY."""
    section("EXPLORATORY -- all ten days_since_high buckets")
    print("\nNo criterion attached. The question is SHAPE: if the recency of the")
    print("high genuinely matters, mean excess should decline roughly smoothly")
    print("as days_since_high rises. A single bad bucket surrounded by fine ones")
    print("is noise, not a mechanism.\n")

    col = f"excess_{CONFIRMATORY_HORIZON}d_pct"
    rows = []
    for days in range(RECENT_N):
        chunk = df[(df["days_since_high"] == days) & df[col].notna()]
        rows.append({
            "days_since_high": days,
            "group": classify(days),
            "alerts": len(chunk),
            "tickers": chunk["ticker"].nunique(),
            f"mean_excess_{CONFIRMATORY_HORIZON}d_pp": (
                round(chunk[col].mean(), 2) if len(chunk) else None
            ),
            "beat_baseline_pct": (
                round((chunk[col] > 0).mean() * 100, 1) if len(chunk) else None
            ),
        })
    print(pd.DataFrame(rows).to_string(index=False))

    # Spearman on the bucket means: does the gradient actually run downhill?
    # Rank correlation on pandas alone, no scipy needed.
    table = pd.DataFrame(rows).dropna(
        subset=[f"mean_excess_{CONFIRMATORY_HORIZON}d_pp"]
    )
    if len(table) >= 3:
        rho = spearman(
            table["days_since_high"],
            table[f"mean_excess_{CONFIRMATORY_HORIZON}d_pp"],
        )
        print(f"\nSpearman rank correlation, bucket index vs mean excess: "
              f"{rho:+.2f}")
        print("Negative = returns fall as the high gets staler, the direction the")
        print("hypothesis predicts. Computed on ten bucket means, so it is a")
        print("description of shape and carries no significance claim.")


def report_drawdown(df):
    """drawdown_from_high as a continuous correlate. EXPLORATORY."""
    section("EXPLORATORY -- drawdown_from_high")
    print("\nNo criterion attached, and none may be added after the fact: the")
    print("hypothesis names the recency of the high, not the depth of the")
    print("pullback. Making this confirmatory would need its own preregistered")
    print("threshold and a correction for testing twice.\n")

    col = f"excess_{CONFIRMATORY_HORIZON}d_pct"
    usable = df[df["drawdown_from_high_pct"].notna() & df[col].notna()]
    if usable.empty:
        print("No usable rows.")
        return

    rho = spearman(usable["drawdown_from_high_pct"], usable[col])
    print(f"Spearman correlation with {CONFIRMATORY_HORIZON}d excess return, "
          f"across all {len(usable)} alerts: {rho:+.3f}")

    quartiles = pd.qcut(
        usable["drawdown_from_high_pct"], 4, labels=False, duplicates="drop"
    )
    table = usable.groupby(quartiles).agg(
        alerts=("ticker", "count"),
        tickers=("ticker", "nunique"),
        min_drawdown_pct=("drawdown_from_high_pct", "min"),
        max_drawdown_pct=("drawdown_from_high_pct", "max"),
        mean_excess_pp=(col, "mean"),
    ).round(2)
    table.index.name = "quartile"
    print("\nBy drawdown quartile (shallowest first):\n")
    print(table.to_string())

    print("\nMean drawdown by group:")
    for name in ("fresh", "stale"):
        chunk = df[df["group"] == name]
        if len(chunk):
            print(f"  {name:<6} {chunk['drawdown_from_high_pct'].mean():.2f}%")


def report_filter_cost(df):
    """What the candidate filter would have cost in alert volume."""
    section("COST OF THE CANDIDATE FILTER")
    print("\nReported whatever the outcome: a filter that improves returns while")
    print("removing most alerts may still not be worth it.\n")

    scored = df[df["days_since_high"].notna()]
    total = len(scored)
    if total == 0:
        print("No scored alerts.")
        return

    rows = []
    for cutoff in FILTER_VARIANTS:
        removed = (scored["days_since_high"] >= cutoff).sum()
        rows.append({
            "filter": f"reject days_since_high >= {cutoff}",
            "alerts_removed": int(removed),
            "alerts_kept": int(total - removed),
            "removed_pct": round(removed / total * 100, 1),
            "note": ("confirmatory stale definition" if cutoff == STALE_MIN
                     else "includes the dropped middle"),
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nTotal scored alerts: {total}")
    print(f"The >= {STALE_MIN} figure understates a live filter's cost: buckets "
          f"{FRESH_MAX + 1}-{STALE_MIN - 1} are excluded from the test, but a "
          f"live filter\nwould still have to decide about them.")


def report_composition(df, label, skipped):
    section(f"SAMPLE COMPOSITION -- {label}")
    counts = df["group"].value_counts().reindex(
        ["fresh", "dropped", "stale", "unknown"], fill_value=0
    )
    print(f"\nTotal alerts: {len(df)}   "
          f"tickers: {df['ticker'].nunique()}   "
          f"dates: {df['date'].min()} to {df['date'].max()}")
    print(f"Tickers skipped for insufficient history: {len(skipped)}")
    print("\nBy group:")
    for name, n in counts.items():
        share = n / len(df) * 100 if len(df) else 0
        print(f"  {name:<8} {n:>4}  ({share:.1f}%)")

    missing = df[f"excess_{CONFIRMATORY_HORIZON}d_pct"].isna().sum()
    if missing:
        print(f"\nAlerts with no {CONFIRMATORY_HORIZON}d excess return "
              f"(too close to the end of the data): {missing}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(label, cache_path, meta):
    if not os.path.exists(cache_path):
        print(f"\nMissing cache {cache_path} -- skipping {label}.")
        return None, None

    print(f"\n\n{'#' * 72}")
    print(f"# {label}   [{cache_path}]")
    print(f"{'#' * 72}")

    frames, skipped = build_frames(cache_path, list(meta))
    print(f"\nUsable tickers: {len(frames)}")

    baseline = build_baseline(frames)
    alerts = collect_alerts(frames, baseline, meta)

    if alerts.empty:
        print("No alerts found.")
        return None, None

    report_composition(alerts, label, skipped)
    summary = report_confirmatory(alerts, label)
    report_supporting_horizons(alerts)
    report_buckets(alerts)
    report_drawdown(alerts)
    report_filter_cost(alerts)

    return alerts, summary


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    meta = load_universe_meta()

    summaries = []
    for label, cache_path in RUNS:
        alerts, summary = run(label, cache_path, meta)

        if alerts is not None:
            slug = "primary" if label.startswith("primary") else "replication"
            path = f"{RESULTS_DIR}/path_alerts_{slug}.csv"
            alerts.to_csv(path, index=False)
            print(f"\nPer-alert rows written to {path}")

        if summary is not None:
            summaries.append(summary)

    if summaries:
        section("CONFIRMATORY SUMMARY, BOTH SAMPLES")
        table = pd.DataFrame(summaries).round(2)
        print()
        print(table.to_string(index=False))
        table.to_csv(f"{RESULTS_DIR}/confirmatory_summary.csv", index=False)
        print(f"\nWritten to {RESULTS_DIR}/confirmatory_summary.csv")

    print("\n" + "=" * 72)
    print("NO VERDICT IS PRINTED HERE, BY DESIGN")
    print("=" * 72)
    print(f"""
Read these numbers against PREREGISTRATION.md, once. The criterion is all four
of: the quantity is fresh-minus-stale mean excess at {CONFIRMATORY_HORIZON}
sessions; its clustered 95% CI excludes zero on the positive side; the point
estimate is at least +{PASS_THRESHOLD_PP:.1f} pp; and both groups meet the
{MIN_ALERTS_PER_GROUP}-alert and {MIN_TICKERS_PER_GROUP}-ticker floors.

If the criterion is not met, the MDE decides which null it is. MDE below
{PASS_THRESHOLD_PP:.1f} pp is an interpretable null -- the design could have
seen an effect worth acting on and did not. MDE above it means underpowered,
and that must be said plainly rather than reported as evidence against the
hypothesis.

The replication cannot create a pass. It can only downgrade one to fragile,
per the disagreement rule.
""")


if __name__ == "__main__":
    main()
