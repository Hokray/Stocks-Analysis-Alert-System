"""
AI-infrastructure stock screener.

Detects "rising waves" -- companies where dollar volume has surged above its own
normal level while price is climbing, filtered down to real businesses.

Run it:
    python screener.py

Set TEST_LIMIT in config.py to a small number first. Once the output looks
right, set it to None for the full universe.
"""

import csv
import json
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from dotenv import load_dotenv
load_dotenv()
import config
import notifier
import heartbeat_monitor as monitor
import snapshot

# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def load_universe():
    """Read tickers.csv into a list of dicts."""
    with open(config.TICKER_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if config.EXCHANGE_FILTER:
        rows = [r for r in rows if r["exchange"] in config.EXCHANGE_FILTER]

    if config.TEST_LIMIT:
        rows = rows[: config.TEST_LIMIT]

    return rows


# ---------------------------------------------------------------------------
# Fundamentals cache
#
# Cash from operations only changes once a quarter, so refetching it every day
# is wasted requests against a rate-limited API. Cache it for a week.
# ---------------------------------------------------------------------------

def load_cache():
    path = config.FUNDAMENTALS_CACHE_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache):
    path = config.FUNDAMENTALS_CACHE_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def cache_is_fresh(entry):
    if not entry or "fetched_at" not in entry:
        return False
    fetched = datetime.fromisoformat(entry["fetched_at"])
    return datetime.now() - fetched < timedelta(days=config.FUNDAMENTALS_CACHE_DAYS)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_price_and_volume(history):
    """
    Given a price history DataFrame, return the dollar-volume surge ratio and
    the price change over the recent window.

    Dollar volume = close price x shares traded. This is the whole point of the
    screener: it measures MONEY moving, not share count. 2M shares of a $4 stock
    is $8M; 2M shares of a $200 stock is $400M.
    """
    recent_n = config.RECENT_WINDOW_DAYS
    baseline_n = config.BASELINE_WINDOW_DAYS

    if len(history) < baseline_n + 1:
        return None  # not enough history to judge what "normal" looks like

    dollar_volume = history["Close"] * history["Volume"]

    recent_avg = dollar_volume.tail(recent_n).mean()
    baseline_avg = dollar_volume.tail(baseline_n).mean()

    if baseline_avg <= 0:
        return None

    price_now = history["Close"].iloc[-1]
    price_then = history["Close"].iloc[-recent_n]

    return {
        "volume_ratio": recent_avg / baseline_avg,
        "price_change": (price_now - price_then) / price_then,
        "recent_avg_dollar_volume": recent_avg,
        "baseline_avg_dollar_volume": baseline_avg,
        "price_now": price_now,
    }


def extract_ttm_cfo(ticker_obj):
    """
    Sum the last four quarters of cash from operations.

    yfinance has used different row labels across versions, so we look for any
    of the known variants rather than assuming one.
    """
    labels = [
        "Operating Cash Flow",
        "Total Cash From Operating Activities",
        "Cash Flow From Continuing Operating Activities",
    ]

    try:
        cf = ticker_obj.quarterly_cashflow
    except Exception:
        return None

    if cf is None or cf.empty:
        return None

    for label in labels:
        if label in cf.index:
            quarters = cf.loc[label].dropna()
            if len(quarters) >= 4:
                return float(quarters.iloc[:4].sum())
            if len(quarters) > 0:
                return None  # not enough quarters for a real TTM figure

    return None


def get_market_cap(ticker_obj):
    """
    Market cap. yfinance changed this key across versions, so try both,
    then fall back to shares x price, then to the heavier .info call.
    """
    try:
        fi = dict(ticker_obj.fast_info)
        for key in ("marketCap", "market_cap"):
            if fi.get(key):
                return float(fi[key])
        # Fallback: compute it ourselves
        shares = fi.get("shares")
        price = fi.get("lastPrice")
        if shares and price:
            return float(shares) * float(price)
    except Exception:
        pass

    try:
        cap = ticker_obj.info.get("marketCap")
        if cap:
            return float(cap)
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Per-ticker screening
# ---------------------------------------------------------------------------

