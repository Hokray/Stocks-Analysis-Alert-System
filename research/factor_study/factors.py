"""
Factor study -- factor construction and the pre-registered analysis.

    python research/factor_study/factors.py

Local only. It reads the caches built by universe_builder.py and fetch_data.py
and makes no network request, so it runs in a couple of minutes and can be
rerun freely.

What it does
------------
    1  month-end close panel from cache/prices/
    2  lagged annual fundamentals from cache/fundamentals/
    3  factor values at each rebalance date
    4  decile ranking, forward returns, top-minus-bottom spread
    5  by-date bootstrap CI, information coefficient, realised MDE
    6  the pre-registered pass criterion, condition by condition
    7  robustness: ex bottom liquidity quintile, positive-metric-only,
       non-overlapping annual momentum
    8  diagnostics: coverage per factor per date, sector composition per decile

What it does NOT do
-------------------
No buy list, no top picks, no named ticker presented as a conclusion. The
decile is the unit of analysis. Only momentum is eligible to pass; value,
quality, dilution and size are exploratory and no criterion is applied to them.
See DESIGN.md, which is fixed and was written before any of this ran.

Rebalance grids
---------------
Momentum ranks monthly: it needs 13 months of history behind the date and 12
months of forward return ahead of it. The fundamental factors rank on 31
December only, because a 12-month forward return has to fit inside the price
history and 5 annual statement periods minus the 6-month lag leaves ~3 usable
dates. That date count, not the number of names, is what makes them
exploratory -- see DESIGN.md.
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_data import (                                        # noqa: E402
    CACHE_DIR,
    OUTPUT_CSV,
    fundamental_path,
    price_path,
)

warnings.filterwarnings("ignore")

PANEL_CACHE = f"{CACHE_DIR}/factor_panel.csv"

# --- pre-registered, see DESIGN.md ----------------------------------------
HORIZONS = {"1m": 1, "3m": 3, "6m": 6, "12m": 12}
CONFIRMATORY_HORIZON = "12m"
PASS_THRESHOLD_PP = 3.0
MIN_PER_DECILE = 30
MIN_DATES = 12
N_DECILES = 10
BOOTSTRAP_ITERS = 10_000
SEED = 42
FUNDAMENTAL_LAG_MONTHS = 6
MOMENTUM_LOOKBACK = 13          # months back for the start of the 12-1 window
MOMENTUM_SKIP = 1               # months skipped at the recent end
DILUTION_YEARS = 3
SECTOR_EXCLUDED = {"Financial Services", "Real Estate"}

# MDE at 80% power = 2.80 * SD / sqrt(n); 1.96 + 0.84.
Z_POWER = 2.80


# ---------------------------------------------------------------------------
# Factor specification. Fixed here so no factor can acquire a criterion later.
# ---------------------------------------------------------------------------

FACTORS = [
    # column            label                      higher_better confirm sector_excl binary
    ("momentum",        "Momentum (12-1)",                 True,  True,  False, False),
    ("ebit_ev",         "Value: EBIT/EV",                  True,  False, True,  False),
    ("fcf_ev",          "Value: FCF/EV",                   True,  False, True,  False),
    ("gp_assets",       "Quality: gross profit/assets",    True,  False, True,  False),
    ("fcf_positive",    "Quality: positive FCF",           True,  False, True,  True),
    ("dilution",        "Dilution: 3y share change",       False, False, False, False),
    ("size",            "Size: market cap",                True,  False, False, False),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def spearman(a, b):
    """
    Rank correlation without scipy, which is not installed and may not be added.

    Ranking both inputs and taking the ordinary correlation is the same number;
    pandas' default ranking averages ties, which is the correction Spearman
    calls for.
    """
    a = pd.Series(np.asarray(a, dtype=float))
    b = pd.Series(np.asarray(b, dtype=float))
    mask = a.notna() & b.notna()
    if mask.sum() < 3:
        return np.nan
    return a[mask].rank().corr(b[mask].rank())


def assign_deciles(values, higher_is_better):
    """
    Decile 1..10, where 10 is the attractive end by the factor's direction.

    Ties share an average rank and therefore land in ONE decile, never split
    across a boundary. Where n is not divisible by ten the remainder goes to
    the MIDDLE deciles, so decile 1 and decile 10 are always the same size --
    they are what the headline spread compares.
    """
    s = pd.Series(values).dropna()
    n = len(s)
    if n < N_DECILES:
        return pd.Series(np.nan, index=pd.Series(values).index)

    sizes = [n // N_DECILES] * N_DECILES
    # Middle-out order: 5, 6, 4, 7, 3, 8, 2, 9, 1, 10 (zero-indexed).
    middle_first = [4, 5, 3, 6, 2, 7, 1, 8, 0, 9]
    for i in range(n % N_DECILES):
        sizes[middle_first[i]] += 1

    ranks = s.rank(method="average", ascending=higher_is_better)
    bounds = np.cumsum(sizes)
    out = pd.Series(np.nan, index=pd.Series(values).index)
    labels = np.arange(1, N_DECILES + 1)
    for label, upper in zip(labels, bounds):
        hit = (ranks <= upper) & out.reindex(ranks.index).isna()
        out.loc[ranks.index[hit.values]] = label
    return out


def bootstrap_ci(per_date_values, iters=BOOTSTRAP_ITERS, seed=SEED):
    """
    Percentile CI resampling REBALANCE DATES, not tickers.

    Each resampled date brings its whole cross-section. In a cross-sectional
    study the dominant dependence is that every name on one date shares the
    same market move, so resampling tickers would treat one bad quarter as
    hundreds of independent observations and give an interval far too narrow.
    """
    vals = np.asarray([v for v in per_date_values if np.isfinite(v)], dtype=float)
    n = len(vals)
    if n < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = vals[rng.integers(0, n, size=(iters, n))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def mde(per_date_values):
    vals = np.asarray([v for v in per_date_values if np.isfinite(v)], dtype=float)
    if len(vals) < 2:
        return np.nan
    return float(Z_POWER * vals.std(ddof=1) / np.sqrt(len(vals)))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_universe():
    df = pd.read_csv(OUTPUT_CSV)
    df["sector"] = df["sector"].fillna("(unknown)")
    return df


def load_month_end_closes(symbols):
    series = {}
    for symbol in symbols:
        path = price_path(symbol)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, parse_dates=["date"])
        if df.empty:
            continue
        closes = df.set_index("date")["close"].sort_index()
        series[symbol] = closes.resample("ME").last()
    panel = pd.DataFrame(series).sort_index()
    print(f"  month-end closes: {panel.shape[1]:,} symbols x "
          f"{panel.shape[0]} month-ends "
          f"({panel.index[0].date()} to {panel.index[-1].date()})")
    return panel


FIELDS = {
    "ebit": ("income", "EBIT"),
    "gross_profit": ("income", "Gross Profit"),
    "total_assets": ("balance", "Total Assets"),
    "total_debt": ("balance", "Total Debt"),
    "cash": ("balance", "Cash And Cash Equivalents"),
    "shares": ("balance", "Ordinary Shares Number"),
    "fcf": ("cashflow", "Free Cash Flow"),
}


def load_fundamentals(symbols):
    """{symbol: DataFrame indexed by fiscal period end, columns = FIELDS}."""
    out = {}
    for symbol in symbols:
        path = fundamental_path(symbol)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        rows = {}
        for field, (stmt, label) in FIELDS.items():
            block = (rec.get(stmt) or {}).get(label) or {}
            for period, value in block.items():
                rows.setdefault(period, {})[field] = value
        if not rows:
            continue
        df = pd.DataFrame(rows).T
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[df.index.notna()].sort_index()
        for field in FIELDS:
            if field not in df.columns:
                df[field] = np.nan
        out[symbol] = df[list(FIELDS)]
    print(f"  fundamentals: {len(out):,} symbols")
    return out


# ---------------------------------------------------------------------------
# Factor construction
# ---------------------------------------------------------------------------

def pick_period(df, as_of):
    """
    The most recent fiscal period ending at least FUNDAMENTAL_LAG_MONTHS before
    as_of. The lag runs from each ticker's OWN year end, not a shared calendar
    date -- verified necessary, since year ends in the universe fall in several
    different months.
    """
    cutoff = as_of - pd.DateOffset(months=FUNDAMENTAL_LAG_MONTHS)
    eligible = df.index[df.index <= cutoff]
    return eligible[-1] if len(eligible) else None


def build_panel(universe, closes, fundamentals):
    sectors = dict(zip(universe["symbol"], universe["sector"]))
    mdv = dict(zip(universe["symbol"], universe["median_dollar_volume"]))

    dates = closes.index
    max_h = max(HORIZONS.values())
    rows = []

    for i, date in enumerate(dates):
        if i < MOMENTUM_LOOKBACK or i + max_h >= len(dates):
            continue

        px_now = closes.iloc[i]
        px_skip = closes.iloc[i - MOMENTUM_SKIP]
        px_back = closes.iloc[i - MOMENTUM_LOOKBACK]
        momentum = px_skip / px_back - 1.0

        forwards = {h: closes.iloc[i + m] / px_now - 1.0
                    for h, m in HORIZONS.items()}

        is_fundamental_date = date.month == 12

        for symbol in closes.columns:
            price = px_now.get(symbol, np.nan)
            if not np.isfinite(price) or price <= 0:
                continue

            row = {
                "date": date,
                "symbol": symbol,
                "sector": sectors.get(symbol, "(unknown)"),
                "median_dollar_volume": mdv.get(symbol, np.nan),
                "momentum": momentum.get(symbol, np.nan),
            }
            for h in HORIZONS:
                row[f"fwd_{h}"] = forwards[h].get(symbol, np.nan)

            for col in ("ebit_ev", "fcf_ev", "gp_assets", "fcf_positive",
                        "dilution", "size"):
                row[col] = np.nan

            if is_fundamental_date and symbol in fundamentals:
                fund = fundamentals[symbol]
                period = pick_period(fund, date)
                if period is not None:
                    rec = fund.loc[period]
                    shares = rec["shares"]
                    if np.isfinite(shares) and shares > 0:
                        market_cap = shares * price
                        row["size"] = market_cap

                        debt, cash = rec["total_debt"], rec["cash"]
                        if np.isfinite(debt) and np.isfinite(cash):
                            ev = market_cap + debt - cash
                            if ev > 0:
                                # Negative EBIT/FCF are KEPT and rank at their
                                # raw value, which puts them below every
                                # profitable name. EV <= 0 is excluded: the
                                # ratio inverts there. See DESIGN.md.
                                if np.isfinite(rec["ebit"]):
                                    row["ebit_ev"] = rec["ebit"] / ev
                                if np.isfinite(rec["fcf"]):
                                    row["fcf_ev"] = rec["fcf"] / ev

                        # Dilution: the period closest to 3 years before,
                        # within a 200-day tolerance.
                        target = period - pd.DateOffset(years=DILUTION_YEARS)
                        gaps = (fund.index - target).days
                        near = np.where(np.abs(gaps) <= 200)[0]
                        if len(near):
                            past = fund.index[near[np.argmin(np.abs(gaps[near]))]]
                            old = fund.loc[past, "shares"]
                            if np.isfinite(old) and old > 0:
                                row["dilution"] = shares / old - 1.0

                    assets = rec["total_assets"]
                    if (np.isfinite(rec["gross_profit"]) and np.isfinite(assets)
                            and assets > 0):
                        row["gp_assets"] = rec["gross_profit"] / assets
                    if np.isfinite(rec["fcf"]):
                        row["fcf_positive"] = 1.0 if rec["fcf"] > 0 else 0.0

            rows.append(row)

    panel = pd.DataFrame(rows)
    print(f"  panel: {len(panel):,} (date, symbol) rows across "
          f"{panel['date'].nunique()} rebalance dates")
    return panel


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def eligible(panel, column, sector_excluded):
    sub = panel[panel[column].notna()]
    if sector_excluded:
        sub = sub[~sub["sector"].isin(SECTOR_EXCLUDED)]
    return sub


def per_date_results(sub, column, higher_is_better, horizon, binary):
    """One row per rebalance date: spread, group means, counts, IC."""
    out = []
    fwd = f"fwd_{horizon}"
    for date, group in sub.groupby("date"):
        group = group[group[fwd].notna()]
        if len(group) < N_DECILES:
            continue

        if binary:
            top = group[group[column] > 0][fwd]
            bottom = group[group[column] <= 0][fwd]
            n_top, n_bottom = len(top), len(bottom)
            decile_means = {}
        else:
            deciles = assign_deciles(group[column], higher_is_better)
            group = group.assign(decile=deciles.values)
            group = group[group["decile"].notna()]
            if group.empty:
                continue
            decile_means = group.groupby("decile")[fwd].mean().to_dict()
            top = group[group["decile"] == N_DECILES][fwd]
            bottom = group[group["decile"] == 1][fwd]
            n_top, n_bottom = len(top), len(bottom)

        if n_top == 0 or n_bottom == 0:
            continue

        out.append({
            "date": date,
            "n": len(group),
            "n_top": n_top,
            "n_bottom": n_bottom,
            "spread": (top.mean() - bottom.mean()) * 100.0,
            "ic": spearman(
                group[column] if higher_is_better else -group[column],
                group[fwd],
            ),
            **{f"d{int(k)}": v * 100.0 for k, v in decile_means.items()},
        })
    return pd.DataFrame(out)


def summarise_factor(sub, column, label, higher_is_better, binary, tag=""):
    print(f"\n  {label}{tag}")
    if sub.empty:
        print("      no eligible observations")
        return None

    results = {}
    for horizon in HORIZONS:
        res = per_date_results(sub, column, higher_is_better, horizon, binary)
        if res.empty:
            continue
        spreads = res["spread"].tolist()
        lo, hi = bootstrap_ci(spreads)
        results[horizon] = {
            "dates": len(res),
            "mean_n": res["n"].mean(),
            "min_top": res["n_top"].min(),
            "min_bottom": res["n_bottom"].min(),
            "spread": float(np.mean(spreads)),
            "ci_lo": lo,
            "ci_hi": hi,
            "ic": float(res["ic"].mean()),
            "mde": mde(spreads),
            "res": res,
        }

    if not results:
        print("      no horizon produced a usable spread")
        return None

    print(f"      {'horizon':<8} {'dates':>5} {'names':>7} {'spread':>9} "
          f"{'95% CI':>20} {'IC':>7} {'MDE':>8}")
    for horizon, r in results.items():
        marker = " <-- confirmatory" if horizon == CONFIRMATORY_HORIZON else ""
        print(f"      {horizon:<8} {r['dates']:>5} {r['mean_n']:>7.0f} "
              f"{r['spread']:>8.2f}pp "
              f"[{r['ci_lo']:>7.2f}, {r['ci_hi']:>7.2f}] "
              f"{r['ic']:>7.3f} {r['mde']:>7.2f}pp{marker}")
    return results


def print_decile_table(results, label):
    conf = results.get(CONFIRMATORY_HORIZON)
    if conf is None:
        return
    res = conf["res"]
    cols = [c for c in res.columns if c.startswith("d") and c[1:].isdigit()]
    if not cols:
        return
    cols = sorted(cols, key=lambda c: int(c[1:]))
    print(f"\n      decile means, {CONFIRMATORY_HORIZON} forward return "
          f"(averaged over {len(res)} dates) -- {label}")
    print(f"        {'decile':>7} {'fwd return':>12}")
    for col in cols:
        print(f"        {col[1:]:>7} {res[col].mean():>11.2f}pp")


def apply_criterion(results, label, confirmatory):
    print(f"\n  PRE-REGISTERED CRITERION -- {label}")
    if not confirmatory:
        print("      EXPLORATORY: ineligible to pass. No criterion applied.")
        print("      Reported as a described curiosity, not as evidence.")
        return
    conf = results.get(CONFIRMATORY_HORIZON) if results else None
    if conf is None:
        print("      no confirmatory-horizon result")
        return

    checks = [
        ("top-minus-bottom decile spread", True),
        (f"CI lower bound above zero ({conf['ci_lo']:.2f}pp)",
         conf["ci_lo"] > 0),
        (f"point estimate >= {PASS_THRESHOLD_PP} pp ({conf['spread']:.2f}pp)",
         conf["spread"] >= PASS_THRESHOLD_PP),
        (f"information coefficient positive ({conf['ic']:.3f})",
         conf["ic"] > 0),
        (f">= {MIN_PER_DECILE} names in every decile at every date "
         f"(min {min(conf['min_top'], conf['min_bottom'])})",
         min(conf["min_top"], conf["min_bottom"]) >= MIN_PER_DECILE),
        (f">= {MIN_DATES} rebalance dates ({conf['dates']})",
         conf["dates"] >= MIN_DATES),
    ]
    for text, ok in checks:
        print(f"      [{'PASS' if ok else 'FAIL'}] {text}")

    passed = all(ok for _, ok in checks)
    if passed:
        verdict = "1. PASS"
    elif conf["mde"] < PASS_THRESHOLD_PP:
        verdict = (f"2. INTERPRETABLE NULL -- realised MDE "
                   f"{conf['mde']:.2f}pp is BELOW the {PASS_THRESHOLD_PP}pp "
                   f"threshold, so the design could have seen an effect worth "
                   f"caring about and did not")
    else:
        verdict = (f"3. UNDERPOWERED -- realised MDE {conf['mde']:.2f}pp is "
                   f"ABOVE the {PASS_THRESHOLD_PP}pp threshold, so this study "
                   f"could not have detected an effect of that size")
    print(f"      OUTCOME: {verdict}")


def print_coverage(sub, column, label):
    if sub.empty:
        return
    counts = sub.groupby("date")[column].count()
    print(f"\n      coverage per date -- {label}")
    for date, n in counts.items():
        per_decile = n // N_DECILES
        flag = "   BELOW FLOOR" if per_decile < MIN_PER_DECILE else ""
        print(f"        {date.date()}  {n:>5} names  "
              f"~{per_decile:>3}/decile{flag}")


def print_sector_composition(sub, column, higher_is_better, label):
    """DESIGN.md step 5: a concentrated decile means a partial sector bet."""
    if sub.empty:
        return
    frames = []
    for _, group in sub.groupby("date"):
        deciles = assign_deciles(group[column], higher_is_better)
        frames.append(group.assign(decile=deciles.values))
    allg = pd.concat(frames)
    allg = allg[allg["decile"].isin([1, N_DECILES])]
    if allg.empty:
        return
    print(f"\n      sector composition of the extreme deciles -- {label}")
    print("      (diagnostic, no criterion; a dominated decile means the")
    print("       factor is partly a sector bet and FINDINGS.md must say so)")
    for decile in (N_DECILES, 1):
        part = allg[allg["decile"] == decile]
        if part.empty:
            continue
        share = part["sector"].value_counts(normalize=True) * 100
        top = ", ".join(f"{s} {p:.0f}%" for s, p in share.head(4).items())
        name = "D10 (attractive end)" if decile == N_DECILES else "D1"
        print(f"        {name:<22} {top}")
        if share.iloc[0] >= 40:
            print(f"        {'':22} CONCENTRATED: "
                  f"{share.index[0]} is {share.iloc[0]:.0f}% of this decile")


# ---------------------------------------------------------------------------

def run_factor(panel, column, label, higher_is_better, confirmatory,
               sector_excl, binary, liquidity_floor):
    print()
    print("=" * 72)
    print(f"{label}")
    print("=" * 72)
    if sector_excl:
        print(f"  sector exclusion applied: {', '.join(sorted(SECTOR_EXCLUDED))}")

    sub = eligible(panel, column, sector_excl)
    print_coverage(sub, column, label)

    results = summarise_factor(sub, column, label, higher_is_better, binary)
    if results:
        print_decile_table(results, label)
    apply_criterion(results, label, confirmatory)

    if not binary:
        print_sector_composition(sub, column, higher_is_better, label)

    # --- robustness 1: ex bottom liquidity quintile ------------------------
    liquid = sub[sub["median_dollar_volume"] >= liquidity_floor]
    dropped = len(sub) - len(liquid)
    print(f"\n  ROBUSTNESS -- excluding the bottom liquidity quintile "
          f"(< ${liquidity_floor / 1e6:.3f}M/day, {dropped:,} rows dropped)")
    summarise_factor(liquid, column, label, higher_is_better, binary,
                     tag="  [ex bottom liquidity quintile]")

    # --- robustness 2: positive-metric-only re-rank ------------------------
    if column in ("ebit_ev", "fcf_ev", "gp_assets"):
        positive = sub[sub[column] > 0]
        print(f"\n  ROBUSTNESS -- positive-metric names only "
              f"({len(positive):,} of {len(sub):,} rows)")
        summarise_factor(positive, column, label, higher_is_better, binary,
                         tag="  [positive metric only]")

    # --- robustness 3: non-overlapping annual momentum ---------------------
    if column == "momentum":
        annual = sub[sub["date"].dt.month == 12]
        print(f"\n  ROBUSTNESS -- non-overlapping annual rebalances only "
              f"({annual['date'].nunique()} dates)")
        summarise_factor(annual, column, label, higher_is_better, binary,
                         tag="  [non-overlapping annual]")


def main():
    print("=" * 72)
    print("FACTOR STUDY -- FACTOR CONSTRUCTION AND ANALYSIS")
    print("=" * 72)
    print("\n  Pre-registered in DESIGN.md before any of this ran.")
    print("  Momentum is the only factor eligible to pass.")
    print("  The decile is the unit of analysis. No name is a conclusion.")

    print("\n  loading...")
    universe = load_universe()
    print(f"  universe: {len(universe):,} symbols")
    closes = load_month_end_closes(universe["symbol"].astype(str).tolist())
    fundamentals = load_fundamentals(universe["symbol"].astype(str).tolist())

    liquidity_floor = float(
        np.percentile(universe["median_dollar_volume"].dropna(), 20))
    print(f"  bottom liquidity quintile boundary: "
          f"${liquidity_floor / 1e6:.3f}M/day")

    print("\n  building factor panel...")
    panel = build_panel(universe, closes, fundamentals)
    panel.to_csv(PANEL_CACHE, index=False)
    print(f"  cached to {PANEL_CACHE}")

    print("\n  rebalance dates per factor:")
    for column, label, _, _, _, _ in FACTORS:
        dates = panel.loc[panel[column].notna(), "date"]
        if dates.empty:
            print(f"      {label:<32} 0 dates")
        else:
            print(f"      {label:<32} {dates.nunique():>3} dates  "
                  f"{dates.min().date()} to {dates.max().date()}")

    for column, label, higher, confirmatory, sector_excl, binary in FACTORS:
        run_factor(panel, column, label, higher, confirmatory, sector_excl,
                   binary, liquidity_floor)

    print()
    print("=" * 72)
    print("REMINDER OF WHAT THIS CANNOT SUPPORT")
    print("=" * 72)
    print("""
  - No claim about any individual stock. The decile is the unit.
  - Size is CONFOUNDED, not merely underpowered: the universe is selected on
    today's market cap, so a size spread would appear even if the true premium
    were zero. See DESIGN.md Pitfall 4.
  - Value, quality and dilution rest on ~3 rebalance dates. Their MDE is many
    times the 3.0pp threshold, so they cannot produce an interpretable null
    either way.
  - Survivorship bias inflates every number, most of all in the cheap and
    distressed end where a value factor lives.
  - Momentum is biased DOWNWARD by the $10bn ceiling, which removes the
    window's biggest compounders. A positive result is therefore conservative;
    a null is harder to read.
  - Nothing here is a recommendation, and no change to any live system follows.
""")


if __name__ == "__main__":
    main()
