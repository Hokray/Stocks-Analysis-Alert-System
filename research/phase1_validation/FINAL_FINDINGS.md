# Findings

Summary of the four validation studies run against the screener, and what they
collectively establish.

**Conclusion: the screener has no demonstrated ability to select stocks that
outperform their sector.** Its most promising result — that stocks qualifying
persistently were better signals — turned out to be an artefact of how the
ticker universe was constructed, and reversed when tested on a universe chosen
without hindsight.

The system itself works. The strategy it implements does not.

---

## Contents

- [The hypothesis](#the-hypothesis)
- [The four studies](#the-four-studies)
- [Study 1: Backtest](#study-1-backtest)
- [Study 2: Significance testing](#study-2-significance-testing)
- [Study 3: Exit rules](#study-3-exit-rules)
- [Study 4: Universe bias test](#study-4-universe-bias-test)
- [The arc](#the-arc)
- [What was learned](#what-was-learned)
- [What the tool is now](#what-the-tool-is-now)
- [Open threads](#open-threads)
- [Verification](#verification)

---

## The hypothesis

Institutions accumulate positions over days rather than all at once. That
accumulation should be visible as **sustained, unusually high dollar volume
while the price rises** — money arriving, and buying rather than selling.

Encoded as three conditions, all of which must hold:

| # | Condition | Threshold |
|---|---|---|
| 1 | Dollar volume surge — 10-day average vs 63-day average | ≥ 1.50× |
| 2 | Price momentum over 10 trading days | ≥ +7% |
| 3 | TTM cash from operations | > 0 |

Tested across 60 AI-infrastructure tickers over 2023–2026.

---

## The four studies

| # | Study | Question | Answer |
|---|---|---|---|
| 1 | [Backtest](BACKTEST_RESULTS.md) | Do signals beat a date-matched sector baseline? | Marginally, and driven by 3 tickers |
| 2 | [Significance testing](SIGNIFICANCE_TESTING.md) | Is the measured edge distinguishable from luck? | No |
| 3 | [Exit rules](EXIT_RULES.md) | Does any exit strategy beat a fixed hold? | No |
| 4 | [Universe bias test](UNIVERSE_TEST.md) | Does the persistence effect survive a neutral universe? | **No — it reverses** |

---

## Study 1: Backtest

**Method.** Every historical date evaluated using only data available up to that
date. Forward returns at 5/10/20/30 days, compared against the average return of
the entire universe over the same window. Overlapping signals collapsed so one
sustained surge counts once.

**Headline result (20-day horizon, 493 signals):**

| Metric | Value |
|---|---|
| Mean return | 8.03% |
| **Median return** | **3.18%** |
| Baseline (universe average) | **5.49%** |
| Mean excess | +2.54pp |
| **Beat baseline** | **45.4%** |

**The mean was positive; almost everything else was not.** Fewer than half of
signals beat the baseline, and the median signal (3.18%) *underperformed* the
average stock (5.49%). The positive mean came entirely from distribution shape —
a few enormous winners against many small losses.

**Outlier dependence:**

| | Signals | Mean excess |
|---|---|---|
| All | 493 | +2.54pp |
| Excluding TSSI, BE, SNDK | 441 | **+0.39pp** |

**Three tickers out of sixty carried roughly 85% of the measured edge.**

**One promising result.** Splitting signals by how persistently a stock kept
qualifying:

| Persistence | Signals | Mean excess | Beat baseline |
|---|---|---|---|
| Brief (1–2 days) | 306 | +1.83pp | 43.1% |
| Very persistent (10+ days) | 123 | **+4.99pp** | **51.2%** |

The only segment crossing a 50% beat rate. This became the project's central
finding.

---

## Study 2: Significance testing

**Method.** Bootstrap resampling to estimate how much the result could move by
chance. Critically, **resampling by ticker rather than by individual signal** —
TSSI's 24 signals came from one stock in one period and are not 24 independent
observations.

**The method mattered:**

| Approach | 95% interval | Verdict |
|---|---|---|
| Naive (resample signals) | +0.31 to +4.89pp | Excludes zero — "real" |
| **Clustered (resample tickers)** | **−0.44 to +5.37pp** | **Includes zero** |

Same data, opposite conclusions. The base signal is **unproven** — not
disproven, but indistinguishable from luck.

**Persistence threshold sweep.** Every threshold from 2 to 14 tested. Values 7
through 11 formed a stable plateau: healthy sample sizes (111–152 signals), gaps
of 3.3–4.4pp, beat rates above 51%, and — importantly — a **positive median**,
which outliers cannot manufacture.

The script's automatic pick was threshold 14, which had the largest gap on just
29 signals and a confidence interval of −6.84 to +18.57pp. Rejected as noise;
`PERSISTENT_STREAK_MIN` was set to 8, in the middle of the plateau.

**Result: base signal unproven, persistence apparently robust.**

---

## Study 3: Exit rules

**Method.** Ten exit strategies simulated against historical signals — fixed
holds, volume decay, signal death, trailing stops, moving-average break. Each
trade compared against the universe return over **its own** entry-to-exit window,
since holding periods differ.

**On all signals, every median excess was negative.** Ten rules, no exceptions,
beat rates from 37% to 48%. No exit strategy rescued the base signal — the
weakness is in the entry.

**On persistent signals only, medians turned positive:**

| Rule | Median excess | Beat baseline | Mean drawdown |
|---|---|---|---|
| fixed_10 | **+2.65pp** | **54.7%** | −14.4% |
| fixed_30 | +3.22pp | 51.1% | −26.7% |
| fixed_60 | −0.52pp | 48.2% | −36.3% |

This appeared to be a third confirmation of the persistence effect.

**Two findings that stand independently of what followed:**

**Sophistication lost to a calendar.** `volume_decay` — exit when the money
stops arriving, the rule that follows directly from the thesis — had the *worst*
beat rate of all ten. The ratio compares a 10-day average to a 63-day average,
so it signals long after the move has ended.

**Drawdown is the practical constraint.** Every approach involved holding
through an average worst-loss of 14% to 36%. `fixed_60` had the highest mean
excess in the table (+17.73pp), a negative median, and a −36.3% average
drawdown — a strategy nobody would actually hold to completion.

---

## Study 4: Universe bias test

**The problem.** All three prior studies ran on 60 tickers hand-picked in 2026
because they are the recognisable names in AI infrastructure. Those companies are
recognisable *because they performed well over 2023–2026* — the exact period
being tested.

TSSI illustrates it: worth roughly $10M when first flagged in 2024, present in
the universe only because it grew ~100× by 2026, and the single largest
contributor to the measured edge.

**Method.** A 124-ticker control universe — the original 60 plus 64 selected
mechanically by category membership: thin-margin distributors, IT resellers,
declining consumer hardware, unrelated industrials, cash-burning speculatives,
and Intel. None chosen because they did well. Everything else held identical.

**Result:**

| Universe | Persistent signals | Excess | **Beat baseline** | Gap vs brief |
|---|---|---|---|---|
| Original 60 | 117 | **+6.92pp** | **53.0%** | +4.38 |
| **Newly added 64** | 88 | **−8.48pp** | **27.3%** | **−10.74** |

**The effect does not weaken. It inverts.**

**The obvious objection fails.** "The added companies are laggards, so they
underperform" is a real confound for absolute numbers — but not for the gap.
Within the added group alone: brief signals +2.26pp, persistent signals −8.48pp,
both against the same baseline. The 10.74-point gap is internal and survives.

**And it is statistically clear:**

| Group | Observed | 95% interval |
|---|---|---|
| Newly added, persistent | −8.48pp | **−13.11 to −4.36pp** |

Every earlier interval in this project straddled zero. This one does not. It is
the only statistically clear result produced anywhere here, and it points the
opposite way to the hypothesis.

---

## The arc

1. **Study 1** found a marginal edge and a promising persistence effect
2. **Study 2** showed the base edge was indistinguishable from luck, but
   persistence held across a stable plateau of thresholds
3. **Study 3** appeared to confirm persistence a third time, through entirely
   different machinery
4. **Study 4** showed all three agreed because they shared a biased sample

**The central methodological lesson:** consistency across multiple analyses of
the same flawed data is not corroboration. It demonstrates only that the flaw is
stable. Three analyses of a biased sample produce three biased results that
agree — and that agreement is actively misleading, because it feels like
mounting evidence while adding none.

Study 2 explicitly described the persistence effect as having "three independent
confirmations." They were not independent. Only changing the sample could reveal
that.

---

## What was learned

**About the strategy:**

- The three conditions have no demonstrated predictive power
- The apparent edge was ~85% attributable to three tickers
- The persistence effect was survivorship bias, and reverses under neutral
  selection
- No exit rule improves on a fixed hold
- Any version of this involves 14–36% average drawdowns while holding

**About method:**

- A date-matched baseline is essential; raw returns during a bull market are
  meaningless
- Clustered resampling gave an interval 1.3× wider than naive resampling and
  changed the conclusion
- Median before mean, always — the gap between them is diagnostic
- Removing the top contributors is a fast fragility test
- **Universe construction can create an effect that survives every other test**

**A bug worth recording.** The Study 4 interpretation logic checked only
`if lo_ci > 0` and defaulted everything else to "includes zero." It therefore
misreported the −13.11 to −4.36 interval — the most important number in the
project — as inconclusive. The assumption baked into that code was that a
significant result would be *positive*. That is precisely the optimism this
whole body of work exists to guard against.

---

## What the tool is now

**Still running, still useful, differently framed.**

The screener continues to operate daily: 60 tickers, three conditions, email
alerts, persistence tagging, run logging, failure alerts, weekly heartbeat.

**What it does:** narrows a universe to the handful of companies where unusual
amounts of money moved recently. That is a legitimate attention filter.

**What it does not do:** indicate those companies will outperform. The
persistence tier remains in the email as a *descriptive* label — how often a
stock qualified — and should not be read as signal strength. `PERSISTENT_STREAK_MIN`
retains the value chosen in Study 2, but that justification no longer holds.

---

## Open threads

**Out-of-sample data is accumulating.** Every live run since the schedule
stabilised produces signals the backtests never saw. The hypothesis to test in a
few months is now the *inverted* one: do persistent signals underperform going
forward, as Study 4 suggests?

**Transaction costs were never modelled.** Every result assumes free trading.
Given the largest winners were small caps with wide spreads, costs would make
the picture worse, not better.

**Point-in-time data would resolve what Study 4 could not.** Companies delisted
or acquired during 2023–2026 return no data from yfinance and are therefore
absent from both universes — six tickers failed to download in Study 4 alone,
including Chart Industries, acquired by Baker Hughes in July 2026. Genuine
failures remain invisible.

**A structurally different hypothesis** — insider buying from SEC Form 4
filings, for instance — would be a new research question rather than a variation
on a dead one. Retuning the current metrics on data already examined four times
would be searching for a false positive, and this project has unusually strong
grounds to know that.

---

## Verification

The logic producing these numbers is covered by **55 unit tests** (`pytest -q`),
run automatically in CI before every scheduled screener run. A failing test
stops the job, so a broken change cannot reach the alert emails or corrupt the
persistence history.

| Area | Tests |
|---|---|
| Dollar volume and price momentum | 8 |
| TTM cash flow extraction | 8 |
| Streak counting | 7 |
| Cooldown and history recording | 7 |
| Run log | 5 |
| Streak labels, near-misses, market cap | 12 |
| Weekly summary, weekday counting, config | 8 |

Three are worth naming:

**`test_no_lookahead_in_the_calculation`** truncates future data and asserts
today's metrics are unchanged. If that ever fails, every backtest result in this
repository is invalid.

**`test_qualifying_day_is_recorded_even_when_not_emailed`** locks in the design
decision that makes persistence tracking possible — a day inside the email
cooldown must still count toward the streak. Easy to break in a refactor, and
silent when broken.

**`test_runs_and_missing_days_reconcile`** pins the weekday-counting fix in the
weekly summary, where an earlier version counted weekend runs in the total while
the weekday they did not cover still appeared as missing.

**Writing the suite found a live bug.** `record_run` returned its untruncated
in-memory list while `save_run_log` wrote a capped one to disk, so the two
disagreed once the log passed its 400-entry limit. It would never have crashed
and never appeared in a log — it would simply have returned a wrong count some
eighteen months from now, with no trace of where the discrepancy came from.
That is the category of error tests exist to catch.

---

## Conclusion

The screener was built to detect where institutional capital concentrates, early
enough to act on. Four studies tested that claim.

It does not do this. The base signal cannot be distinguished from chance, the
apparent edge rested on three tickers, and the one finding that survived
repeated testing turned out to be an artefact of choosing a ticker list in
hindsight — reversing entirely when tested against companies selected without it.

The system works: it runs unattended, monitors itself, and reports honestly.
The hypothesis it was built to test does not hold.

**A test that changes what you would have done is worth more than one that
confirms what you already believed.** Study 4 was designed specifically to
attack the project's strongest finding, and the finding failed. That result
arrived before any money was committed to it.

---

*These results describe historical behaviour of a screening rule. They are not
investment advice and do not predict future returns.*