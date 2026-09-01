"""
Cross-asset regime analysis.

Every study so far has looked WITHIN the sector -- which stock beats which. This
looks at the level above: was capital moving into equities at all during each
period, or into gold and bonds instead?

The question it answers is not "which stock should I pick" but "does the
screener only work when the whole market is already rising?" Six quarters of
results showed metric separation swinging from +0.57 to -0.38 with no
stock-specific explanation. Market regime is the obvious candidate.

Assets tracked
--------------
    SPY   S&P 500 -- broad equities
    QQQ   Nasdaq 100 -- growth and tech, closest to the screener's universe
    GLD   Gold -- the classic risk-off destination
    TLT   20+ year Treasuries -- the other one
    UUP   US Dollar index -- rises when capital leaves risk assets
    HYG   High-yield corporate bonds -- credit risk appetite
    XLU   Utilities -- defensive equity, rises when investors stay in stocks
                       but get cautious

A crude but standard regime measure: equities minus safe havens. Positive means
capital favoured risk; negative means it favoured safety.

    python research/phase2_metric_search/markets_analysis.py
"""

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
CACHE_PATH = "cache/regime_history.pkl"

ASSETS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "GLD": "Gold",
    "TLT": "Long Treasuries",
    "UUP": "US Dollar",
    "HYG": "High-yield credit",
    "XLU": "Utilities",
}

RISK_ON = ["SPY", "QQQ", "HYG"]
RISK_OFF = ["GLD", "TLT", "UUP"]

PERIODS = [
    ("Mar-May 2024", "2024-03-01", "2024-05-31"),
    ("Jun-Aug 2024", "2024-06-01", "2024-08-31"),
    ("Sep-Nov 2024", "2024-09-01", "2024-11-30"),
    ("Dec-Feb 2024/25", "2024-12-01", "2025-02-28"),
    ("Mar-May 2025", "2025-03-01", "2025-05-31"),
    ("Jun-Aug 2025", "2025-06-01", "2025-08-31"),
    ("Sep-Nov 2025", "2025-09-01", "2025-11-30"),
    ("Dec-Feb 2025/26", "2025-12-01", "2026-02-28"),
    ("Mar-May 2026", "2026-03-01", "2026-05-31"),
]

