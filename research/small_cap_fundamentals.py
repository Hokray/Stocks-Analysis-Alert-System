"""Fundamentals pass over the sub-$2bn names from universe_market_caps.csv.

Not a ranking to buy from -- a filter to find which names are worth reading
about properly.
"""
import time
import pandas as pd
import yfinance as yf

IN_FILE = "research/universe_market_caps.csv"
OUT_FILE = "research/small_cap_fundamentals.csv"
MAX_MCAP = 2_000_000_000


def pick(df, names):
    """First matching row from a statement, newest first. None if absent."""
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            s = df.loc[n].dropna()
            if not s.empty:
                return s
    return None


def cagr(series, years=3):
    """Growth rate from oldest to newest available, annualised."""
    s = series.dropna()
    if len(s) < 2:
        return None
    new, old = float(s.iloc[0]), float(s.iloc[min(years, len(s) - 1)])
    if old <= 0:
        return None
    span = min(years, len(s) - 1)
    return ((new / old) ** (1 / span) - 1) * 100


def row_for(tk):
    t = yf.Ticker(tk)
    inc = t.income_stmt
    bal = t.balance_sheet
    cfs = t.cashflow

    rev = pick(inc, ["Total Revenue", "Operating Revenue"])
    ni = pick(inc, ["Net Income", "Net Income Common Stockholders"])
    shares = pick(bal, ["Ordinary Shares Number", "Share Issued"])
    cash = pick(bal, ["Cash And Cash Equivalents",
                      "Cash Cash Equivalents And Short Term Investments"])
    debt = pick(bal, ["Total Debt", "Long Term Debt"])
    fcf = pick(cfs, ["Free Cash Flow"])

    return {
        "ticker": tk,
        "revenue_m": round(float(rev.iloc[0]) / 1e6, 1) if rev is not None else None,
        "rev_cagr_3y_pct": round(cagr(rev), 1) if rev is not None and cagr(rev) is not None else None,
        "net_income_m": round(float(ni.iloc[0]) / 1e6, 1) if ni is not None else None,
        "fcf_m": round(float(fcf.iloc[0]) / 1e6, 1) if fcf is not None else None,
        "cash_m": round(float(cash.iloc[0]) / 1e6, 1) if cash is not None else None,
        "debt_m": round(float(debt.iloc[0]) / 1e6, 1) if debt is not None else None,
        # the dilution check: positive means more shares exist than 3y ago
        "share_growth_3y_pct": round(cagr(shares), 1) if shares is not None and cagr(shares) is not None else None,
    }


def main():
    caps = pd.read_csv(IN_FILE)
    small = caps[caps["market_cap"] < MAX_MCAP].copy()
    print(f"{len(small)} names under ${MAX_MCAP/1e9:.0f}bn\n")

    rows = []
    for i, tk in enumerate(small["ticker"], 1):
        try:
            rows.append(row_for(tk))
        except Exception as e:
            rows.append({"ticker": tk, "error": str(e)[:60]})
        print(f"  {i}/{len(small)}  {tk}")
        time.sleep(0.4)

    df = pd.DataFrame(rows).merge(
        small[["ticker", "market_cap_b"]], on="ticker", how="left")

    # cash burn years: how long the cash lasts at the current FCF rate
    df["years_of_cash"] = df.apply(
        lambda r: round(r["cash_m"] / abs(r["fcf_m"]), 1)
        if pd.notna(r.get("cash_m")) and pd.notna(r.get("fcf_m")) and r["fcf_m"] < 0
        else None, axis=1)

    cols = ["ticker", "market_cap_b", "revenue_m", "rev_cagr_3y_pct",
            "net_income_m", "fcf_m", "cash_m", "debt_m",
            "share_growth_3y_pct", "years_of_cash"]
    df = df.reindex(columns=cols).sort_values("rev_cagr_3y_pct", ascending=False)
    df.to_csv(OUT_FILE, index=False)
    print("\n" + df.to_string(index=False))


if __name__ == "__main__":
    main()