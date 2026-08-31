# Exit Rules

Third validation study, after [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md) and
[SIGNIFICANCE_TESTING.md](SIGNIFICANCE_TESTING.md).

The screener identifies when to *look* at a stock. It says nothing about when to
stop. Ten exit rules were tested against historical signals to find out whether
any of them beat simply holding for a fixed period.

**Summary:** none did. Every signal-based and price-based exit underperformed a
plain calendar hold. The most useful output is not a rule but the drawdown
column, which quantifies how much pain each approach involves — a figure absent
from every earlier analysis.

A secondary result: the persistence finding held up again, in an analysis using
entirely different machinery. That is now three independent confirmations.

---

## Contents

- [Rules tested](#rules-tested)
- [Method](#method)
- [Result 1: on all signals, everything fails](#result-1-on-all-signals-everything-fails)
- [Result 2: on persistent signals, holding works](#result-2-on-persistent-signals-holding-works)
- [Result 3: the clever exits are the worst](#result-3-the-clever-exits-are-the-worst)
- [Result 4: fixed_60 is the trap](#result-4-fixed_60-is-the-trap)
- [Drawdown: the practical finding](#drawdown-the-practical-finding)
- [What this means for the project](#what-this-means-for-the-project)
- [Limitations](#limitations)
- [Reproducing](#reproducing)

---

## Rules tested

| Rule | Exit condition |
|---|---|
| `fixed_10/20/30/60` | Hold exactly N trading days |
| `volume_decay` | Dollar-volume ratio falls back below 1.0 |
| `signal_death` | Stock no longer meets both entry conditions |
| `trailing_10/15/20` | Price falls N% from its peak since entry |
| `ma20_break` | Close drops below its 20-day moving average |

All open-ended rules capped at 90 trading days.

`volume_decay` and `signal_death` are the two that follow directly from the
project's thesis: if the entry was justified by capital arriving, exit when it
stops.

---

## Method

Holding periods differ between rules, so raw returns are not comparable — a rule
holding 60 days gets three times the market exposure of one holding 20.

Each trade is therefore measured against **the universe's average return over
that trade's own entry-to-exit window**. A 60-day trade is compared against what
the average stock did over those same 60 days.

Each rule was run twice: across all signals, and across persistent signals only
(8 or more qualifying days in the prior 14, matching the live
`PERSISTENT_STREAK_MIN`).

`mean_max_dd_pct` records the worst peak-to-trough loss experienced **while
holding**, averaged across trades.

---

## Result 1: on all signals, everything fails

498 signals, 495 with sufficient forward data.

| Rule | Hold days | Mean excess | **Median excess** | Beat baseline | Mean drawdown |
|---|---|---|---|---|---|
| fixed_10 | 11.0 | +2.11 | **−0.51** | 48.1% | −12.5% |
| fixed_20 | 21.0 | +2.33 | **−2.30** | 44.0% | −17.9% |
| fixed_30 | 30.9 | +2.86 | **−1.47** | 44.6% | −21.9% |
| fixed_60 | 60.1 | +8.07 | **−5.09** | 42.8% | −30.4% |
| volume_decay | 28.1 | +3.92 | **−3.90** | 37.2% | −21.6% |
| signal_death | 6.6 | +1.59 | **−1.45** | 41.2% | −8.9% |
| trailing_10 | 19.8 | +1.31 | **−3.01** | 39.6% | −13.6% |
| trailing_15 | 31.4 | +4.14 | **−4.47** | 39.8% | −18.3% |
| trailing_20 | 43.5 | +5.99 | **−5.37** | 42.2% | −21.8% |
| ma20_break | 17.1 | +5.94 | **−2.99** | 38.6% | −14.4% |

**Every median is negative. Every beat rate is below 50%.**

The typical trade underperformed the universe baseline under all ten rules.
Means are positive, but the mean–median gaps are enormous — `fixed_60` shows
+8.07 mean against −5.09 median — the same outlier distortion documented in
BACKTEST_RESULTS.md Result 1.

**This independently confirms the base-signal problem.** No exit strategy
rescues it. The weakness is in the entry, not the exit, and no amount of exit
optimisation compensates for an entry that does not select well.

---

## Result 2: on persistent signals, holding works

Same rules, restricted to signals with 8+ qualifying days (137 trades).

| Rule | Hold days | Mean excess | **Median excess** | **Beat baseline** | Mean drawdown |
|---|---|---|---|---|---|
| **fixed_10** | 11.0 | +4.21 | **+2.65** | **54.7%** | **−14.4%** |
| fixed_20 | 21.0 | +5.54 | +0.91 | 50.4% | −21.4% |
| **fixed_30** | 31.0 | +6.78 | **+3.22** | 51.1% | −26.7% |
| fixed_60 | 60.0 | +17.73 | −0.52 | 48.2% | −36.3% |
| volume_decay | 31.4 | +8.06 | −2.37 | 44.5% | −27.5% |
| signal_death | 6.7 | +3.41 | −0.60 | 43.8% | −10.3% |
| trailing_10 | 14.0 | +5.17 | −0.96 | 48.2% | −14.0% |
| trailing_15 | 20.4 | +6.40 | −2.07 | 47.4% | −19.6% |
| **trailing_20** | 30.6 | +9.92 | **+1.67** | **54.0%** | −23.2% |
| ma20_break | 16.8 | +10.03 | −0.38 | 48.9% | −16.9% |

Medians turn positive. Beat rates cross 50%. Same stocks, same conditions — the
only change is the persistence filter.

**This is the third independent confirmation of the persistence effect**, after
the bucketed comparison and the threshold sweep. Different analysis, different
code, same direction. That consistency is worth more than any individual number.

**`fixed_10` has the best practical profile:** positive median, highest beat
rate, and the lowest drawdown of any rule with a positive median.

---

## Result 3: the clever exits are the worst

The two rules derived from the project's own thesis performed poorly.

**`volume_decay`** — sell when the dollar-volume ratio falls back below 1.0,
i.e. when the capital that justified entry stops arriving. It has the **worst
beat rate in Result 1** (37.2%) and a negative median in Result 2 (−2.37).

The mechanism is a lagging indicator. The ratio compares a 10-day average
against a 63-day average, so by the time the recent average has decayed below
baseline, the move has been over for a week or more.

**`signal_death`** — exit when the stock stops meeting both entry conditions.
Average hold of only 6.6 days. It cuts winners short: the price condition fails
as soon as the 10-day change slips under 7%, which happens routinely during
consolidation inside an ongoing move.

**Trailing stops and the moving-average break** also underperformed fixed holds
on median in both tables.

**The conclusion is uncomfortable but clear: sophistication lost to a
calendar.** The entry signal contains no useful exit information, and every
attempt to extract some produced worse results than ignoring it.

---

## Result 4: fixed_60 is the trap

`fixed_60` has the **highest mean excess in both tables** — +8.07 and +17.73.
Any process optimising on mean return selects it.

It is the worst available choice:

| Metric | fixed_60 (persistent) |
|---|---|
| Mean excess | **+17.73pp** — best in table |
| Median excess | **−0.52pp** — negative |
| Beat baseline | **48.2%** — below half |
| Mean drawdown | **−36.3%** — worst in table |

The typical trade *loses* to the baseline while a handful of giants carry the
average, and reaching that average requires holding through an average 36%
drawdown.

This is a compact illustration of why median is reported before mean throughout
this project.

---

## Drawdown: the practical finding

`mean_max_dd_pct` is the most useful column here and is absent from all earlier
analyses. It measures the worst loss experienced **while still holding**, not
the final result.

On persistent signals it ranges from **−10.3%** (`signal_death`) to **−36.3%**
(`fixed_60`).

**Why it matters more than return:** a backtest assumes the position is held to
the exit rule regardless of what happens in between. A rule averaging −36%
drawdown is one most people abandon partway through, which makes its backtest
return unachievable in practice. The number that matters is not what a strategy
returns but what it returns *for someone who actually follows it*.

Even the best-performing rule, `fixed_10`, involves an average worst-loss of
−14.4%. Routinely watching a position fall 14% before recovering is the real
cost of this approach, and it is the honest answer to "when should I sell?" —
the question is as much about tolerance as about timing.

---

## What this means for the project

**No exit rule will be implemented.** The screener remains an entry-detection
tool. This is a genuine negative result: a real question, tested properly, with
a clear answer.

**If a holding period is used at all, a short fixed one is the best-supported
choice.** `fixed_10` had the strongest risk-adjusted profile on persistent
signals. But the differences between fixed_10, fixed_20 and fixed_30 across 137
trades are almost certainly inside the noise band — the base signal's confidence
interval spanned −0.44pp to +5.37pp on 493 signals, so a 137-trade comparison
cannot separate +2.65 from +0.91. Treat this as "roughly 10–30 days, shorter for
less drawdown," not as a precise finding.

**The persistence filter is reinforced.** Three independent analyses now point
the same way. It remains the only part of the system with repeated support.

**No configuration changes follow from this study.**

---

## Limitations

**Ten rules on the same data.** One will look best by chance. The finding
reported here is the *negative* one — that nothing beat a fixed hold — which is
the direction least vulnerable to this problem. Any positive claim about a
specific rule would be far weaker.

**No transaction costs.** Rules differ enormously in trade frequency:
`signal_death` averages 6.6 days per trade, `fixed_60` averages 60. Costs would
penalise short-hold rules disproportionately and could reverse the `fixed_10`
advantage entirely. **This is the single most important missing piece.**

**No stop-losses on the fixed rules.** `fixed_60` holds through a −36% average
drawdown with no floor. Real position management would have intervened, which
means these figures do not describe how anyone would actually trade.

**Same in-sample data** as all prior studies, with the same survivorship bias.

**Averages hide distributions.** `mean_max_dd_pct` is an average; the worst
individual trades were far deeper. A distribution would be more informative than
a mean.

---

## Reproducing

```bash
python backtest/exit_rules.py
```

| Output | Contents |
|---|---|
| `backtest_results/exit_summary_all.csv` | Rule comparison, all signals |
| `backtest_results/exit_summary_persistent.csv` | Rule comparison, persistent only |
| `backtest_results/exit_trades_all.csv` | Every simulated trade |
| `backtest_results/exit_trades_persistent.csv` | Every simulated trade, persistent only |

---

## Conclusion

Ten exit strategies were tested and none beat simply holding for a fixed period.
The two rules derived from the project's own thesis — exiting when volume decays
or when the signal dies — were among the worst performers.

The entry signal carries no useful information about when to exit. Those are
separate problems, and this project solves only the first.

The most valuable output is the drawdown figure: any approach here involves
holding through losses of 14% to 36% on average. That, more than any return
number, determines whether a strategy is followable.

---

*These results describe historical behaviour of a screening rule. They are not
investment advice and do not predict future returns.*