def screen_ticker(row, cache):
    """Fetch and evaluate a single ticker. Returns a result dict, or None on failure."""
    symbol = row["ticker"]
    t = yf.Ticker(symbol)

    try:
        history = t.history(period=config.HISTORY_PERIOD, auto_adjust=True)
    except Exception as e:
        print(f"  {symbol}: price fetch failed ({e})")
        return None

    if history.empty:
        print(f"  {symbol}: no price data returned")
        return None

    metrics = compute_price_and_volume(history)
    if metrics is None:
        print(f"  {symbol}: not enough history")
        return None

    # Fundamentals, cached
    entry = cache.get(symbol)
    if cache_is_fresh(entry):
        ttm_cfo = entry["ttm_cfo"]
        market_cap = entry["market_cap"]
    else:
        ttm_cfo = extract_ttm_cfo(t)
        market_cap = get_market_cap(t)
        cache[symbol] = {
            "ttm_cfo": ttm_cfo,
            "market_cap": market_cap,
            "fetched_at": datetime.now().isoformat(),
        }

    # Apply the four conditions
    passed_volume = metrics["volume_ratio"] >= config.VOLUME_SURGE_THRESHOLD
    passed_price = metrics["price_change"] >= config.PRICE_CHANGE_THRESHOLD
    passed_cfo = (not config.REQUIRE_POSITIVE_TTM_CFO) or (
        ttm_cfo is not None and ttm_cfo > 0
    )
    passed_cap = (market_cap or 0) >= config.MIN_MARKET_CAP

    return {
        "ticker": symbol,
        "company": row["company_name"],
        "category": row["category"],
        "exchange": row["exchange"],
        "price": round(metrics["price_now"], 2),
        "price_change_pct": round(metrics["price_change"] * 100, 1),
        "volume_ratio": round(metrics["volume_ratio"], 2),
        "recent_dollar_vol_musd": round(metrics["recent_avg_dollar_volume"] / 1e6, 1),
        "ttm_cfo_musd": round(ttm_cfo / 1e6, 1) if ttm_cfo is not None else None,
        "market_cap_busd": round(market_cap / 1e9, 2) if market_cap else None,
        "pass_volume": passed_volume,
        "pass_price": passed_price,
        "pass_cfo": passed_cfo,
        "pass_cap": passed_cap,
        "MATCH": passed_volume and passed_price and passed_cfo and passed_cap,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    universe = load_universe()
    cache = load_cache()
    results = []

    print(f"Screening {len(universe)} tickers...\n")

    for i, row in enumerate(universe, 1):
        print(f"[{i}/{len(universe)}] {row['ticker']}")
        result = screen_ticker(row, cache)
        if result:
            results.append(result)
        time.sleep(config.REQUEST_DELAY_SECONDS)

    save_cache(cache)

    if not results:
        print("\nNo tickers returned usable data.")
        return

    df = pd.DataFrame(results)

    # Full diagnostic table -- shows every ticker and which conditions it passed
    print("\n" + "=" * 70)
    print("ALL RESULTS")
    print("=" * 70)
    print(
        df[
            [
                "ticker",
                "price",
                "price_change_pct",
                "volume_ratio",
                "recent_dollar_vol_musd",
                "ttm_cfo_musd",
                "market_cap_busd",
                "MATCH",
            ]
        ].to_string(index=False)
    )

    matches = df[df["MATCH"]].sort_values("volume_ratio", ascending=False)

    print("\n" + "=" * 70)
    print(f"MATCHES: {len(matches)}")
    print("=" * 70)

    if matches.empty:
        print("Nothing tripped all four conditions today.")
    else:
        for _, r in matches.iterrows():
            print(
                f"\n{r['ticker']} - {r['company']} ({r['category']})\n"
                f"  Price ${r['price']}, up {r['price_change_pct']}% "
                f"over {config.RECENT_WINDOW_DAYS} days\n"
                f"  Dollar volume {r['volume_ratio']}x its 3-month normal "
                f"(${r['recent_dollar_vol_musd']}M/day)\n"
                f"  Market cap ${r['market_cap_busd']}B, TTM CFO ${r['ttm_cfo_musd']}M"
            )

    df.to_csv("last_run_results.csv", index=False)
    print("\nFull results written to last_run_results.csv")

    # Log every run, whether or not anything matched and whether or not
    # email is enabled. This is what makes a skipped run distinguishable
    # from a quiet market.
    monitor.record_run(
        "ok",
        tickers_screened=len(results),
        matches=matches.to_dict("records"),
        near_misses=monitor.find_near_misses(df),
    )
    
    if config.SEND_EMAIL:
        notifier.notify(matches.to_dict("records"))
        monitor.record_run(
        "ok",
        tickers_screened=len(results),
        matches=matches.to_dict("records"),
        near_misses=monitor.find_near_misses(df),
    )

    if config.SEND_EMAIL:
        notifier.notify(matches.to_dict("records"))

    # Archive all metrics for all tickers. Slowest step, so it runs last --
    # a failure here must never delay or block the alert email.
    try:
        snapshot.take_snapshot()
    except Exception as e:
        print(f"Snapshot failed (non-fatal): {e}")
    
    


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        monitor.record_run("error", error=e)
        monitor.send_failure_alert(e)
        raise
    