# Universe Bias Test

Fourth and most consequential validation study, after
[BACKTEST_RESULTS.md](BACKTEST_RESULTS.md),
[SIGNIFICANCE_TESTING.md](SIGNIFICANCE_TESTING.md) and
[EXIT_RULES.md](EXIT_RULES.md).

**Result: the persistence effect does not survive. It reverses.**

The one finding this project had repeatedly supported turned out to be an
artefact of how the ticker list was built. On a universe selected without
hindsight, signals that qualified persistently **underperformed** — with the
only statistically clear confidence interval produced anywhere in this project,
and it points the wrong way.

---

## Contents

- [Why this test was run](#why-this-test-was-run)
- [The control universe](#the-control-universe)
- [Result 1: the persistence effect reverses](#result-1-the-persistence-effect-reverses)
- [Result 2: the obvious objection does not hold](#result-2-the-obvious-objection-does-not-hold)
- [Result 3: the only statistically clear result in the project](#result-3-the-only-statistically-clear-result-in-the-project)
- [Why the earlier finding was wrong](#why-the-earlier-finding-was-wrong)
- [A bug found in the test itself](#a-bug-found-in-the-test-itself)
- [What this changes](#what-this-changes)
- [Limitations](#limitations)
- [Why this study matters](#why-this-study-matters)
- [Reproducing](#reproducing)

---

## Why this test was run

Every prior result in this project was produced on 60 tickers hand-picked in
August 2026 because they are the recognisable names in AI infrastructure.

Those companies are recognisable **because they performed well over
2023–2026** — the exact period the backtests covered. That is survivorship bias,
and it should inflate every finding.

The scale of the problem was visible in the list itself: 42 of the 60 were $10B+
companies, and only 2 were small caps. Selection was never explicitly on market
cap, but it was on prominence, and prominence correlates almost perfectly with
having grown.

The clearest illustration is TSSI. It was worth roughly $10M when the screener
first flagged it in 2024. It appears in the universe only because it grew
roughly 100× by 2026. Nobody constructing this list in 2023 would have included
it. That ticker entered the sample purely through hindsight — and it went on to
become the single largest contributor to the measured edge.

Survivorship bias was documented as a limitation in all three previous studies.
This test measures it rather than noting it.

---

## The control universe

124 tickers: the original 60, plus 64 chosen **mechanically by category
membership** rather than by prominence.

The additions are deliberately unremarkable:

| Type | Examples |
|---|---|
| Thin-margin distributors | AVT, ARW, SNX, SCSC |
| IT resellers | CNXN, NSIT, PLUS |
| Declining consumer hardware | NTGR |
| Unrelated industrials | AOS (water heaters), MLI (copper tube), FELE (agricultural pumps) |
| Cash-burning speculatives | PLUG, FCEL, SMR |
| Major underperformers | INTC |
| Micro caps nobody would list | OCC, DAIO, MRAM, QMCO |

None were selected because they did well. Several were selected knowing they did
badly.

**Everything else was held identical** — same three conditions, same thresholds,
same 3-year window, same date-matched baseline, same signal deduplication, same
clustered bootstrap.

118 of 124 tickers returned usable data. Six did not: COMM, THR, GTLS, CSWI,
BITF, GREE.

---

## Result 1: the persistence effect reverses

| Universe | Signals | Mean excess | Median excess | Beat baseline |
|---|---|---|---|---|
| Control universe (all 124) | 906 | +1.93pp | −2.16pp | 43.9% |
| — original 60 | 493 | +3.58pp | −0.89pp | 47.7% |
| — **newly added 64** | 413 | **−0.03pp** | **−4.13pp** | **39.5%** |

Now the persistence split, which is the finding this project had built on:

| Universe | Persistent (8+) | Persistent excess | Persistent median | **Persistent beat rate** | Brief excess | **Gap** |
|---|---|---|---|---|---|---|
| Control (all 124) | 205 | +0.31pp | −3.91pp | 42.0% | +2.41pp | **−2.10** |
| — original 60 | 117 | **+6.92pp** | +1.31pp | **53.0%** | +2.54pp | **+4.38** |
| — **newly added 64** | 88 | **−8.48pp** | −9.37pp | **27.3%** | +2.26pp | **−10.74** |

Same conditions. Same code. Same period. Same baseline.

On the hand-picked universe, persistence helps: +4.38pp gap, 53% beat rate.

On the mechanically-selected universe, persistence **actively hurts**: −10.74pp
gap, and a 27.3% beat rate — barely one signal in four beating the baseline.

The effect does not weaken. It inverts.

---

## Result 2: the obvious objection does not hold

The immediate objection: *"the added companies are laggards, so of course they
underperform a baseline that includes the winners."*

That is a genuine confound for the overall numbers in the first table. It does
**not** touch the persistence finding, and the reason matters.

Compare within the added group only:

| Group | Excess | Beat baseline |
|---|---|---|
| Brief signals | **+2.26pp** | 42.8% |
| Persistent signals | **−8.48pp** | 27.3% |

Both measured against the same baseline. Both drawn from the same laggard
companies. Any distortion from the baseline containing winners applies equally
to both rows and cancels out.

The 10.74-point gap between them is **internal to the added universe**. It is
not a statement that these companies are worse — it is a statement that *among
these companies, the ones that kept qualifying did substantially worse than the
ones that flashed once.*

That is the exact reversal of the project's central finding.

---

## Result 3: the only statistically clear result in the project

Clustered bootstrap on the persistent group, resampling by ticker:

| Group | Signals | Observed | 95% interval | Verdict |
|---|---|---|---|---|
| Control universe | 205 | +0.31pp | −4.44 to +5.28 | Includes zero |
| **Newly added only** | 88 | **−8.48pp** | **−13.11 to −4.36** | **Entirely negative** |

Every previous confidence interval in this project straddled zero. This one does
not.

It is the first — and so far only — statistically clear result produced here,
and it says that persistent signals in a neutrally-selected universe are
associated with **underperformance**.

---

## Why the earlier finding was wrong

The mechanism is now visible, and it is instructive.

In a universe of companies selected *because they rose over 2023–2026*, a stock
that keeps tripping the conditions is a stock in a sustained rally. And you
already know those rallies continued — that is precisely why the company made
the list in the first place.

**Persistence was not detecting institutional accumulation. It was detecting
membership in the winners' club.** The variable and the selection criterion were
measuring the same thing.

In a neutral universe, a sustained volume surge means something different: a
stock being distributed into, or a crowded move approaching mean reversion. The
27.3% beat rate is consistent with that reading.

### The methodological lesson

SIGNIFICANCE_TESTING.md described the persistence effect as having **three
independent confirmations** — the bucketed comparison, the threshold sweep, and
the exit-rules analysis.

They were not independent. All three ran on the same biased sample.

**Consistency across multiple analyses of the same flawed data is not
corroboration.** It only demonstrates that the flaw is stable. Three analyses of
a biased sample produce three biased results that agree with each other, and
that agreement is actively misleading — it feels like mounting evidence while
adding none.

The only way to detect this was to change the sample.

---

## A bug found in the test itself

The script reported "Includes zero. Cannot distinguish from luck" for the
newly-added group, whose interval was −13.11 to −4.36 — entirely below zero.

The interpretation logic only checked `if lo_ci > 0` and defaulted everything
else to "includes zero." It had no branch for an interval that excludes zero on
the *negative* side, because a negative significant result was not anticipated.

**The bug hid the single most important number in the study.** Worth recording
for two reasons: a monitoring script that only recognises the outcomes you
expect will silently misreport the ones you do not, and the assumption baked
into that code — that a significant result would be positive — is the same
optimism this entire body of work exists to guard against.

---

## What this changes

**The persistence finding is withdrawn.** It was the project's only supported
result across three studies, and it does not survive a change of universe.

**`PERSISTENT_STREAK_MIN = 8` has lost its justification.** That value was
selected from the threshold sweep in SIGNIFICANCE_TESTING.md, which ran on the
biased universe. The persistence tier remains in the email as a descriptive
label — it reports how often a stock qualified — but it should no longer be read
as indicating a stronger signal.

**The base signal looks worse than previously measured.** On the added 64:
−0.03pp mean, −4.13pp median, 39.5% beat rate. Approximately nothing, tilting
negative.

**Prior documents are not deleted.** BACKTEST_RESULTS.md and
SIGNIFICANCE_TESTING.md remain as written, with pointers to this file. The
sequence of being wrong and finding out is the substance of the work, not an
embarrassment to be tidied away.

**The out-of-sample collection continues**, now testing an inverted hypothesis:
whether persistent signals in live data underperform. If the negative effect
here is real, it should appear going forward too.

---

## Limitations

**Six tickers returned no data** — COMM, THR, GTLS, CSWI, BITF, GREE. These are
delistings and acquisitions, and their absence is a small live demonstration of
the one bias this test *cannot* fix.

**Failures remain invisible in both universes.** Companies that were delisted or
acquired at a loss during 2023–2026 return no data from yfinance. Genuine
failures are absent from the control universe too, so it is less biased, not
unbiased.

**The control universe was still enumerated by hand.** It was built from what
could be listed by category rather than pulled programmatically from a full
exchange listing. Some selection bias survives. A paid point-in-time dataset
with historical index constituents would be the correct instrument.

**The persistence window differs slightly.** This script uses a 10-trading-day
rolling count; other scripts use 14 calendar days. The two are roughly
equivalent, and the measure is identical *within* this comparison, so the
reversal stands. Absolute numbers are not directly comparable to earlier
documents.

**Same period, same regime.** 2023–2026 remains one unusual market environment.

---

## Why this study matters

This is the most valuable result the project has produced.

A test was designed specifically to attack its own strongest finding — and the
finding failed. That is what quantitative research consists of, and it is the
step most people never take.

The failure mode it guards against is a comfortable one. The persistence effect
was plausible: it had a mechanism, it matched intuition, it appeared across
three separate analyses, and the numbers moved in the expected direction. Every
signal said *stop here, you have found something.* Continuing past that point,
building a test whose only possible outcomes were "no new information" or "your
best result was wrong," is the part that required deliberate effort.

Most backtests never face this test. Most published strategies are constructed
on universes chosen with hindsight, and the bias is noted in a limitations
section rather than measured. Noting a limitation costs nothing. Measuring it
cost this project its central finding.

**The practical outcome is worth stating plainly: this test ran before any money
was committed.** The persistence tier was days away from being treated as an
actionable signal. A test that changes what you would have done is worth more
than one that confirms what you already believed.

---

## Reproducing

```bash
python backtest/universe_test.py
```

| File | Contents |
|---|---|
| `data/tickers_control.csv` | 124-ticker control universe with `in_original` flag |
| `backtest_results/control_signals.csv` | Every signal with excess return and persistence count |

---

## Conclusion

The persistence effect was survivorship bias.

On a universe selected without hindsight it reverses — persistent signals
underperformed by 8.48pp with a confidence interval entirely below zero, the
only statistically clear result this project has produced.

Three prior analyses agreed with each other because they shared a flawed sample,
not because they independently confirmed anything. That is the central
methodological lesson here, and it generalises well beyond this project.

The screener has no demonstrated ability to select stocks that outperform. It
remains a functioning attention filter — it narrows a universe to where unusual
money moved — and nothing more.

---

*These results describe historical behaviour of a screening rule. They are not
investment advice and do not predict future returns.*