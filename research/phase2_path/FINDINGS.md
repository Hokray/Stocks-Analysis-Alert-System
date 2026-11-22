# Path Study: Does the Shape of a Price Move Predict What Happens Next?

Phase 2, path study. Pre-registered in `PREREGISTRATION.md` before any result
was computed.

**The hypothesis could not be tested, and the reason it could not be tested is
the finding.**

Alerts almost always fire at or near the 10-session high. **82.6% of them, in
both samples, to the decimal.** The stale-high alert the study was built to
measure is roughly **9%** of the alert stream. There was never a second
population large enough to compare against the first.

The pre-registered test therefore returns **outcome 3 of 3: underpowered.** Not
a pass, and explicitly **not** an interpretable null. The design could detect a
fresh-minus-stale difference of about **14 to 17 percentage points**; the
threshold worth acting on was **2.0 pp**. It was roughly seven times too blunt
to answer its own question.

**Nothing here licenses a change to the live screener, in either direction.**

---

## Contents

- [Finding 1: alerts fire at the high almost by construction](#finding-1-alerts-fire-at-the-high-almost-by-construction)
- [Finding 2: the pre-registered test is underpowered](#finding-2-the-pre-registered-test-is-underpowered)
- [Cost of the candidate filter](#cost-of-the-candidate-filter)
- [Exploratory views, all null or incoherent](#exploratory-views-all-null-or-incoherent)
- [What the pre-registration prevented](#what-the-pre-registration-prevented)
- [A correction to the pre-registration](#a-correction-to-the-pre-registration)
- [Defects found and their status](#defects-found-and-their-status)
- [Limitations](#limitations)
- [Conclusion](#conclusion)

---

## Finding 1: alerts fire at the high almost by construction

`days_since_high` is 0 when the stock peaked today and 9 when it peaked at the
start of the 10-session window. Distribution of historical alerts:

| group | `days_since_high` | primary (60-ticker) | replication (178-ticker) |
|---|---|---|---|
| fresh | 0-2 | 95 (**82.6%**) | 304 (**82.6%**) |
| dropped | 3-4 | 8 (7.0%) | 30 (8.2%) |
| stale | 5-9 | 12 (**10.4%**) | 34 (**9.2%**) |
| | **total** | **115** | **368** |

The two samples agree to the decimal on an 82.6% fresh share despite one being
three times the size of the other and deliberately stuffed with laggards. That
is not a coincidence of sampling; it is close to mechanical.

**Why.** The alert condition requires +7% over 10 sessions *together with* a
dollar-volume surge. A stock that has done both is nearly always sitting at or
near its 10-session high — that is very close to what the condition means. For
an alert to be stale, the stock must rise sharply, peak, fall back, and *still*
be up 7% over the full window measured endpoint-to-endpoint, with elevated
volume. That is a narrow corridor, and about one alert in ten lands in it.

**What that does to the original suspicion.** The concern was that the
path-blind price filter admits falling knives: a stock that rose 25% and fell
back to +10% scores identically to one still climbing at +10%. That concern is
correct in kind. It is just much smaller in degree than the framing suggested.
AMD is a real instance of a real pattern — it is simply a ~9% pattern, not a
pervasive defect. Even a large true effect confined to that sliver moves the
alert stream very little.

**It also explains why the study cannot be rescued by scale.** 178 tickers over
three years produced **34** stale alerts. Reaching the pre-registered 100-alert
floor for the stale group would take roughly 500 tickers; reaching a sample
where the 2.0 pp threshold is detectable would take several thousand, all still
inside the same 2023-2026 regime. More data of this kind does not fix this. A
different design would be required — event-time sampling that selects on the
path itself rather than waiting for the alert condition to produce one.

### The base rate is not an artefact of the old baseline geometry

The figures above come from the phase-1/2 alert set, whose volume baseline
*overlaps* the recent window. The live screener excludes it
(`config.BASELINE_EXCLUDES_RECENT = True`, Study 9's fix), and fires about 3.6×
more often as a result. That raised a fair objection: the overlapping ratio is
capped at `BASELINE / RECENT = 3.0`, so the ceiling restricted *which* days
could fire, and the 82.6% might have been an artefact of that restriction
rather than a property of the screener.

It is not. Recomputed under both definitions, counts only, no test:

| | overlapping (this study's set) | **live (baseline excludes recent)** |
|---|---|---|
| **60-ticker** | | |
| episodes | 115 | **407** |
| fresh (0-2) | 95 (**82.6%**) | 341 (**83.8%**) |
| dropped (3-4) | 8 (7.0%) | 30 (7.4%) |
| stale (5-9) | 12 (10.4%) | 36 (**8.8%**) |
| mean `days_since_high` | 1.34 | 1.19 |
| **178-ticker** | | |
| episodes | 368 | **1,096** |
| fresh (0-2) | 304 (**82.6%**) | 908 (**82.8%**) |
| dropped (3-4) | 30 (8.2%) | 88 (8.0%) |
| stale (5-9) | 34 (9.2%) | 100 (**9.1%**) |
| mean `days_since_high` | 1.27 | 1.23 |

All four combinations — two universes by two baseline geometries — land between
**82.6% and 83.8% fresh** and between **8.8% and 10.4% stale**, and the live
178-ticker figure rests on 1,096 episodes rather than 368.

**This localises the base rate to the price condition.** Loosening the volume
condition by 3.6× barely moves the distribution, so the clustering at the high
is not produced by the volume filter and not produced by the Study 9 ceiling. It
is the geometry of the price condition itself: a stock up 7% over ten sessions
is at or near its ten-session high almost by construction. Finding 1 is a
property of the momentum filter, and it describes the screener that is running
today as well as the one this study measured.

One consequence for any future attempt. The live definition yields **exactly
100 stale episodes** on the 178-ticker cache, which would just clear the
pre-registered 100-alert floor. The MDE would still be near **8 pp** against a
2.0 pp threshold — better powered, not adequately powered — and it would need
its own pre-registration, since the sample definition changes.

**A reconciliation, so the two tables agree.** The bucket table later in this
document shows bucket 1 at 16 for the 60-ticker cache where the recompute above
counts 17. That table includes only alerts with a non-NaN 10-session excess
return, and one bucket-1 alert sits too close to the end of the cached history
to have one. Group totals agree exactly at 95 fresh.

---

## Finding 2: the pre-registered test is underpowered

The confirmatory comparison, exactly as specified in advance: fresh minus stale,
mean excess return at 10 sessions, clustered bootstrap by ticker, 10,000
iterations, seed 42.

### Primary sample (60-ticker cache, 115 alerts, 42 tickers, 2023-11-01 to 2026-08-19)

| group | alerts | tickers | mean excess | median | SD | beat baseline |
|---|---|---|---|---|---|---|
| fresh | 94 | 39 | **+1.40 pp** | −0.70 | 19.77 | 47.9% |
| stale | 12 | 9 | **+0.29 pp** | −2.56 | 22.61 | 41.7% |

Observed difference **+1.11 pp**, 95% CI **−8.15 to +11.68 pp**, 38.8% of
resamples at or below zero.

### Replication sample (178-ticker cache, 368 alerts, 114 tickers, 2023-07-14 to 2026-08-24)

| group | alerts | tickers | mean excess | median | SD | beat baseline |
|---|---|---|---|---|---|---|
| fresh | 302 | 105 | **+3.93 pp** | +0.10 | 26.74 | 50.3% |
| stale | 34 | 25 | **+6.18 pp** | −1.69 | 37.58 | 41.2% |

Observed difference **−2.25 pp** — the opposite sign — 95% CI **−16.55 to
+8.25 pp**, 58.3% of resamples at or below zero.

### Reading the criterion mechanically

| condition | primary | replication |
|---|---|---|
| quantity is fresh − stale, 10-session excess | +1.11 pp | −2.25 pp |
| clustered 95% CI excludes zero, positive side | no | no |
| point estimate >= +2.0 pp | no | no |
| both groups meet 100-alert and 20-ticker floors | no: fresh 94, stale 12 | no: stale 34 |

The primary sample fails, so by the pre-registered disagreement rule the result
is a failure regardless of the replication — which also fails, in the other
direction.

### Which kind of failure: the MDE decides

| | primary | replication |
|---|---|---|
| pooled SD | 20.09 pp | 28.00 pp |
| 95% CI half-width | 12.07 pp | 9.93 pp |
| **MDE at 80% power** | **17.24 pp** | **14.18 pp** |
| pass threshold | 2.00 pp | 2.00 pp |

Both MDEs are roughly **seven times** the effect size worth acting on, so this
is **outcome 3: underpowered**. Stated plainly, as the pre-registration
requires: **this study could not have detected an effect worth acting on, and
therefore says nothing about whether one exists.** The null here is a statement
about the instrument, not about the market.

The realised MDE is far worse than the 4.8-6.8 pp the pre-registration projected
for balanced groups of 100-250. Two reasons, one minor and one decisive.
Dispersion came in higher than the 17.16 pp assumed (20-28 pp). But the
`sqrt(1/n_fresh + 1/n_stale)` term is governed by the *smaller* group, and the
smaller group is 12 alerts in the primary sample. Group imbalance, which is
Finding 1, is what destroyed the power — not sample size in aggregate.

Note that the fresh group also missed its floor, at 94 against 100. Per the
pre-registration the floors were fixed in advance and not moved after the counts
were seen. It makes no difference to the verdict: the stale group misses by a
factor of eight either way.

---

## Cost of the candidate filter

Reported whatever the outcome, since a filter that improves returns while
removing most alerts may still not be worth it.

| filter | primary removed | replication removed |
|---|---|---|
| reject `days_since_high >= 5` (confirmatory stale definition) | 12 (**10.4%**) | 34 (**9.2%**) |
| reject `days_since_high >= 3` (includes the dropped middle) | 20 (**17.4%**) | 64 (**17.4%**) |

So the candidate filter is cheap — it would suppress about one alert in ten.
That cuts both ways. A cheap filter is easy to justify *if* it works, and
nothing here establishes that it works. Buying a 10% volume reduction on an
effect this study could not measure would be paying a real cost for an imagined
benefit.

---

## Exploratory views, all null or incoherent

No criterion was attached to any of these in advance, and none may be attached
now.

**Horizons do not agree on a sign.** The pre-registration stated that a real
effect should point the same way at 5, 10 and 21 sessions.

| horizon | primary | replication |
|---|---|---|
| 5d | −3.79 pp | +1.06 pp |
| 10d (confirmatory) | +1.11 pp | −2.25 pp |
| 21d | +3.97 pp | +6.43 pp |

Four sign flips across six cells. This is what noise looks like.

**Monotonicity is absent, and what gradient exists runs the wrong way.**
Spearman rank correlation between bucket index and mean 10-session excess:
**+0.04** (primary) and **+0.18** (replication). The hypothesis predicts a
negative gradient — returns declining as the high gets staler. There is no
gradient.

| `days_since_high` | primary: alerts / mean excess | replication: alerts / mean excess |
|---|---|---|
| 0 | 61 / +1.81 | 190 / +5.00 |
| 1 | 16 / −0.76 | 71 / +3.95 |
| 2 | 17 / +1.96 | 41 / −1.05 |
| 3 | 5 / **+22.22** | 15 / +5.77 |
| 4 | 3 / −2.22 | 15 / +6.63 |
| 5 | 5 / −1.71 | 14 / +0.01 |
| 6 | 2 / +7.30 | 10 / +2.03 |
| 7 | 2 / +16.82 | 3 / +10.43 |
| 8 | 2 / −19.45 | 4 / −10.36 |
| 9 | 1 / +2.77 | 3 / **+66.67** |

Past bucket 2 the cells hold single-digit alert counts and the means swing
wildly in both directions. There is no shape here to interpret.

**`drawdown_from_high` predicts nothing.** Spearman with 10-session excess
return: **+0.036** (primary) and **−0.012** (replication) — both
indistinguishable from zero, and in opposite directions. The metric does measure
what it claims: mean drawdown is 2.2% for fresh alerts against 7.0-8.6% for
stale ones. It simply carries no forward information here.

For completeness and no more: the deeper-drawdown half had the *higher* mean
excess in both samples (+1.55 vs +3.72 pp primary, +4.02 vs +5.23 pp
replication). That is the opposite of the falling-knife story. At these
confidence intervals it means nothing and should not be read as a hint.

---

## What the pre-registration prevented

Worth recording, because the protection was not hypothetical.

Replication bucket 9 shows a mean excess of **+66.67 pp** — from **3 alerts
across 2 tickers**. Its immediate neighbour, bucket 8, shows −10.36. Primary
bucket 3 shows +22.22 pp from 5 alerts.

Had "report all ten buckets" been the test rather than a labelled exploratory
view, a headline was available: *alerts that peaked at the window start massively
outperform* — the exact reverse of the hypothesis, from three observations. With
ten buckets and two samples, some cut always looks good, and after the fact there
is no honest way to say whether it was found or invented.

One pre-registered comparison, fixed in advance, is the only reason that number
sits in an exploratory table instead of a conclusion. The same goes for the
decision not to give `drawdown_from_high` its own criterion: it would have been
a second shot at a positive on the same data.

---

## A correction to the pre-registration

`PREREGISTRATION.md` claimed the primary run would reproduce the 498-alert
sample in `results/phase1/signals.csv`. It does not: the primary run produced
**115 alerts**. That file was generated under an earlier config — volume surge
1.50 and baseline window 63 — both since changed to 1.75 and 30. Its
`volume_ratio` column runs down to 1.50, and only 161 of its 498 rows clear
today's 1.75 threshold.

The pre-registered **sample definition** — alerts at the live thresholds in
`config.py` — was unchanged and is what ran. Only the claim of equivalence to
the phase-1 sample was wrong, and it is corrected by a dated note at the top of
that document rather than edited out, so the error remains visible in version
history.

Its practical consequence was severe: the study ran on roughly a quarter of the
sample the document led a reader to expect, which turned an already-marginal
design into a decisively underpowered one. The lesson is narrow and worth
keeping: a committed result file records the config of the day it was written,
not the config in force now. Row counts matching is not the same as thresholds
matching.

---

## Defects found and their status

1. **`pandas` Spearman requires scipy** — the script crashed at the end of the
   first run. scipy is not installed and this study was not permitted to add a
   dependency. Replaced with a local `spearman()` that ranks both inputs and
   takes the ordinary correlation, which is the same number; pandas' default
   ranking averages ties, the correction Spearman calls for. **Fixed.**
2. **The drawdown table is labelled "quartile" but has two rows.**
   `pd.qcut(..., 4, duplicates="drop")` collapsed the bins because a large mass
   of alerts have a drawdown of exactly 0.00%, making the lower cut points
   identical. The collapse is itself informative — the mass at zero *is* the
   distribution, and it is Finding 1 restated — but the label is wrong.
   **Open.** It affects an exploratory table only and none of the figures above.
3. **No off-by-one was found in the path metrics.** The fencepost this repo had
   shipped a bug in before was pinned by 52 tests covering every peak position
   from 0 to 9, both window boundaries, tie direction, and agreement between the
   pure functions and the vectorised rolling pass the study actually reads from.
   All pass; full suite 139 pass.

---

## Limitations

1. **Underpowered by a factor of about seven.** The central limitation, and the
   reason there is no finding about the hypothesis. See Finding 2.
2. **The alert set is phase-1-comparable but not live-screener-identical.**
   `backtest.compute_metrics` computes the volume baseline as a plain rolling
   mean, so the baseline window overlaps the recent window; the live screener
   excludes it (`config.BASELINE_EXCLUDES_RECENT = True`). This was inherited
   deliberately, to keep the alert set comparable with phase 1 rather than
   silently redesigning it mid-study. It does mean any finding here would need
   re-checking against the live configuration before being acted on.
3. **Alerting tickers sit inside their own baseline.** An alert's forward return
   contributes to the date-matched mean it is compared against, shrinking every
   excess return slightly toward zero. In a difference of two groups this mostly
   cancels, but only where the two groups share dates — and fresh and stale
   alerts need not. Small relative to the effects discussed, and not corrected,
   since changing the baseline would break comparability with phase 1.
4. **Survivorship bias** in both universes, strongest in the 60-ticker one.
   Argued in the pre-registration to fall on both arms roughly equally, which
   makes a *difference* far more robust to it than a *level*.
5. **Overlapping periods.** Alerts close in time share market conditions even
   after the 10-session episode de-duplication. The clustered bootstrap handles
   clustering within a ticker, not across tickers on the same date.
6. **One sector, one regime.** The 2023-2026 AI buildout. Nothing generalises.
7. **No point-in-time fundamentals.** The TTM cash-flow gate is not applied
   historically, so these are the two technical conditions only.
8. **No costs**, and **adjusted closes** — so the "high" is not the headline
   price a trader saw at the time.
9. **The out-of-sample snapshot check was not run.** `data/snapshots/` holds no
   per-ticker daily close series and its forward returns run past the end of the
   cached history, so it could not have confirmed anything regardless.

---

## Conclusion

The hypothesis — that alerts with a recent 10-session high outperform those with
a stale one — **remains untested**. This study was too blunt to measure it by
roughly a factor of seven, and says nothing about whether the effect is real.

What it did establish is why: **the alert condition fires at or near the
10-session high 82.6% of the time, in two independent universes, and the stale
population the hypothesis is about is only about 9% of alerts.** The
path-blindness of the price filter is real but much narrower in scope than the
motivating example suggested, and no amount of additional data of this kind will
produce a testable sample — 178 tickers over three years yielded 34 stale alerts.

**No change to the live screener is proposed or justified by this work.** A 10%
alert reduction is cheap, but buying it on an unmeasured effect would be paying
a real cost for an imagined benefit. If the question is worth pursuing, it needs
a different design: sampling on the path directly rather than waiting for the
alert condition to yield one, which is a new study and not an extension of this
one.

`screener.py`, `config.py`, `notifier.py` and `snapshot.py` were not touched.
This was measurement only.
