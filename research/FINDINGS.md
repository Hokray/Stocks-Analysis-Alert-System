# Findings — all nine studies

What was built, what was tested, and what the evidence supports. This is the
consolidated record across both research phases. Each study has its own
document with the full tables; this one carries the numbers that matter and the
reasoning that connects them.

**The short version.** The screener was built on the hypothesis that
institutions accumulate positions over days, and that this is visible as
sustained unusually high dollar volume while the price rises. Nine studies
tested that. The hypothesis does not hold: nothing here predicts which stocks
outperform their sector. Two promising findings were discovered, tested and
formally withdrawn — one was survivorship bias, one was a two-quarter
coincidence. One modest positive survived: a corrected, rewindowed volume
condition that detects *impending movement* in all six quarters tested, but
calls the *direction* only weakly. The live system runs unattended and is a
legitimate attention filter, not a stock picker.

---

## Contents

- [What was built](#what-was-built)
- [How to read the numbers](#how-to-read-the-numbers)
- [The nine studies](#the-nine-studies)
- [Phase 1 — Build and validate](#phase-1--build-and-validate)
  - [Study 1 — Backtest](#study-1--backtest)
  - [Study 2 — Significance testing](#study-2--significance-testing)
  - [Study 3 — Exit rules](#study-3--exit-rules)
  - [Study 4 — Universe bias](#study-4--universe-bias)
- [Phase 2 — Metric search](#phase-2--metric-search)
  - [Study 5 — Metric search](#study-5--metric-search)
  - [Study 6 — Volume timing](#study-6--volume-timing)
  - [Study 7 — Multi-period robustness](#study-7--multi-period-robustness)
  - [Study 8 — Cross-asset regime](#study-8--cross-asset-regime)
  - [Study 9 — Volume windows](#study-9--volume-windows)
- [The arc](#the-arc)
- [What was learned](#what-was-learned)
- [Configuration history](#configuration-history)
- [What has not been tested](#what-has-not-been-tested)
- [Limitations that apply to everything here](#limitations-that-apply-to-everything-here)
- [Open threads](#open-threads)

---

## What was built

A daily screener over AI-infrastructure equities. Three conditions, all
required:

| # | Condition | Original | Current |
|---|---|---|---|
| 1 | Dollar-volume surge — recent average ÷ baseline average | 10d ÷ 63d ≥ 1.50× | 10d ÷ preceding 30d ≥ 1.75× |
| 2 | Price change over 10 trading days | ≥ +7% | ≥ +7% |
| 3 | TTM cash from operations | > 0 | > 0 |

**Dollar volume, not share volume.** 2M shares of a $4 stock is $8M; 2M shares
of a $200 stock is $400M. The thesis was about money moving, so the metric
multiplies by price.

**Universe.** Six categories — Networking and Optics, Memory and Storage,
Servers and Compute, Data Center Cooling, Data Center Power Supply, Neo Cloud.
Sixty tickers were hand-picked in August 2026; 118 more were added
mechanically by category after Study 4 showed the original selection was
biased. The live screener now runs on all 178.

---

## How to read the numbers

Four conventions recur throughout, and the conclusions depend on them.

**Date-matched baseline.** Every signal is measured against the average forward
return of the whole universe *over the same dates*. A signal returning +8% in a
sector that returned +10% is a bad pick, not a good one. Without this, a
screener operating during a bull market looks skilful for doing nothing.
Study 8 later quantified why this was essential: the share of the universe
rising 10% correlates with the Nasdaq at **+0.83**.

**Median before mean.** The gap between them is diagnostic. A positive mean
with a negative median means a few enormous winners are carrying an average
that most individual signals fell short of. That pattern appears in almost
every table here.

**Clustered bootstrap.** Confidence intervals resample *tickers*, not
individual signals. TSSI contributed 24 signals from one stock over one move —
they are not 24 independent observations. Resampling signals rather than
tickers produced intervals 1.3× too narrow and, in Study 2, the opposite
conclusion.

**Signal deduplication.** Signals within 10 trading days of a prior signal for
the same ticker collapse into one event, so a two-week surge counts once rather
than ten times.

---

## The nine studies

| # | Study | Question | Answer |
|---|---|---|---|
| 1 | [Backtest](phase1_validation/BACKTEST_RESULTS.md) | Do signals beat a date-matched baseline? | Marginally; ~85% from three tickers |
| 2 | [Significance](phase1_validation/SIGNIFICANCE_TESTING_RESULTS.md) | Is that edge distinguishable from luck? | No — unproven |
| 3 | [Exit rules](phase1_validation/EXIT_RULES.md) | Does any exit beat a fixed hold? | No |
| 4 | [Universe bias](phase1_validation/UNIVERSE_TEST_RESULTS.md) | Does persistence survive a neutral universe? | **No — it reverses** |
| 5 | [Metric search](phase2_metric_search/METRICS_TESTED_RESULTS.md) | Do future winners look different beforehand? | Eight metrics, two periods |
| 6 | [Volume timing](phase2_metric_search/VOLUME_TIMING.md) | Does volume lead or lag the move? | Leads by ~2 days; precedes falls more |
| 7 | [Multi-period](phase2_metric_search/MULTI_PERIOD_TEST.md) | Do those eight hold in other quarters? | **No — zero of thirty-one** |
| 8 | [Cross-asset](phase2_metric_search/MARKETS_ANALYSIS.md) | Does market regime explain the failures? | No (+0.05) |
| 9 | [Volume windows](phase2_metric_search/VOLUME_WINDOW_VALIDATION.md) | Are the window lengths themselves wrong? | **Yes — and rewindowed it passes 6/6 quarters** |

Phase 1 summary: [phase1_validation/PHASE1_FINDINGS.md](phase1_validation/PHASE1_FINDINGS.md).

---

## Phase 1 — Build and validate

Three years of history (2023–2026) against the original 60-ticker universe.

### Study 1 — Backtest

Every historical date evaluated using only data available up to that date.
Forward returns at 5, 10, 20 and 30 trading days. 20 days is the reference
horizon.

**The headline, 493 signals at 20 days:**

| Metric | Value |
|---|---|
| Mean return | 8.03% |
| **Median return** | **3.18%** |
| Baseline (universe average) | **5.49%** |
| Mean excess | +2.54pp |
| **Beat baseline** | **45.4%** |

Excess return was positive at every horizon (+0.75 / +1.86 / +2.54 / +3.35pp),
which looks encouraging. It is not. **The beat rate is under 50% at every
horizon**, and the median signal (3.18%) *underperformed* the average stock
(5.49%). Best single signal +200.4%, worst −58.4%. The positive mean is
entirely distribution shape.

**Outlier dependence:**

| | Signals | Mean excess | Beat baseline |
|---|---|---|---|
| All signals | 493 | +2.54pp | 45.4% |
| Excluding TSSI, BE, SNDK | 441 | **+0.39pp** | 43.8% |

Three tickers out of sixty carried roughly **85%** of the measured edge (TSSI
+414.1pp, BE +351.0pp, SNDK +317.4pp of cumulative excess). Those three were
among the largest movers of the entire AI cycle. "The strategy works" and "the
strategy caught three of the biggest movers of the cycle" are different claims,
and only the second was supported.

**The promising result.** Bucketing by how many of the prior 14 trading days
also qualified:

| Persistence | Signals | Mean excess | Beat baseline |
|---|---|---|---|
| Brief (1–2 days) | 306 | +1.83pp | 43.1% |
| Building (3–5 days) | 27 | −1.22pp | 44.4% |
| Persistent (6–9 days) | 37 | +3.04pp | 45.9% |
| **Very persistent (10+ days)** | **123** | **+4.99pp** | **51.2%** |

The only segment anywhere in the analysis crossing a 50% beat rate. This became
the project's central finding — and Study 4 destroyed it.

**Two sub-results worth keeping.** The apparent small-cap edge was a mirage:
under $2B showed a mean excess of +11.67pp against a **median of −1.04pp** and
a 48.6% beat rate — a lottery-ticket distribution, not an edge. And the
strongest-looking category, Servers and Compute (+6.01pp over 87 signals), was
largely one ticker: TSSI alone supplied 24 of those 87.

### Study 2 — Significance testing

A measured +2.54pp means nothing without knowing how far it could move by
chance. The question is not "is the number positive?" but "how often would a
skill-free screener produce a number this good?"

**The method mattered more than the result:**

| Approach | 95% interval | Verdict |
|---|---|---|
| Naive (resample signals) | +0.31 to +4.89pp | Excludes zero — "real effect" |
| **Clustered (resample tickers)** | **−0.44 to +5.37pp** | **Includes zero — inconclusive** |

Same data, opposite conclusions. 4.8% of resamples landed at or below zero —
right at the conventional threshold, so the result leans favourable but cannot
be claimed. **"Unproven" is the precise word**: not proven to work, not proven
not to work.

**The persistence plateau.** Every threshold from 2 to 14 was swept.
Thresholds 7–11 formed a stable plateau: healthy samples (111–152 signals),
gaps clustered at 3.3–4.4pp, beat rates consistently above 51%, and — the part
that carried the most weight — **the median excess turns positive at 7 and
stays positive**, reaching +1.50 at 11. Outliers cannot manufacture a median.

**The trap that was avoided.** The sweep script selected threshold **14**,
which had the largest gap (+4.63pp) on **29 signals** and a confidence interval
of **−6.84 to +18.57pp**, with 16.4% of resamples at or below zero. Adjacent
thresholds thrashed between +5.91, +3.60,
+5.96 and +6.90 — noise, not signal. SNDK alone drove most of it. Threshold 8
was chosen instead, mid-plateau, explicitly rejecting the best-scoring value.
*Optimising for the best score selects the noisiest corner of the data.*

### Study 3 — Exit rules

Ten exit strategies against historical signals: fixed holds at 10/20/30/60
days, volume decay, signal death, trailing stops at 10/15/20%, and a 20-day
moving-average break. Each trade measured against the universe return over
**its own** entry-to-exit window, since holding periods differ.

**On all signals, every single median excess was negative** — ten rules, no
exceptions, beat rates from 37% to 48%. No exit rescued the base signal. The
weakness is in the entry.

**On persistent signals only (137 trades), medians turned positive:**

| Rule | Mean excess | Median excess | Beat baseline | Mean drawdown |
|---|---|---|---|---|
| **fixed_10** | +4.21 | **+2.65** | **54.7%** | **−14.4%** |
| fixed_30 | +6.78 | +3.22 | 51.1% | −26.7% |
| trailing_20 | +9.92 | +1.67 | 54.0% | −23.2% |
| fixed_60 | **+17.73** | **−0.52** | 48.2% | **−36.3%** |

This looked like a third independent confirmation of persistence. It was not
independent — see Study 4.

**Two findings that stand regardless.** *Sophistication lost to a calendar*:
`volume_decay` — exit when the money stops arriving, the rule following
directly from the project's own thesis — had the **worst** beat rate of all ten
(37.2%), because a 10-day-vs-63-day ratio only decays a week after the move has
ended. `signal_death` cut winners short at an average 6.6-day hold.

And *drawdown is the practical constraint*. `mean_max_dd_pct` — the worst loss
while still holding — ranged from −10.3% to −36.3%. `fixed_60` had the highest
mean excess in the table, a negative median, and a −36.3% average drawdown: a
backtest return nobody would actually collect, because nobody holds through
that. Even the best rule involves routinely watching a position fall 14%.

### Study 4 — Universe bias

**The most consequential study in the project.**

Every prior result ran on 60 tickers hand-picked in August 2026 because they
are the recognisable names in AI infrastructure. They are recognisable *because
they performed well over 2023–2026* — the exact period being backtested. The
scale was visible in the list itself: 42 of 60 were $10B+ companies and only 2
were small caps.

TSSI illustrates it. It was worth roughly $10M when the screener first flagged
it in 2024, and appears in the universe only because it grew ~100× by 2026.
Nobody building this list in 2023 would have included it — and it became the
single largest contributor to the measured edge.

**Method.** A 124-ticker control universe: the original 60 plus 64 selected
**mechanically by category membership** — thin-margin distributors (AVT, ARW,
SNX), IT resellers (CNXN, NSIT, PLUS), declining consumer hardware (NTGR),
unrelated industrials (AOS water heaters, MLI copper tube, FELE agricultural
pumps), cash-burning speculatives (PLUG, FCEL, SMR), Intel, and micro caps
nobody would list (OCC, DAIO, MRAM, QMCO). None chosen because they did well;
several chosen knowing they did badly. Everything else held identical.

**The result:**

| Universe | Persistent (8+) | Excess | Median | **Beat baseline** | **Gap vs brief** |
|---|---|---|---|---|---|
| Original 60 | 117 | **+6.92pp** | +1.31pp | **53.0%** | **+4.38** |
| **Newly added 64** | 88 | **−8.48pp** | −9.37pp | **27.3%** | **−10.74** |

**The effect does not weaken. It inverts.**

**The obvious objection fails.** "The added companies are laggards, so of
course they underperform" is a real confound for the absolute numbers — but not
for the gap. Within the added group alone: brief signals +2.26pp, persistent
signals −8.48pp, both against the same baseline, both drawn from the same
laggard companies. Any baseline distortion applies to both rows and cancels.
The 10.74-point gap is **internal**.

**And it is the only statistically clear result in the project:**

| Group | Signals | Observed | 95% interval |
|---|---|---|---|
| Control universe, persistent | 205 | +0.31pp | −4.44 to +5.28 |
| **Newly added, persistent** | **88** | **−8.48pp** | **−13.11 to −4.36** |

Every other interval produced anywhere here straddles zero. This one does not,
and it points the opposite way to the hypothesis.

**Why the earlier finding was wrong.** In a universe of companies selected
*because they rose*, a stock that keeps tripping the conditions is a stock in a
sustained rally — and you already know those rallies continued, because that is
why the company made the list. **Persistence was not detecting accumulation; it
was detecting membership in the winners' club.** The variable and the selection
criterion were measuring the same thing. In a neutral universe the same signal
reads as distribution or a crowded move approaching mean reversion, which is
what a 27.3% beat rate looks like.

**A bug in the test itself.** The interpretation logic checked only
`if lo_ci > 0` and defaulted everything else to "includes zero." It therefore
reported the −13.11 to −4.36 interval — the most important number in the
project — as inconclusive. The assumption baked into that code was that a
significant result would be *positive*, which is exactly the optimism this body
of work exists to guard against.

---

## Phase 2 — Metric search

Phase 1 established what does not work. Phase 2 asked what might, on the
expanded 178-ticker universe.

### Study 5 — Metric search

Thirty-one metrics across five families, each measured on the first trading day
of a period using only prior data, with stocks then labelled by whether they
rose 10% over the following three months. The reported figure is the
**separation** between winners and non-winners in pooled standard deviations.
A metric passes only by reaching 0.30 in *both* periods *and* pointing the same
direction. Periods: Sep–Nov 2024 and Sep–Nov 2025.

**Eight passed**, against a random-label baseline of 0.08:

| Metric | 2024 | 2025 | Family |
|---|---|---|---|
| `gap_freq_21` | +0.63 | +0.46 | Volatility |
| `volatility_60d_pct` | +0.62 | +0.45 | Volatility |
| `bollinger_width_pct` | +0.51 | +0.48 | Volatility |
| `volatility_20d_pct` | +0.51 | +0.48 | Volatility |
| `atr_pct` | +0.49 | +0.55 | Volatility |
| `ma50_vs_ma200` | +0.33 | +0.47 | Position in range |
| `pct_above_52w_low` | +0.34 | +0.44 | Position in range |
| `momentum_accel` | −0.44 | −0.32 | Momentum |

Together they describe a **pullback within an uptrend**: volatile, in an
established uptrend, recently cooling. Note `momentum_accel` is *negative* —
winners had 10-day momentum *below* their 21-day momentum. They were
decelerating.

**Two controls both behaved.** The mirror test re-ran every passing metric
against stocks that *fell* 10%; none separated fallers, and `momentum_accel`
flipped cleanly (−0.38 risers, +0.40 fallers), so these were directional rather
than general movement detectors. The permutation control shuffled labels and
re-ran the entire search 500 times: real labels 8 passes, random labels 0.08
average, 95th percentile 1, chance of 8+ by luck **0.0%**.

**Three findings that matter more than the eight.**

*No volume metric passed.* Not one of the eight came from the volume family —
the family containing the screener's own core condition. `vol_ratio_10_63`, the
live condition, scored −0.33 / +0.09. This was a fifth independent line of
evidence against the thesis, approached from the opposite direction: instead of
asking whether volume surges predict returns, it asked whether future winners
had volume surges. Same answer.

*One passing metric contradicts the screener directly.* The live screener
requires +7% momentum over 10 days. `momentum_accel` says winners were
decelerating. If that held, the entry condition points the wrong way.

*Eight passes is really three findings.* The permutation control assumes 31
independent tests. `atr_pct`, both volatility measures, `bollinger_width_pct`
and `gap_freq_21` are five ways of measuring how much a stock moves — like
recording height in inches, centimetres and feet. `pct_above_52w_low` and
`ma50_vs_ma200` both describe position in an uptrend. The honest count is
volatility, uptrend, deceleration.

The document closed by labelling itself **"hypothesis, not finding"** and
stating the prediction that Study 7 would go on to test. It also flagged the
caveat that mattered: in 2024, **121 of 168 tickers (72%) rose 10%+**, and only
9 fell, so "which stocks rose" barely discriminated and the 2024 mirror test
was nearly meaningless.

### Study 6 — Volume timing

Five studies had established that volume does not predict returns. None
explained *why*. This located every case where a stock began a 10%+ move over
10 trading days (2,199 up-moves, 1,683 down-moves, 516 random days), anchored
day 0 at the start, and averaged relative dollar volume from 20 days before to
20 days after.

**The control failed, and that is why it exists.** Random days came out at
**1.24×**, not 1.0 — sector-wide volume growth over 2023–2026 inflates any
window compared against its own past. All findings are therefore reported net
of the control. Without it, "volume was 1.50× normal before a move" would have
looked like a finding when 1.24× of it was just the sector getting busier.

**Volume leads — by two days, not two weeks:**

| Day | Up-moves | Random |
|---|---|---|
| −20 to −4 | 1.15 – 1.29 | 1.07 – 1.28 |
| **−2** | **2.18** | 1.27 |
| **−1** | **3.03** | 1.28 |
| 0 | 1.90 | 1.35 |

Days −20 through −4 are indistinguishable from normal. Two days do all the
work. **A two-day spike is not the signature of accumulation** — institutions
building over weeks would produce a gradual ramp. This looks like a discrete
event: earnings, an announcement, an analyst action.

**And it precedes falls more strongly than rises**, net of control:

| Period | Up-moves | **Down-moves** |
|---|---|---|
| Before (−10 to −1) | +0.26 | **+0.80** |
| Start (0 to +2) | +0.40 | **+1.26** |

Volume elevation before a 10% *fall* is roughly **three times larger** than
before a 10% rise. Elevated volume signals that something is about to happen,
not which way — and historically leans the wrong way.

**The screener could not see its own signal.** Around real 10% moves,
`vol_ratio_10_63` read 1.08 at day −10, 1.05 at day 0, and peaked at **1.13**
— against a trigger of **1.50**. The measurement window was five times longer
than the phenomenon, so a two-day surge averaged across ten days smoothed into
invisibility. This was not a threshold needing adjustment; the metric never
approached its own trigger even while the event it was built to detect was
occurring.

The study concluded volume should be removed from the screening logic. **Study 9
superseded that conclusion** — these figures were computed with a baseline that
overlapped the recent window, which capped the ratio and understated every
number here.

### Study 7 — Multi-period robustness

The identical metric search extended from two periods to **six
non-overlapping quarters** (Mar–May, Jun–Aug and Sep–Nov across 2024 and 2025),
with history pushed back to June 2022 to supply the 252-day lookbacks. Pass
criteria: same direction in **all six** periods and at least 0.30 SD in at
least four.

**0 of 31 metrics passed. 0 of the original 8.** `same_direction` was False for
every single metric — not one pointed the same way across all six quarters.

**The failure is reversal, not weakness.** The strongest of the eight,
20-day volatility:

| Period | Separation |
|---|---|
| Mar–May 2024 | **−0.38** |
| Jun–Aug 2024 | +0.05 |
| **Sep–Nov 2024** | **+0.51** |
| Mar–May 2025 | +0.57 |
| Jun–Aug 2025 | −0.10 |
| **Sep–Nov 2025** | **+0.48** |

All eight showed this: same-sized gaps, opposite directions, depending on the
quarter. A real effect does not reverse between adjacent quarters.

**It was an autumn artefact.** Averaging the two autumns against the four other
quarters, eleven metrics separate at 0.39–0.55 in autumn and essentially not at
all otherwise (+0.04 typical) — and all eight of the original finding are in
that list. But it is not a calendar effect either: the two springs have
*opposite* signs (volatility_20d −0.38 in 2024, +0.57 in 2025). No mechanism is
required. Two quarters out of six aligning is unremarkable, and the analysis
happened to begin with those two.

**How much stricter the six-period test is:** on pure random data, the
two-period criteria produce at least one false hit about 2% of the time; the
six-period criteria produced **zero across 200 simulated trials**.

**Volume confirmed dead a seventh time.** `vol_ratio_10_63` across the six
quarters: `+0.12, −0.01, −0.33, −0.05, −0.14, +0.09`. Signs scattered,
magnitudes near zero.

**What this prevented.** A second screener had been planned on those eight
metrics. This test ran first, specifically to check them, and killed the plan
before any code was written. Cost: one script.

### Study 8 — Cross-asset regime

Every prior study looked *within* the sector. This looked at the level above,
using seven ETFs as asset-class proxies (SPY, QQQ, HYG risk-on; GLD, TLT, UUP
risk-off; XLU defensive), with a deliberately crude regime score of
mean(SPY, QQQ, HYG) − mean(GLD, TLT, UUP) across nine quarters.

**The main purpose was to test one specific explanation** for Study 7's
failure: that volatile stocks amplify whatever the market does, so they lead in
rising quarters and lag in falling ones — which would make the eight metrics a
measure of beta rather than anything predictive.

**Correlation between regime score and volatility separation: +0.05.** Not
supported. Two quarters make the point directly: Jun–Aug 2025 was the
strongest risk-on quarter (+5.50, QQQ +9.14%) and volatility separation was
−0.10; Mar–May 2025 was merely mixed and separation was +0.57. If the effect
were beta-driven, the strong quarter should show strong separation. It shows the
opposite. The hypothesis was stated, tested and rejected — it would have been
easy to assert the beta story and never check.

**The durable finding is the other one.** The share of the universe rising 10%+
correlates with the Nasdaq at **+0.83** (and with the regime score at +0.63).
Nasdaq up 10%, roughly 70% of the universe clears 10%; Nasdaq up 1%, roughly
39% does. This is close to definitional — these are high-beta Nasdaq stocks —
but the consequence is real: **the screener's hit rate is mostly set by market
direction, not by its own logic.** A busy week means the sector rose. It also
retroactively justifies the date-matched baseline used in every other study.

**Where the rotation model breaks.** Four of nine quarters saw safe havens beat
equities, and Mar–May 2026 is textbook (Nasdaq +21.57%, gold −14.87%). But in
Sep–Nov 2025 *everything* rose at once — gold +19.13%, Nasdaq +9.61%,
Treasuries +6.10% — so the score labelled a perfectly healthy equity quarter
"risk-off". The model assumes a fixed pot being reallocated; that fails when
the pot grows. Gold also had its own drivers in this period (central bank
accumulation, debasement concerns), which weakens it as a risk-off proxy here.

### Study 9 — Volume windows

Prompted by a proposal to change the volume condition: recent window 10 → 5
days, baseline 63 → 20 days. **The proposal was half right, and the half that
was right was the half the author argued against.**

**The sweep.** Eleven recent/baseline pairs × four triggers across six
quarters. **Every one of the top six rows by edge kept `recent = 10`.** Not one
shorter recent window placed. There was also a dose-response at two of the
three baselines — a stricter trigger producing a larger edge, monotone at
baselines 30 and 63:

| baseline | 1.35 | 1.50 | 1.75 |
|---|---|---|---|
| 20 | 11.83 | 16.67 | 13.09 |
| 30 | 6.81 | 13.01 | **17.04** |
| 63 | — | 7.83 | 12.57 |

**The measurement bug.** The ratio was computed as
`dv.rolling(recent_n).mean() / dv.rolling(base_n).mean()` — so the baseline
*includes* the recent window, and the ratio is mathematically capped at
`base_n / recent_n`. Verified directly: with a 50× spike injected into the
recent window, the overlapping ratio at 10/20 tops out at **1.96** against a
ceiling of 2.0; with a separate baseline the same spike reaches **50.0**.

Recomputed with a separate baseline — the `base_n` days *ending* `recent_n`
days ago:

| Config | Baseline | Ceiling | Signals | Fire rate | Rise edge |
|---|---|---|---|---|---|
| 10/30 @ 1.75 | overlapping | 3.0 | 1,492 | 2.34% | +17.04pp |
| 10/30 @ 1.75 | **separate** | none | 5,569 | 8.74% | **+10.24pp** |
| 10/20 @ 1.50 | overlapping | 2.0 | 1,106 | 1.73% | +16.67pp |
| 10/20 @ 1.50 | **separate** | none | 9,424 | 14.77% | **+4.69pp** |

10/20's edge collapsed by **3.6×** — its apparent strength was largely the
ceiling restricting which days could fire. The live 10/63 pair had a ceiling of
6.3, well above its 1.50 trigger, so live behaviour was not distorted — but
every figure in Studies 1–8 understates the ratio, and the ceiling would have
started binding immediately on any shorter baseline.

**Volatility versus direction.** Measuring both sides for 10/30 @ 1.75: firing
raises the probability of a 10% rise by a factor of **1.58** (27.74% vs 17.51%
base) and of a 10% fall by **1.26** (11.92% vs 9.43%). Both go up — that is the
volatility component. Rises go up more — that is the directional component.
Conditioned on a large move happening at all, it calls the direction right
**69.94%** of the time against a **65.00%** base rate: a **+4.94pp** tilt.

**The pre-registered test.** Study 4 and Study 7 both died because an average
across quarters concealed a reversal, so the threshold was fixed *before*
running: positive edge in at least 5 of 6 quarters, worst quarter still above
zero, only the two pre-selected configurations tested, no re-sweeping
afterwards.

**10/30 @ 1.75 — rise edge by quarter:** +5.18, +10.81, +17.35, +2.17, +6.12,
+13.55. **6/6 positive, worst +2.17pp. PASS.**

**The asterisk that matters.** The *direction* edge by quarter was +3.87,
+13.96, +3.24, **−6.43**, **−3.28**, +3.49 — positive in only **4 of 6**. The
pre-registration was on rise edge, which the decomposition then showed to be a
blend. **The volatility component is stable across all six quarters; the
directional component is not.** What survived is a reliable detector of
impending movement carrying a directional tilt that reverses in two quarters —
worth having, and a smaller claim than the headline number suggests.

The 65/35 rise/fall split among large moves is itself inflated by survivorship
bias, which makes the directional figure the one most exposed to better data.

**The author's own error, recorded in the document.** Earlier in the
investigation he argued from the event study's spike shape that *shorter*
recent windows would work better, with arithmetic suggesting 3/63 or 2/63 would
fire where 10/63 does not. The sweep found the opposite. The spike shape was
measured correctly; the inference from it was wrong. A 2-day window catches the
spike but also catches every one-day news event that mean-reverts, whereas a
10-day window measures sustained elevation — a different and apparently more
informative phenomenon.

---

## The arc

1. **Study 1** found a marginal edge and a promising persistence effect
2. **Study 2** showed the base edge was indistinguishable from luck, but
   persistence held across a stable plateau of thresholds
3. **Study 3** appeared to confirm persistence a third time, through entirely
   different machinery
4. **Study 4** showed all three agreed because they shared a biased sample —
   **finding withdrawn**
5. **Study 5** found eight metrics separating future winners across two periods,
   with a clean permutation control
6. **Study 6** explained the mechanical reason volume never worked
7. **Study 7** extended Study 5 to six quarters: zero survived —
   **finding withdrawn**
8. **Study 8** tested and rejected the obvious explanation for why
9. **Study 9** found the measurement bug behind Studies 1–8, and on the
   corrected metric produced the project's one pre-registered positive

**The central methodological lesson, stated twice by the data.** Consistency
across multiple analyses of the same flawed sample is not corroboration — it
demonstrates only that the flaw is stable. Study 2 explicitly described
persistence as having "three independent confirmations"; they were not
independent. Both withdrawn findings failed the same way: a pattern that looked
robust because it had only been tested on one slice — one universe, one season,
one regime. **A finding tested on one slice has not been tested.**

---

## What was learned

**About the strategy**

- The original three conditions, as specified and combined, have no
  demonstrated ability to select stocks that outperform
- The apparent edge was ~85% attributable to three tickers
- Persistence was survivorship bias, and reverses under neutral selection
  (−8.48pp, CI −13.11 to −4.36)
- The eight Phase 2 metrics were a two-quarter coincidence
- No exit rule beats a fixed hold, and the two rules derived from the project's
  own thesis were among the worst
- Any version of this involves 14–36% average drawdowns while holding
- Volume spikes are brief (two days) and news-shaped, not the gradual ramp
  accumulation would produce — and they precede falls about three times more
  strongly than rises
- The screener's hit rate tracks the Nasdaq at +0.83; a busy week means the
  market rose
- **The one surviving positive:** the rewindowed volume condition
  (`10/30 @ 1.75`, non-overlapping baseline) detects impending movement in 6 of
  6 quarters, worst case +2.17pp, against a threshold fixed in advance. It calls
  direction only weakly (+4.94pp on a 65% base, positive in 4 of 6 quarters)

**About method**

- A **date-matched baseline** is essential; raw returns in a bull market are
  meaningless
- **Median before mean**, always — the gap between them is diagnostic
- **Clustered resampling** widened the interval 1.3× and changed the conclusion
- **Removing the top contributors** is a fast fragility test
- **Universe construction** can create an effect that survives every other test
- **Optimising for the best score** selects the noisiest corner of the data —
  threshold 14 had the largest gap and a 25-point confidence interval
- **Controls earn their keep.** Study 6's random-day control came back at 1.24
  instead of 1.0 and rescaled every number in the study
- **Pre-registration is the only defence** against a sweep that has already seen
  the answers, and it is what makes Study 9's result different in kind
- **Decompose a passing result before believing it.** 10/30's +10.24pp looked
  directional and was mostly volatility

**Two bugs worth recording**

The Study 4 interpretation logic checked only `if lo_ci > 0` and reported the
project's single statistically clear result as "includes zero" — a monitoring
script that only recognises the outcomes you expect will silently misreport the
ones you do not.

Writing the test suite found a live bug: `record_run` returned its untruncated
in-memory list while `save_run_log` wrote a capped one to disk, so the two
disagreed once the log passed its 400-entry limit. It would never have crashed
and never appeared in a log — it would simply have returned a wrong count
eighteen months later with no trace of where the discrepancy came from.

---

## Configuration history

Every change, and what justified it. The snapshot archive stores raw `close`
and `volume` for all 178 tickers daily, so any configuration — old or new — can
be recomputed retrospectively from it.

| Date | Change | Basis |
|---|---|---|
| 2026-08-27 | `PERSISTENT_STREAK_MIN` 4 → 8 | Study 2 threshold plateau. **Justification since withdrawn by Study 4**; the value remains, the tier is now descriptive only |
| 2026-08-27 | Schedule 08:37 → 21:15 UTC | Scheduled runs arriving up to 10h 37m late; three early runs read partial intraday bars |
| 2026-09-27 | `BASELINE_WINDOW_DAYS` 63 → 30 | Study 9 sweep |
| 2026-09-27 | `BASELINE_EXCLUDES_RECENT` added, `True` | Study 9 overlap bug |
| 2026-09-27 | `VOLUME_SURGE_THRESHOLD` 1.50 → 1.75 | Study 9 dose-response |
| 2026-09-27 | Universe 60 → 178 tickers | Study 4 selection bias |
| — | `RECENT_WINDOW_DAYS` unchanged at 10 | Study 9: every top configuration kept it at 10 |
| — | `MIN_MARKET_CAP` stays 0 | Study 1 Result 4: evidence for either setting is weak |
| — | No exit rule implemented | Study 3 |

---

## What has not been tested

Stated plainly, because these are the limits of every claim above.

**The current three-condition combination has never been backtested.** Study 9
tested the rewindowed volume condition *alone*. The live screener ANDs it with
price momentum and positive TTM cash flow, and that combination has not been
re-run since the 2026-09-27 change.

**The TTM cash-flow condition has never been backtested at all.** yfinance does
not provide historical quarterly statements far enough back, so every result
here reflects the two technical conditions only. No point-in-time fundamentals
are available.

**Transaction costs were never modelled.** Every figure assumes free trading.
The largest winners were small caps with wide spreads, so costs would make the
picture worse. Study 3 flags this as its single most important missing piece,
since the rules differ enormously in trade frequency.

**Out-of-sample validation has not happened yet.** It is accumulating: the
snapshot archive has recorded all 31 metrics for all 178 tickers every trading
day since 2026-08-26. That is the only clean test remaining, and it needs
elapsed time rather than more analysis.

---

## Limitations that apply to everything here

**Survivorship bias is reduced, not eliminated.** Companies delisted or
acquired during 2023–2026 return no data from yfinance, so genuine failures are
absent from *every* universe used here — including the control. Six tickers
failed to download in Study 4 (COMM, THR, GTLS, CSWI, BITF, GREE) and four in
the Phase 2 studies, among them Chart Industries, acquired by Baker Hughes in
July 2026. The control universe was also still enumerated by hand rather than
pulled from a full exchange listing. A paid point-in-time dataset with
historical index constituents is the correct instrument.

**One regime, one sector.** 2023–2026 was an unusual period dominated by a
single thematic buildout, and an equity bull market throughout. Nothing here
generalises to other sectors or conditions.

**Effective sample sizes are far below the headline counts.** Signals cluster in
time, forward windows overlap between adjacent days, and sector names move
together. Study 9's 5,569 signals plausibly represent independent events in the
tens, not the thousands.

**Base rates vary enormously** between periods — from 37% to 72% of the universe
rising 10% in a quarter. A period where 72% of stocks rose contributes less
information than its row suggests.

**Historical market caps are approximate.** Study 1's size buckets estimate size
as signal-date price × *current* share count, and several universe members
diluted heavily (IREN, WULF, BTDR).

---

## Open threads

**Out-of-sample validation.** Revisit once several months of live signals have
accumulated. Two predictions are on record and were stated before the data
existed: Study 2's (persistent signals beat the baseline more often) and
Study 4's inversion of it (they underperform). Study 4's evidence says to
expect the latter.

**Transaction costs.** Modelling them would make every result worse and is the
largest single gap.

**Insider buying (SEC Form 4).** The one remaining idea not derived from price
and volume, and therefore worth testing where another price transformation is
not. Retuning the current metrics on data already examined nine times would be
searching for a false positive, and this project has unusually strong grounds to
know it.

---

*These results describe historical behaviour of a screening rule. They are not
investment advice and do not predict future returns.*
