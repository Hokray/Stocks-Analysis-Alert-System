import config, screener, yfinance as yf

for sym in ["ANET", "AVGO", "MRVL", "GNRC", "P"]:
    h = yf.Ticker(sym).history(period=config.HISTORY_PERIOD, auto_adjust=True)
    m = screener.compute_price_and_volume(h)
    print(f"{sym:<6} {m['price_change']*100:+6.1f}%  vol {m['volume_ratio']:.2f}")