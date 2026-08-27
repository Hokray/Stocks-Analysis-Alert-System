# Significance Testing

Follow-up to [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md). That analysis produced
a mean excess return of +2.54pp and a persistence effect that looked promising.
Neither number came with any measure of uncertainty.

This document answers two questions:

1. Is the measured edge distinguishable from luck?
2. Where should the persistence threshold actually sit?

**Summary:** the base signal is **unproven** — not disproven, but the data
cannot separate it from chance. The persistence effect is the most robust
pattern in the dataset and survives several checks that the base signal fails,
but it is also not statistically confirmed. One config change follows from this;
real confirmation requires out-of-sample data the live system is now collecting.

**`PERSISTENT_STREAK_MIN` changed from 4 to 8 on 8-27-2026.** All live signals from
this date forward constitute out-of-sample data for the prediction below.

---

## Contents

- [Why this was needed](#why-this-was-needed)
- [Method: clustered bootstrap](#method-clustered-bootstrap)
- [Result 1: the base signal is unproven](#result-1-the-base-signal-is-unproven)
- [Result 2: the persistence plateau](#result-2-the-persistence-plateau)
- [Result 3: the extreme threshold is a trap](#result-3-the-extreme-threshold-is-a-trap)
- [Decisions taken](#decisions-taken)
- [What would actually settle this](#what-would-actually-settle-this)
- [Reproducing](#reproducing)

---

## Why this was needed

A measured result of +2.54pp is meaningless without knowing how much it could
have moved by chance. A screener with **zero** skill does not produce exactly
0.00pp — it produces some scatter around zero. Sometimes +3pp, sometimes −2pp,
purely from which stocks happened to be in the sample.

So the question is not *"is the number positive?"* It is *"how often would a
skill-free screener produce a number this good?"*

---

## Method: clustered bootstrap

Resample the signals thousands of times and observe how much the result moves.
The 95% confidence interval is the range containing the middle 95% of those
resampled outcomes.

**The critical detail: resample by ticker, not by individual signal.**

TSSI contributed 24 signals — all from one stock, over one period, driven by one
underlying move. They are not 24 independent pieces of evidence. Treating them
as independent produces an interval that is far too narrow and makes a fragile
result look solid.

Resampling whole tickers keeps each stock's signals together. It asks the honest
question: *what if this universe had contained a different set of companies?*

The difference is not academic:

| Method | 95% interval | Verdict |
|---|---|---|
| Naive (resample signals) | +0.31pp to +4.89pp | Excludes zero — "real effect" |
| **Clustered (resample tickers)** | **−0.44pp to +5.37pp** | **Includes zero — inconclusive** |

Same data, opposite conclusions. The clustered interval is 1.3× wider, and that
width is the difference between an honest answer and a flattering one.

---

## Result 1: the base signal is unproven

**Observed:** +2.54pp mean excess return
**95% confidence interval:** −0.44pp to +5.37pp
**Share of resamples at or below zero:** 4.8%

The interval includes zero. The true edge could plausibly be slightly negative,
exactly zero, or as high as +5.37pp. This data cannot narrow it further.

**"Unproven" is the precise word.** Three distinct states are easy to confuse:

- *Proven to work* — strong evidence in favour. **Not this.**
- *Proven not to work* — strong evidence against. **Also not this.**
- *Unproven* — the evidence cannot distinguish between them. **This.**

Most of the interval is positive and 4.8% sits right at the conventional 5%
threshold, so the result leans favourable. It is simply not strong enough to
claim.

An analogy: a scale reading "between 68kg and 75kg" does tell you something —
you are not 100kg. But it cannot answer "did I lose weight this month?" The
instrument is not precise enough for the question being asked.

---

## Result 2: the persistence plateau

Every threshold from 2 to 14 was swept. For each, signals were split into those
with at least that many qualifying days in the prior 14, and those below.

| Threshold | n above | Excess above | Excess below | Gap | Beat baseline | **Median above** |
|---|---|---|---|---|---|---|
| 2 | 191 | 4.01 | 1.61 | 2.39 | 49.7% | −0.37 |
| 3 | 187 | 3.71 | 1.83 | 1.88 | 49.2% | −0.53 |
| 4 | 180 | 4.23 | 1.57 | 2.65 | 50.6% | +0.08 |
| 5 | 169 | 4.16 | 1.70 | 2.47 | 49.7% | −0.37 |
| 6 | 160 | 4.54 | 1.58 | 2.96 | 50.0% | −0.16 |
| **7** | **152** | **5.18** | **1.37** | **3.81** | **51.3%** | **+0.80** |
| **8** | **137** | **5.72** | **1.32** | **4.40** | **51.8%** | **+0.91** |
| **9** | **133** | **5.75** | **1.36** | **4.39** | **51.9%** | **+0.91** |
| **10** | **123** | **4.99** | **1.73** | **3.26** | **51.2%** | **+0.70** |
| **11** | **111** | **5.91** | **1.56** | **4.34** | **53.2%** | **+1.50** |
| 12 | 41 | 3.60 | 2.45 | 1.15 | 48.8% | −0.84 |
| 13 | 34 | 5.96 | 2.29 | 3.67 | 47.1% | −1.59 |
| 14 | 29 | 6.90 | 2.27 | 4.63 | 51.7% | +1.50 |

**Thresholds 7 through 11 form a stable plateau**, and this is the most
trustworthy finding in the project:

- Sample sizes remain healthy (111–152 signals)
- Gaps cluster tightly at 3.3–4.4pp
- Beat rates are the only ones consistently above 51%
- **The median excess turns positive at 7 and stays positive** — reaching +1.50
  at threshold 11

That last point carries the most weight. Medians are immune to outliers. Below
threshold 7 the median is negative, meaning the typical signal underperformed.
From 7 upward the typical signal outperforms. That is not the signature of two
or three lucky stocks.

**A result that holds across a range of nearby settings is far more credible
than one appearing at a single lucky value.** A plateau suggests a real
underlying effect; a spike suggests noise.

---

## Result 3: the extreme threshold is a trap

The sweep script selected threshold **14** because it produced the largest gap
(+4.63pp). That selection was wrong, and the reason is instructive.

At threshold 14 there are **29 signals**. Watch the numbers thrash as the sample
collapses:

| Threshold | n above | Excess above |
|---|---|---|
| 11 | 111 | +5.91 |
| 12 | 41 | +3.60 |
| 13 | 34 | +5.96 |
| 14 | 29 | +6.90 |

Swinging from 5.91 to 3.60 to 5.96 to 6.90 across adjacent thresholds is noise,
not signal. Real effects do not lurch like that.

Bootstrapping the threshold-14 group confirms it:

**Observed:** +6.90pp
**95% confidence interval:** **−6.84pp to +18.57pp**
**Share of resamples at or below zero:** 16.4%

An interval spanning 25 percentage points is a statement that the answer is
unknown. The cause is visible in the group's composition — 29 signals across 17
tickers, with a handful dominating:

| Ticker | Total excess contribution |
|---|---|
| SNDK | +141.7pp |
| BE | +99.3pp |
| PENG | +83.5pp |
| ALAB | +24.1pp |
| SMCI | +19.1pp |

SNDK alone drives most of it. Whether the bootstrap happens to include SNDK
determines the answer, which is precisely what a 25-point interval reflects.

**The lesson:** optimising for the best score selects the noisiest corner of the
data. The script maximised the gap without weighting sample size — a flaw in how
the sweep was written, and a good demonstration of how easily an automated
search finds an artefact.

---

## Decisions taken

**`PERSISTENT_STREAK_MIN`: 4 → 8**

The original value of 4 was chosen by intuition before any testing. Threshold 8
sits in the middle of the stable plateau with 137 signals above and 356 below —
healthy samples on both sides — and a median excess of +0.91.

Deliberately **not** 14, despite its higher score. Choosing the extreme value
that happened to win the search is the overfitting this analysis exists to
detect.

**`MIN_MARKET_CAP` stays at 0.** See BACKTEST_RESULTS.md, Result 4.

**Volume and price thresholds unchanged** at 1.50 and 7%. Nothing here justifies
moving them.

**How alerts should be read:**

- A first alert carries no demonstrated edge
- A signal that has qualified 8+ days out of the last 14 is the tier with
  whatever edge exists
- No claim that either is profitable

---

## What would actually settle this

**Out-of-sample validation, and it is already running.**

Everything above is **in-sample**: the same 2023–2026 data was examined, 13
thresholds were tried, and the best-looking one was selected. Seeing the answers
before choosing guarantees a good-looking result and proves nothing about
whether the pattern generalises.

**Out-of-sample** means data the analysis has never seen. Every scheduled run
from this point forward produces exactly that — signals on dates that did not
exist when the backtest was run, and therefore could not have been optimised
against.

The prediction to test, stated in advance:

> Among live signals, those with 8+ qualifying days in the prior 14 will beat
> the universe baseline more often than those with fewer.

After roughly three months there should be enough live signals to check it.

- **If it holds:** genuine confirmation, because it was predicted before the
  data existed.
- **If it does not:** the plateau was an artefact of examining one dataset too
  closely — which is itself worth knowing.

Two things no amount of resampling can fix:

- **Threshold selection bias.** Picking the best of 13 candidates and testing it
  on the same data overstates significance regardless of method.
- **Survivorship bias.** The universe was chosen in 2026 partly because these
  companies matter now. This inflates every result here, and the results were
  still weak.

---

## Reproducing

```bash
python backtest/backtest.py            # generate signals
python backtest/backtest_analysis.py   # add size and persistence buckets
python backtest/significance_testing.py
```

Outputs:

| File | Contents |
|---|---|
| `backtest_results/persistence_sweep.csv` | Full threshold sweep |
| `backtest_results/significance.csv` | Confidence intervals |

---

## Conclusion

The screener is not proven to work, and it is not proven not to work. On this
evidence:

- The base signal cannot be distinguished from chance
- Persistence is the strongest pattern available and survives the outlier and
  median checks that the base signal fails
- Neither reaches statistical confirmation
- The one actionable change is raising the persistence threshold from 4 to 8

**This is an honest inconclusive result, not a failure.** Knowing that a
strategy is unproven is more useful than believing an untested one works — and
the live system is now generating exactly the data needed to settle it.

---

*These results describe historical behaviour of a screening rule. They are not
investment advice and do not predict future returns.*