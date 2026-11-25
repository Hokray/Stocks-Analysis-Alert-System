"""One-off: pull market caps for the universe and sort by size.

Writes research/universe_market_caps.csv so a follow-up script doesn't refetch.
"""
import time
import pandas as pd
import yfinance as yf

TICKER_FILE = "data/tickers_universe.csv"
OUT_FILE = "research/universe_market_caps.csv"

BANDS = [
    ("micro",             0,     300_000_000),
    ("small",   300_000_000,   2_000_000_000),
    ("mid",   2_000_000_000,  10_000_000_000),
    ("large", 10_000_000_000, 200_000_000_000),
    ("mega", 200_000_000_000, float("inf")),
]


def band(mc):
    for name, lo, hi in BANDS:
        if lo <= mc < hi:
            return name
    return "unknown"


def market_cap(ticker):
    """fast_info first, fall back to .info. None if neither works."""
    t = yf.Ticker(ticker)
    try:
        mc = t.fast_info.get("market_cap")
        if mc:
            return float(mc)
    except Exception:
        pass
    try:
        info = t.info
        # this repo has already been bitten once by market_cap -> marketCap
        mc = info.get("marketCap") or info.get("market_cap")
        return float(mc) if mc else None
    except Exception:
        return None


def main():
    raw = pd.read_csv(TICKER_FILE)
    col = "ticker" if "ticker" in raw.columns else raw.columns[0]
    tickers = raw[col].dropna().astype(str).str.strip().unique().tolist()
    print(f"{len(tickers)} tickers\n")

    rows, failed = [], []
    for i, tk in enumerate(tickers, 1):
        mc = market_cap(tk)
        if mc is None:
            failed.append(tk)
        else:
            rows.append({"ticker": tk, "market_cap": mc, "band": band(mc)})
        if i % 20 == 0:
            print(f"  {i}/{len(tickers)}")
        time.sleep(0.2)

    df = pd.DataFrame(rows).sort_values("market_cap").reset_index(drop=True)
    df["market_cap_b"] = (df["market_cap"] / 1e9).round(3)
    df.to_csv(OUT_FILE, index=False)

    print(f"\nResolved {len(df)}, failed {len(failed)}: {failed}\n")
    counts = df["band"].value_counts()
    for name, _, _ in BANDS:
        print(f"  {name:<6} {counts.get(name, 0)}")
    print("\nSmallest 25:")
    print(df[["ticker", "market_cap_b", "band"]].head(25).to_string(index=False))


if __name__ == "__main__":
    main()