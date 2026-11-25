# Factor Study — Findings

Systematic factor research over 2,477 US-listed common stocks, $100m–$10bn,
November 2021 to November 2026. Pre-registered in
[DESIGN.md](DESIGN.md) before any factor was computed.

**This is not a recommendation engine, not a buy list and not a set of top
picks.** The decile is the unit of analysis. No individual name below is a
conclusion about that name.

---

## Verdict

| | |
|---|---|
| **Momentum** (the only confirmatory factor) | **Outcome 3 — underpowered.** Realised MDE 18.83pp against a 3.0pp threshold. The criterion also failed on *sign*: the spread is −56.82pp, not positive. |
| **Value, quality, size** | Exploratory. Ineligible to pass. Two usable rebalance dates, not the ~3 estimated. |
| **Dilution** | **Zero observations.** Structurally impossible with the available statement depth. |
| **The substantive finding** | Every factor's *unattractive* decile outperformed its attractive one, and in every case a handful of names produced the gap. The study measures survivorship and outlier concentration, not factor premia. |

The one-sentence version: **the pre-registered statistic did not survive contact
with this universe**, and that is a more useful result than anything the factors
themselves produced.

---

## Contents

- [Finding 1: the unattractive decile won, everywhere, on a handful of names](#finding-1-the-unattractive-decile-won-everywhere-on-a-handful-of-names)
- [Finding 2: momentum, the confirmatory test](#finding-2-momentum-the-confirmatory-test)
- [Finding 3: the fundamental data is thinner than pre-registered](#finding-3-the-fundamental-data-is-thinner-than-pre-registered)
- [Finding 4: the value factor is a sector bet](#finding-4-the-value-factor-is-a-sector-bet)
- [The tempting number, and why it is not reported as a result](#the-tempting-number-and-why-it-is-not-reported-as-a-result)
- [Three pre-registration flaws, and the corrected wording](#three-pre-registration-flaws-and-the-corrected-wording)
- [What this study cannot support](#what-this-study-cannot-support)
- [Reproduction](#reproduction)
- [Defects and open items](#defects-and-open-items)

---

## Finding 1: the unattractive decile won, everywhere, on a handful of names

This is the headline, and it is one finding rather than five, because the same
mechanism produces every factor's result.

### The mean-median divergence is the evidence

The pre-registered statistic is the equal-weighted mean forward return within
decile. For momentum at the confirmatory 12-month horizon:

| statistic | D10 − D1 spread |
|---|---|
| **mean — pre-registered** | **−56.82pp** |
| median — post-hoc | **−6.18pp** |
| 99%-winsorised mean — post-hoc | −36.23pp |

**A 9× gap between the mean and the median is not a footnote about estimator
choice. It is the evidence that the result is artefactual**, and it is reported
here as a substantive finding. The median and winsorised figures were computed
*after* seeing the result and are labelled post-hoc throughout; the mean remains
the primary number because that is what was pre-registered.

### The concentration, measured

Within decile 1 at the 12-month horizon, averaged across the 36 rebalance dates:

- **the single largest name contributes 25% of the decile's total return**
- **the largest five names contribute 52%**, out of roughly 223 names per decile

The largest 12-month forward return in the panel is **+24,890pp**. The nine
largest all belong to one ticker, whose monthly closes span $0.088 to $29.22 — a
330× range. A second name spans 73×.

**These appear to be genuine moves rather than defective price adjustments.**
Inspecting the thirty largest forward returns by name gives a coherent and
recognisable cohort from the 2023–2025 small-cap market — quantum computing
(`RGTI`, `QBTS`, `QUBT`), AI-datacenter infrastructure (`TSSI`), fintech
turnarounds (`SEZL`, `DAVE`, `ROOT`), drones (`RCAT`) and a long tail of
biotech (`WGS`, `DRUG`, `RLMD`, `TNGX`). A contaminated sample would not
cluster by theme and date the way this one does. The names are listed here as
data provenance — evidence about where the numbers came from — and not as names
of interest.

The residual uncertainty is narrower than the original one: the exact
magnitudes are unverified, and some rebalance dates post-date any independent
check available here. See
[defects and open items](#defects-and-open-items).

### The distribution is right-skewed, which is a second and separate problem

Per rebalance date, the share of names returning more than +500% over the
following 12 months averages **0.63%** — a mean of 14.6 names out of ~2,314,
ranging from **0.00%** (2023-06-30) to **1.97%** (2025-05-31, 47 of 2,385).

Roughly one name in 160, then, not one in sixteen. **The driver is the
magnitude of the tail, not its frequency**: ~1.5 such names land in an average
231-name decile, and returns reaching +24,890pp move a 231-name mean by tens of
points on their own. That is what the concentration figures above measure
directly.

So an equal-weighted mean is **the wrong summary statistic for this
distribution**, independently of which names are present. It is a
count of lottery tickets, and it will be unstable under any resampling.

### The information coefficient gives the artefact away

For momentum at 12 months the IC is **−0.009** while the spread is −56.82pp.
Those two numbers are nearly incompatible. A genuine cross-sectional reversal
would produce a clearly negative rank correlation; an IC indistinguishable from
zero beside a 57-point extreme-decile gap means **there is no gradient across
the ranking** — one bucket is an outlier, not the end of a trend.

The decile table confirms it. Deciles 4 through 10 sit inside a 7.5-point band:

| decile | 12m forward return |
|---|---|
| **1** — worst past return | **+80.99pp** |
| 2 | +31.09pp |
| 3 | +21.70pp |
| 4 | +19.16pp |
| 5 | +17.36pp |
| 6 | +16.68pp |
| 7 | +17.69pp |
| 8 | +17.56pp |
| 9 | +18.74pp |
| **10** — best past return | **+24.16pp** |

### The pattern is uniform across every factor

Dropping the invalid date (see [Finding 3](#finding-3-the-fundamental-data-is-thinner-than-pre-registered)),
every factor shows the same signature — a large negative mean spread, a median
three to six times smaller, and a negative IC:

| factor | mean spread | median — post-hoc | mean ÷ median |
|---|---|---|---|
| Value: EBIT/EV | −61.49pp | −17.99pp | 3.4× |
| Value: FCF/EV | −62.64pp | −19.43pp | 3.2× |
| Quality: gross profit/assets | −51.35pp | −14.06pp | 3.7× |
| Quality: positive FCF | −45.18pp | −7.99pp | 5.7× |
| Size: market cap | −157.62pp | −41.82pp | 3.8× |
| Momentum (36 dates) | −56.82pp | −6.18pp | 9.2× |

Five factors measuring different things cannot all be wrong in the same
direction by the same mechanism unless something common to the data is driving
them. The common thing is which names are present and which few of them moved.

### Two independent reasons the −56.82pp is not a momentum measurement

These compound rather than substitute, and the write-up keeps both:

1. **The sample is missing the names that delisted.** Decile 1 holds only the
   catastrophic decliners that survived to November 2026. This is a problem
   about *which rows exist* — see the mechanism below.
2. **The equal-weighted mean is the wrong summary for a right-skewed
   distribution.** This is a problem about *how the existing rows are
   aggregated*, and it would remain even with a perfect survivorship-free
   universe.

Fixing either one alone would not rescue the figure. Point-in-time constituent
data would repair the sample and leave the estimator mismatch untouched; a
robust estimator would repair the summary and still be computed over a
survivor-only sample. The −56.82pp spread is not a momentum premium under
either reading.

### The mechanism behind reason 1 is the one Pitfall 1 predicted

[DESIGN.md Pitfall 1](DESIGN.md#pitfall-1-survivorship-bias) committed in
advance to the direction: survivorship bias "inflates measured returns, and it
inflates them most in the cheap and distressed bucket." That is exactly what
appears, and the reason is mechanical.

The universe was built from companies listed in **November 2026**. The losers
decile therefore contains only the names that fell hard **and did not
subsequently delist, go bankrupt or get taken under**. Those that did are
absent. What remains in decile 1 is a selected set of survivors of a decline —
a population whose expected forward return is upward-biased by construction,
and whose right tail is populated by the handful that went from near-zero to
multiples of it.

The same logic applies to the expensive end of value: a loss-making
pre-revenue biotech with negative EBIT ranks in decile 1, and the ones still
listed in 2026 are the ones that did not fail.

**This is not correctable here.** It needs point-in-time constituent data. The
forward archive that would have accumulated survivorship-free data from the day
it started was specified and then dropped from the plan, which Pitfall 1 records
as leaving the bias with no remediation path.

---

## Finding 2: momentum, the confirmatory test

```
horizon  dates  names    spread          95% CI        IC      MDE
1m          36   2237    -4.70pp  [ -7.42,  -2.21]   0.005   3.84pp
3m          36   2237   -15.07pp  [-21.27,  -9.68]   0.005   8.49pp
6m          36   2237   -26.76pp  [-34.57, -19.35]   0.011  11.05pp
12m         36   2237   -56.82pp  [-70.12, -43.82]  -0.009  18.83pp  <- confirmatory
```

### The criterion, condition by condition

| condition | result |
|---|---|
| top-minus-bottom decile spread | PASS — the quantity is as specified |
| CI lower bound above zero | **FAIL** — −70.12pp |
| point estimate ≥ +3.0pp | **FAIL** — −56.82pp |
| information coefficient positive | **FAIL** — −0.009 |
| ≥ 30 names in every decile at every date | PASS — minimum 215 |
| ≥ 12 rebalance dates | PASS — 36 |

**Outcome 3 — underpowered**, because the realised MDE of 18.83pp exceeds the
3.0pp threshold.

That label is literally correct and actively misleading, and the fault is in the
pre-registration rather than the data. The design cannot resolve a 3pp effect at
this dispersion, *and* it observed a 57pp one whose interval excludes zero. Both
statements are true at once and the three-outcome scheme has no slot for the
combination. Recorded as
[flaw 1](#flaw-1-no-outcome-for-significant-in-the-wrong-direction).

### Rebalance dates: 36, not the 48 assumed

Price history begins 2021-11-26 for 2,166 of the 2,477 names. A 12-1 rank needs
13 months behind it and the confirmatory horizon needs 12 months ahead, so the
usable window is **2022-12-31 to 2025-11-30 — 36 monthly rebalances**, at 215 to
234 names per decile. Both floors clear. DESIGN.md's MDE table was corrected for
this before the run.

### The liquidity robustness check did its job

| | 12m spread | 95% CI | MDE | median — post-hoc |
|---|---|---|---|---|
| all names | −56.82pp | [−70.12, −43.82] | 18.83pp | −6.18pp |
| **ex bottom liquidity quintile** (< $1.013M/day) | **−32.64pp** | [−42.52, −23.61] | 13.52pp | −4.00pp |

Excluding the least liquid fifth cuts the spread by **43%**. The reversal
survives in direction but not in magnitude, which means a substantial part of it
lives in names that barely trade.

**This was only visible because liquidity was stored as a field rather than
imposed as a funnel threshold.** A strict floor in the universe builder would
have removed most of the effect and reported a smaller, cleaner number with no
indication that the threshold was doing the work. The permissive $100k floor
plus the bottom-quintile re-run is what turned a hidden parameter choice into a
reported result.

### The non-overlapping annual check

| | dates | 12m spread | 95% CI | MDE |
|---|---|---|---|---|
| monthly (overlapping) | 36 | −56.82pp | [−70.12, −43.82] | 18.83pp |
| annual (non-overlapping) | 3 | −52.00pp | [−74.73, −35.56] | 32.86pp |

The point estimate is stable across the two, which is reassuring about the
overlap concern specifically. It says nothing about the outlier problem, which
affects both equally.

---

## Finding 3: the fundamental data is thinner than pre-registered

### The oldest fiscal period is an empty column

yfinance returns five annual period labels for most tickers. **The oldest one
contains no data.** Measured across every cached statement, for tickers with
exactly five period labels:

| position (0 = oldest) | tickers with any data |
|---|---|
| **0** | **29 of 2,153 — 1%** |
| 1 | 2,153 of 2,153 — 100% |
| 2 | 2,153 of 2,153 — 100% |
| 3 | 2,150 of 2,153 — 100% |
| 4 | 2,147 of 2,153 — 100% |

The header is emitted; the figures are not. **Real statement depth is four
periods, not five.** The coverage report in the fetch step counted 2,308 names
with ≥4 annual periods, which was true of the labels and wrong about the data —
counting period labels rather than populated periods is what hid it.

### Consequence 1: two usable dates, not three

| rebalance date | names with EBIT/EV | status |
|---|---|---|
| 2022-12-31 | **13** | invalid — see below |
| 2023-12-31 | 1,579 | usable |
| 2024-12-31 | 1,722 | usable |

### The 2022-12-31 date is invalid, not underpowered

This distinction matters and is stated explicitly rather than folded into the
limitations.

After the pre-registered 6-month lag, the only fiscal period eligible at
2022-12-31 is the 2021 column — **the empty one**. Thirteen names clear it, out
of roughly 1,850 that carry a 2021 period *label*. The date does not have thin
coverage. It has **no data**, and the thirteen survivors are the 1% for whom
yfinance happened to populate the oldest column.

DESIGN.md's rule — "a factor-date below the floor is reported as underpowered,
not dropped" — was written for **genuinely thin coverage**: a real but small
cross-section, where dropping it would discard information and invite
outcome-dependent filtering. It was not written for **absent data**.

**Excluding this date would not have been an outcome-dependent choice.** The
emptiness of the oldest column is a property of the source. It is testable
before any factor is computed, it would have been equally true whatever the
results turned out to be, and had it been discovered before the run, **the
two-date version would have been the pre-registered primary.** It was not
discovered before the run, so the three-date figures are reported as promised,
with the two-date figures beside them and labelled post-hoc.

| factor, 12m | 3-date — **pre-registered primary** | 2-date — post-hoc |
|---|---|---|
| Value: EBIT/EV | −4.02pp [−74.10, +110.92], MDE 162.20pp | −61.49pp [−74.10, −48.87], MDE 35.32pp |
| Value: FCF/EV | −4.79pp [−72.14, +110.92], MDE 162.72pp | −62.64pp [−72.14, −53.13], MDE 26.61pp |
| Quality: GP/assets | −2.90pp [−64.51, +94.02], MDE 137.34pp | −51.35pp [−64.51, −38.19], MDE 36.85pp |
| Quality: positive FCF | −15.90pp [−59.66, +42.66], MDE 85.26pp | −45.18pp [−59.66, −30.69], MDE 40.56pp |
| Size: market cap | −94.37pp [−162.09, +32.15], MDE 177.27pp | −157.62pp [−162.09, −153.15], MDE 12.52pp |

Note what the invalid date does: it pulls every point estimate toward zero and
inflates every interval to roughly ±100pp. It does not make the results look
worse — **it makes them look more equivocal than the data is**, which is the
opposite of a conservative error.

Neither column should be believed. The two-date version is not a better estimate
of a factor premium; it is a cleaner measurement of the same artefact described
in [Finding 1](#finding-1-the-unattractive-decile-won-everywhere-on-a-handful-of-names).

### Consequence 2: dilution is structurally impossible

**Zero observations, at every date.** Not underpowered — impossible.

A 3-year share-count change needs two populated periods three years apart. With
four real periods and a 6-month lag, the selected period at the latest usable
rebalance is 2023-12-31, whose 3-years-prior counterpart would be 2020-12-31 —
outside the data entirely. The window never closes.

DESIGN.md estimated "one or two non-overlapping observations per ticker." That
was wrong, and it was wrong for a reason that was checkable in advance: it
assumed five usable periods where there are four, and did not work through the
lag arithmetic against the actual date range.

---

## Finding 4: the value factor is a sector bet

The sector-composition diagnostic was added to the design before the run, with
no criterion attached, on the reasoning that a concentrated decile means the
factor is partly a sector exposure. It fired immediately.

Value: EBIT/EV, after the pre-registered exclusion of Financial Services and
Real Estate:

| decile | composition |
|---|---|
| **D10** — cheap | Energy 28%, Industrials 17%, Basic Materials 16%, Consumer Cyclical 15% |
| **D1** — expensive | **Healthcare 64%**, Technology 10%, Consumer Cyclical 8%, Industrials 6% |

Value: FCF/EV is near-identical, with Healthcare again 64% of D1.

**Sixty-four percent of the expensive decile is one sector.** Whatever the
spread, this comparison is energy-and-materials versus biotech, and it cannot be
described as a factor result without that composition beside it. The mechanism
is transparent: a pre-revenue biotech has negative EBIT, negative EBIT ranks at
the bottom under the pre-registered negative-values rule, and the universe holds
461 Healthcare names — the largest sector in it.

Momentum and size are less concentrated but not neutral — Healthcare is 39% of
momentum's D1 and 38% of size's D1, the same bucket that carries the outliers.

---

## The tempting number, and why it is not reported as a result

Value EBIT/EV, restricted to positive-EBIT names:

| horizon | spread | 95% CI | MDE |
|---|---|---|---|
| 3m | **+4.30pp** | **[+2.82, +5.77]** | 4.12pp |
| 6m | **+4.69pp** | **[+2.33, +7.05]** | 6.61pp |
| 12m | +1.85pp | [−6.03, +9.73] | 22.07pp |

Tight intervals excluding zero, point estimates squarely inside the published
2–5% range for factor premia. It is the most publication-shaped output of the
entire study.

It is also, simultaneously:

1. an **exploratory** factor, pre-registered as ineligible to pass;
2. computed on **two** rebalance dates;
3. at **non-confirmatory horizons** — the 12-month figure is +1.85pp with an
   interval straddling zero;
4. produced by a **robustness filter**, not the primary specification;
5. one of roughly 60 spread estimates this run produced, so finding two adjacent
   cells with intervals excluding zero is unremarkable.

Five independent reasons not to believe it. It is recorded here explicitly
because this is the precise shape of finding that pre-registration exists to
prevent being written up — and leaving it un-named in the raw output invites
someone to rediscover it later without the five caveats attached.

---

## Three pre-registration flaws, and the corrected wording

Recorded so the next study inherits the fix rather than the lesson. None of
these is a data problem; all three are defects in
[DESIGN.md](DESIGN.md) that only became visible when it met real output.

### Flaw 1: no outcome for "significant in the wrong direction"

**What it said.** Three outcomes: pass; interpretable null with MDE below the
threshold; underpowered with MDE above it.

**Why it failed.** Momentum produced an interval excluding zero on the side
*opposite* the hypothesis, with an MDE above the threshold. The scheme forces
the label "underpowered," which is true about the design's resolution and false
about what was observed. A reader is told the study saw nothing, when it saw
something large.

**Corrected wording.** Condition on the interval first, the MDE second:

> For each confirmatory factor, exactly one of:
> 1. **Pass** — all criteria met.
> 2. **Counter-directional result** — the CI excludes zero on the side opposite
>    the hypothesis. Report the sign and magnitude, and state separately
>    whether the realised MDE permits treating it as an *estimate* of an effect
>    or only as a *detection* of one. A counter-directional result is never
>    reported as a null.
> 3. **Interpretable null** — the CI contains zero and the realised MDE is
>    below the threshold.
> 4. **Underpowered** — the CI contains zero and the realised MDE is above the
>    threshold.

### Flaw 2: the robust statistic was never pre-registered

**What it said.** Forward returns are "equal-weighted within decile." No
companion statistic, and no concentration diagnostic.

**Why it failed.** An equal-weighted mean of 12-month returns in a micro-cap
universe is an outlier estimator. One name supplied 25% of a decile's total
return. The median and winsorised mean had to be computed after seeing the
result, which is exactly the circumstance that makes a statistic untrustworthy
as a headline — so the honest magnitude of the effect can only ever be
reported here as post-hoc.

**Corrected wording.**

> Where the dependent variable is a long-horizon return in a small- or micro-cap
> universe, pre-register **both** the equal-weighted mean **and** robust
> companions — the median and the 99%-winsorised mean — as primary outputs, so
> neither is a post-hoc choice. Pre-register alongside them a **concentration
> diagnostic**: the share of each extreme decile's total return contributed by
> its largest one and largest five names. A mean-to-median ratio above 2× is
> **reported as a result about the estimator**, not as a footnote, and the
> factor's spread is not described as an effect size until the divergence is
> explained.

### Flaw 3: "report, don't drop" was applied to invalid rather than thin data

**What it said.** "A factor-date below the floor is reported as underpowered,
not dropped silently."

**Why it failed.** The rule is right for a small-but-real cross-section, where
dropping dates invites outcome-dependent filtering. Applied to a date whose
inputs do not exist, it injected 13 names into a 3-date mean, pulled every
fundamental point estimate toward zero and inflated every interval to ±100pp.
The rule designed to prevent a biased estimate produced one.

**Corrected wording.**

> Distinguish **thin** coverage from **absent** data.
> - A factor-date whose inputs exist but are few is **underpowered**: reported,
>   never dropped.
> - A factor-date whose inputs do not exist — an empty source column, a lag
>   window containing no populated period — is **invalid**: excluded, with the
>   exclusion and its source-side reason recorded.
>
> Validity is a property of the source, not of the result. It is therefore
> **checked and recorded in the data-fetch step, before any factor is
> computed**, so that the exclusion cannot be outcome-dependent. Concretely:
> coverage must be counted over **populated** periods, never over period
> labels, and the fetch step must report populated-period counts per field per
> period position.

That last clause is where this one should have been caught. The fetch step
reported 2,308 names with ≥4 annual periods — a true statement about labels and
a false one about data.

---

## What this study cannot support

- **Any claim about an individual stock.** The decile is the unit of analysis.
  No name here is a recommendation, a pick, or a conclusion.
- **Any claim about a momentum premium.** The confirmatory test is
  counter-directional and dominated by a few names; its honest magnitude is
  available only as a post-hoc statistic.
- **Any claim about a value, quality or size premium.** Two usable dates,
  MDEs 26–177pp against a 3.0pp threshold, and a value factor whose expensive
  decile is 64% one sector.
- **Any claim about dilution.** Zero observations.
- **Any claim about the size premium in either direction.** Beyond the power
  problem, the universe is selected on today's market cap, so a size spread
  would appear even if the true premium were zero —
  [Pitfall 4](DESIGN.md#pitfall-4-the-universe-is-selected-on-todays-market-cap).
- **Generalisation beyond this period or to larger caps.** One regime, measured
  on survivors, with mega caps excluded by construction.
- **A live trading decision of any kind.** Nothing here is a recommendation and
  no change to the screener or any other live system follows from it.

---

## Reproduction

```powershell
# 1. universe funnel  (~45 min, network)
.\.venv\Scripts\python.exe research\factor_study\universe_builder.py

# 2. prices + fundamentals  (~45 min, network, resumable)
.\.venv\Scripts\python.exe research\factor_study\fetch_data.py

# 3. tests
.\.venv\Scripts\python.exe -m pytest research\factor_study\test_factors.py -v

# 4. analysis  (~2 min, local only)
.\.venv\Scripts\python.exe research\factor_study\factors.py
```

Steps 1 and 2 cache per ticker under `research/factor_study/cache/` and are
resumable; both are gitignored, so a fresh clone refetches. Step 4 reads only
the cache and makes no network request. Bootstrap seed 42, 10,000 iterations,
so the intervals above reproduce exactly.

Run as reported: 2026-11-25. Universe built 2026-11-25, prices through
2026-11-23.

---

## Defects and open items

**Substantially resolved — the extreme returns appear genuine.** The original
concern was that the 330× and 73× price ranges driving decile 1 might be
defective adjustments. Inspecting the thirty largest forward returns by name
gives a thematically and temporally coherent cohort — quantum computing,
AI-datacenter, fintech turnarounds, biotech — which is not what a contaminated
sample looks like. Of the thirty, **21 of the 23 carrying a momentum value had
12-month past returns between −38% and −96%**, which confirms the survivorship
mechanism in
[Finding 1](#finding-1-the-unattractive-decile-won-everywhere-on-a-handful-of-names)
from individual rows rather than inferring it from decile means.

**Still open, narrowly:** the exact magnitudes are unverified against a second
source, and some rebalance dates post-date any independent check available
here. This no longer threatens the headline finding, which rests on
concentration and skew rather than on authenticity — and which
[has a second, independent basis](#two-independent-reasons-the-5682pp-is-not-a-momentum-measurement)
in the estimator mismatch regardless.

**Corrected during review — an inflated tail statistic.** A first pass reported
that 6.1% of the universe (151 of 2,477 names) exceeded +500%. That figure is
`max()` taken over 36 *overlapping* 12-month windows and counts the same name
at many dates: it overstates the per-date tail by **9.8×**. The correct figure
is a per-rebalance-date mean of **0.63%**, and it is what Finding 1 reports.
Recorded here because a document about methodological care should not carry an
overlap artefact of exactly the kind it warns about elsewhere.

**Open — coverage counting.** The fetch step's coverage report counts period
*labels*, not populated periods, and therefore overstated fundamental depth
(2,308 names with ≥4 periods). Flaw 3's corrected wording specifies the fix; the
code in `fetch_data.py` has not been changed.

**Accepted — the final month is partial.** The month-end panel's last entry is
2026-11-30, carrying the close from 2026-11-23. The 12-month forward return from
the final rebalance therefore spans about 11.8 months. A rebalance date was
judged worth more than a week of precision.

**Fixed during the run.** Two code defects were found and corrected before the
reported numbers were produced:

1. `assign_deciles` put the remainder into decile 1 when it exceeded eight,
   making D1 and D10 unequal in size at n ≡ 9 (mod 10) — a biased spread by
   construction. Caught by `test_the_extreme_deciles_are_always_equal_in_size`,
   which sweeps n from 10 to 59. It would not have fired at n = 2,477.
2. `load_fundamentals` returned object-dtype columns when the cache contained
   JSON `null`, and `np.isfinite` raises rather than returning False on object
   dtype. The hand-built test fixtures used clean floats and were tidier than
   the real cache, so the tests missed it until the first real run crashed.
   A `TestFundamentalLoading` class now reads an actual file containing nulls.

86 tests pass against the code that produced these numbers.
