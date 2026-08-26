"""The purpose of this py file is to prove with historical data that our idea of the metrics
#actually shows that we can predict when a wave for a stock occurs"""

#What you're trying to prove

#The claim embedded in your screener is: "when these three conditions fire, the stock is more likely to keep rising than it otherwise would be."

#That's a testable prediction. Right now it's an assumption — reasonable-sounding, but unverified. The backtest checks whether history agrees.

#What the answer means

#If excess ≈ +6%: your three conditions genuinely identify better-than-average stocks. The screener works.

#If excess ≈ 0%: alerted stocks did exactly as well as randomly picking from your CSV. The screener adds nothing — you might as well buy the whole list.

#If excess is negative: the conditions systematically pick underperformers. Worth knowing.