# From multi_period_test.py -- share of the 178-ticker universe that rose 10%+,
# and how strongly 20-day volatility separated winners from non-winners.
SCREENER_RESULTS = {
    "Mar-May 2024": {"base_rate_pct": 39, "vol_separation": -0.38},
    "Jun-Aug 2024": {"base_rate_pct": 37, "vol_separation": 0.05},
    "Sep-Nov 2024": {"base_rate_pct": 72, "vol_separation": 0.51},
    "Mar-May 2025": {"base_rate_pct": 44, "vol_separation": 0.57},
    "Jun-Aug 2025": {"base_rate_pct": 63, "vol_separation": -0.10},
    "Sep-Nov 2025": {"base_rate_pct": 51, "vol_separation": 0.48},
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_prices():
    if os.path.exists(CACHE_PATH):
        print(f"Loading cached history from {CACHE_PATH}")
        return pd.read_pickle(CACHE_PATH)

    print(f"Downloading {len(ASSETS)} cross-asset ETFs...")
    os.makedirs("cache", exist_ok=True)
    data = yf.download(list(ASSETS), start="2023-09-01", interval="1d",
                       auto_adjust=True, group_by="ticker",
                       progress=True, threads=True)

    closes = {}
    for t in ASSETS:
        try:
            closes[t] = data[t]["Close"].dropna()
        except (KeyError, TypeError):
            print(f"  {t}: no data")
    df = pd.DataFrame(closes)
    df.to_pickle(CACHE_PATH)
    return df


def period_returns(prices, start, end):
    window = prices.loc[pd.Timestamp(start):pd.Timestamp(end)].dropna(how="all")
    if len(window) < 20:
        return None
    first = window.ffill().bfill().iloc[0]
    last = window.ffill().iloc[-1]
    return ((last / first - 1) * 100).round(2)


def regime_score(returns):
    """
    Equities minus safe havens, in percentage points.

    Positive: capital favoured risk assets over the quarter.
    Negative: it favoured gold, Treasuries and the dollar.

    Crude by design -- it is a directional summary, not a factor model.
    """
    on = [returns[t] for t in RISK_ON if t in returns and pd.notna(returns[t])]
    off = [returns[t] for t in RISK_OFF if t in returns and pd.notna(returns[t])]
    if not on or not off:
        return np.nan
    return round(np.mean(on) - np.mean(off), 2)


def label_regime(score):
    if pd.isna(score):
        return "?"
    if score >= 8:
        return "strong risk-on"
    if score >= 2:
        return "risk-on"
    if score > -2:
        return "mixed"
    if score > -8:
        return "risk-off"
    return "strong risk-off"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    prices = load_prices()
    print(f"\nAssets loaded: {', '.join(prices.columns)}")

    rows = []
    for label, start, end in PERIODS:
        r = period_returns(prices, start, end)
        if r is None:
            continue
        row = {"period": label}
        row.update({t: r.get(t, np.nan) for t in ASSETS})
        row["regime_score"] = regime_score(r)
        row["regime"] = label_regime(row["regime_score"])
        rows.append(row)

    df = pd.DataFrame(rows)

    print("\n" + "=" * 104)
    print("QUARTERLY RETURNS BY ASSET CLASS (%)")
    print("=" * 104 + "\n")
    print(df[["period"] + list(ASSETS) + ["regime_score", "regime"]]
          .to_string(index=False))

    print("""
  regime_score = mean(SPY, QQQ, HYG) - mean(GLD, TLT, UUP), in percentage
  points. Positive means capital favoured risk assets over safe havens.""")

    # ------------------------------------------------------------------
    # Rotation: when did gold and bonds beat equities outright?
    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("ROTATION -- quarters where safe havens outperformed equities")
    print("=" * 104 + "\n")

    rotated = df[df["regime_score"] < 0]
    if len(rotated):
        print(rotated[["period", "SPY", "QQQ", "GLD", "TLT",
                       "regime_score", "regime"]].to_string(index=False))
    else:
        print("  None. Equities beat safe havens in every quarter measured.")
        print("  Worth noting: 2024-2026 was a sustained equity bull market, so")
        print("  this sample contains few genuine risk-off periods. That limits")
        print("  what any regime comparison below can establish.")

    # ------------------------------------------------------------------
    # Does regime explain the screener's behaviour?
    # ------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("DOES REGIME EXPLAIN THE SCREENER'S RESULTS?")
    print("=" * 104 + "\n")

    merged = []
    for _, r in df.iterrows():
        s = SCREENER_RESULTS.get(r["period"])
        if not s:
            continue
        merged.append({
            "period": r["period"],
            "regime_score": r["regime_score"],
            "regime": r["regime"],
            "QQQ_pct": r.get("QQQ"),
            "base_rate_pct": s["base_rate_pct"],
            "vol_separation": s["vol_separation"],
        })

    m = pd.DataFrame(merged)
    if m.empty:
        print("  No overlapping periods.")
        return

    print(m.to_string(index=False))

    valid = m.dropna(subset=["regime_score", "base_rate_pct"])
    if len(valid) >= 4:
        c_base = valid["regime_score"].corr(valid["base_rate_pct"])
        c_qqq = valid["QQQ_pct"].corr(valid["base_rate_pct"])
        c_vol = valid["regime_score"].corr(valid["vol_separation"])

        print(f"""
  Correlation, regime score vs share of universe rising 10%+:  {c_base:+.2f}
  Correlation, QQQ return  vs share of universe rising 10%+:   {c_qqq:+.2f}
  Correlation, regime score vs volatility separation:          {c_vol:+.2f}

  With only {len(valid)} quarters these correlations are indicative at best.
  Four to six points can produce a correlation above 0.7 by chance routinely.""")

        if c_qqq > 0.6:
            print("""
  -> The share of the sector rising tracks the broad market closely. That is
     expected and not a finding: AI-infrastructure stocks are high-beta Nasdaq
     names, so when the Nasdaq rises most of them rise.

     The consequence for the screener is real though. Its hit rate is largely
     determined by market direction rather than by stock selection -- which is
     precisely why the date-matched baseline was necessary in every earlier
     study. Without it, the screener would have looked skilful simply for
     operating during a bull market.""")

        if abs(c_vol) > 0.5:
            print(f"""
  -> Volatility separation tracks the regime ({c_vol:+.2f}). In rising quarters
     volatile stocks led; in weaker ones they lagged. That is beta, not
     prediction -- high-volatility stocks amplify whatever the market does.

     This is the mechanical explanation for why the eight metrics from the
     two-period search failed across six periods: they were measuring beta
     during a rally, not a property that forecasts returns.""")

    df.to_csv(f"{RESULTS_DIR}/regime_analysis.csv", index=False)
    m.to_csv(f"{RESULTS_DIR}/regime_vs_screener.csv", index=False)
    print(f"\n\nWritten to {RESULTS_DIR}/")

    print("""
LIMITATIONS

Nine quarters, of which six overlap the screener results. Far too few for any
statistical claim -- this is descriptive.

2024-2026 was a sustained equity bull market. A sample with few genuine
risk-off quarters cannot establish how the screener behaves in one.

The regime score is a crude directional summary, not a factor model. Gold rose
strongly through this period for reasons largely unrelated to equity risk
appetite (central bank buying, currency debasement concerns), which weakens it
as a risk-off proxy here.

And the timing problem remains: asset classes reprice simultaneously. Observing
risk-off tells you what has already happened, not what is coming.
""")


if __name__ == "__main__":
    main()