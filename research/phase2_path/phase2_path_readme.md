# Study 10 — Path Study

Tenth study. Phase 2.

Every metric in Studies 1–9 was endpoint-only. This one asks whether the *path*
a price took to get where it is carries information the endpoints throw away.

**Status: complete, and the hypothesis is untested.** Not refuted — untested.
The study turned out to be about seven times too blunt to measure the thing it
was built to measure, and the reason why is the finding worth keeping: **alerts
fire at or near their 10-session high 82.6% of the time, in two independent
universes.** The population the hypothesis is about is roughly 9% of alerts.

**No configuration change. Nothing in the live screener was touched.**

For all ten studies across both phases, see [../FINDINGS.md](../FINDINGS.md).

---

## Contents

- [The question](#the-question)
- [Why endpoint-only measurement loses information](#why-endpoint-only-measurement-loses-information)
- [The two metrics](#the-two-metrics)
- [The fencepost, and why it got 52 tests](#the-fencepost-and-why-it-got-52-tests)
- [How the study was designed](#how-the-study-was-designed)
- [What was fixed before any result existed](#what-was-fixed-before-any-result-existed)
- [Why the minimum detectable effect was computed in advance](#why-the-minimum-detectable-effect-was-computed-in-advance)
- [What the numbers were](#what-the-numbers-were)
- [Why the study failed, and what failed about it](#why-the-study-failed-and-what-failed-about-it)
- [Files in this directory](#files-in-this-directory)
- [How to reproduce](#how-to-reproduce)
- [What would be needed to actually answer the question](#what-would-be-needed-to-actually-answer-the-question)

---

## The question

The live price condition is:

```
(close_today - close_10_sessions_ago) / close_10_sessions_ago >= 0.07
```

Two endpoints. Nothing between them.

**Hypothesis.** Alerts where the 10-session high is *recent* outperform alerts
where the high is *stale*.

The intuition: a stock still climbing at +10% is a different animal from one
that rose 25%, broke, and fell back to +10%. The second may be a falling knife
that the filter cannot see. AMD was the motivating example — and one example is
not evidence, which is why this was measured before anything was changed.

---

## Why endpoint-only measurement loses information

Three stocks, all reporting exactly +10% over ten sessions:

| | day 1 | ... | day 10 | what the filter sees | what happened |
|---|---|---|---|---|---|
| A | 100 | climbing | 110 | +10% | still making highs |
| B | 100 | spiked to 125 | 110 | +10% | broke, fell 12% off the high |
| C | 100 | flat then jumped | 110 | +10% | one-day gap, now sideways |

Identical to the screener. Not identical as trades — or so the hypothesis
claims. The study's job was to find out whether that claim survives contact
with history, or whether it only sounds right.

---

## The two metrics

Both measured at the moment of each alert, over the last `recent_n = 10` closes,
oldest first, with `closes[-1]` being the alert day:

```
days_since_high    = (recent_n - 1) - argmax(closes)
drawdown_from_high = (max(closes) - closes[-1]) / max(closes)
```

`days_since_high` is **0** when the stock peaked today and **9** when it peaked
at the window start. `drawdown_from_high` is **0** when today *is* the high.

Applied to the table above: A scores `days_since_high = 0`, drawdown 0%. B
scores something in the middle with a 12% drawdown. The filter cannot
distinguish them; these two numbers can.

**Ties go to the earlier bar.** `np.argmax` returns the first occurrence, so two
bars at the same high score as the *staler* of the two. That direction is
deliberate: a tie never flatters the group the hypothesis predicts will win.

---

## The fencepost, and why it got 52 tests

`days_since_high` is a window index subtraction, and this repo has already
shipped exactly one bug of that shape. Study 9 found that the volume ratio was
computed as `dv.rolling(recent).mean() / dv.rolling(base).mean()`, so the
baseline *included* the recent window — mathematically capping the ratio at
`base_n / recent_n` and inflating an apparent result by up to 4×. It survived
eight studies unnoticed.

So the arithmetic here was pinned rather than trusted:

- **Every peak position from 0 to 9**, parametrized, each asserting
  `9 - position`. An off-by-one cannot hide in the middle of the range where it
  would still look plausible.
- **Both boundaries separately.** Peak-is-today must be 0; peak-at-window-start
  must be 9. An implementation with the subtraction reversed passes a midpoint
  test and fails both of these.
- **The vectorised pass against the pure functions.** This is the one that
  matters. The study reads its numbers from a `rolling(...).apply` pass, not
  from the pure function directly, so a window drifting by one bar there would
  corrupt every result while the unit tests stayed green.
- **NaN is never swept into "fresh."** An unscored alert landing in the group
  predicted to win is the failure mode that would quietly manufacture a
  positive.

52 tests, all passing; full suite 139. No off-by-one was found.

---

## How the study was designed

**Alert set.** The trigger logic is imported unchanged from
`../phase1_validation/backtest.py` rather than reimplemented, so the alert set
stays comparable with Studies 1–4. That module's `extract_ticker_frame` gates
tickers on `BASELINE_WINDOW_DAYS + max(HORIZONS) + 10` sessions, so its
`HORIZONS` decides which tickers are eligible at all — rebuilding it around this
study's horizons would have silently changed the usable universe, the baseline
and the alert list.

**Episode de-duplication.** `SIGNAL_GAP_DAYS = 10`, counted in *trading
sessions*, inherited. Without it one two-week surge counts as ten alerts and
inflates the sample.

**Baseline.** Date-matched universe mean: for each date, the cross-sectional
mean forward return across every usable ticker. Excess return, not raw return,
is the quantity tested. A group that returned +8% where the universe returned
+8% found nothing.

**Two samples, roles fixed in advance.** 60-ticker cache primary (comparable
with every phase-1 result), 178-ticker cache as replication (deliberately
includes laggards and names with no AI story, so it is the harder test of
whether an effect is an artefact of universe construction).

**Survivorship bias is less corrosive here than usual.** It would wreck a
question like "what return do alerts earn" — surviving names drift up. This
study compares two groups *inside* the same biased universe, and the bias lands
on both arms roughly equally. A difference is far more robust to it than a
level.

---

## What was fixed before any result existed

All of it is in [PREREGISTRATION.md](PREREGISTRATION.md), committed before the
analysis script was run:

| commitment | value |
|---|---|
| fresh | `days_since_high` 0–2 |
| stale | `days_since_high` 5–9 |
| dropped | 3–4, as genuinely ambiguous |
| confirmatory horizon | 10 sessions, and only 10 |
| supporting horizons | 5 and 21, no criterion |
| pass criterion | clustered 95% CI excludes zero on the positive side **and** point estimate >= +2.0 pp |
| sample floors | 100 alerts **and** 20 tickers per group |
| disagreement rule | passes on primary, fails on replication → **fragile**, not a pass |

**Why one confirmatory comparison and not ten.** Reporting all ten
`days_since_high` buckets as *the test* is the forking-paths trap: with ten
buckets some split always looks good, and after the fact there is no honest way
to say whether it was found or invented. The ten-bucket view was kept, but
labelled exploratory with no criterion attached — its job is to show *shape*,
since a real mechanism should produce a roughly monotonic gradient.

That protection was not hypothetical. Replication bucket 9 came back at
**+66.67 pp mean excess — from 3 alerts across 2 tickers**, next to −10.36 in
bucket 8. A headline was sitting there, in the *reverse* direction of the
hypothesis, from three observations.

**Why `drawdown_from_high` got no criterion.** The hypothesis names the recency
of the high, not the depth of the pullback. Giving drawdown its own criterion
would have been a second shot at a positive on the same data.

---

## Why the minimum detectable effect was computed in advance

A null result is ambiguous between two very different worlds: the effect is not
there, or the instrument cannot see it. The MDE is what separates them, and it
is knowable before any result because it depends only on sample size and
dispersion.

So the design was committed to **three** outcomes rather than two:

1. **Pass** — criterion met.
2. **Interpretable null** — criterion not met, MDE *below* 2.0 pp. The design
   could have seen an effect worth acting on and did not.
3. **Underpowered** — criterion not met, MDE *above* 2.0 pp. The study could
   not have detected an effect worth acting on, and must say so rather than
   reporting a null.

The pre-registration projected MDEs of 4.8–6.8 pp for balanced groups of
100–250 against a 2.0 pp threshold — already a warning, recorded in advance,
that only an effect several times larger than the action threshold would be
visible.

The realised MDEs were far worse: **17.24 pp** primary, **14.18 pp**
replication. The `sqrt(1/n_fresh + 1/n_stale)` term is governed by the *smaller*
group, and the smaller group held 12 alerts.

---

## What the numbers were

Full tables in [FINDINGS.md](FINDINGS.md). The headline:

| | primary (60) | replication (178) |
|---|---|---|
| alerts | 115 | 368 |
| fresh (0–2) | 95 (**82.6%**) | 304 (**82.6%**) |
| stale (5–9) | 12 (**10.4%**) | 34 (**9.2%**) |
| fresh mean excess, 10d | +1.40 pp | +3.93 pp |
| stale mean excess, 10d | +0.29 pp | +6.18 pp |
| difference | +1.11 pp | **−2.25 pp** |
| 95% CI (clustered) | −8.15 to +11.68 | −16.55 to +8.25 |
| MDE at 80% power | 17.24 pp | 14.18 pp |

**Outcome 3: underpowered.** The sign flips between samples, the horizons
disagree four times out of six, and the bucket gradient runs weakly *the wrong
way* (Spearman +0.04 and +0.18 where the hypothesis predicts negative).

---

## Why the study failed, and what failed about it

Not sample size in aggregate — **group imbalance**, which is itself the finding.

An alert requires +7% over 10 sessions *together with* a dollar-volume surge. A
stock that has done both is nearly always sitting at or near its 10-session high;
that is very close to what the condition *means*. For an alert to be stale, the
stock must rise sharply, peak, fall back, and *still* be up 7% endpoint-to-
endpoint with elevated volume. That is a narrow corridor, and about one alert in
ten lands in it.

Two universes of very different size and composition agreed on **82.6%** fresh
to the decimal. That is close to mechanical, not a sampling coincidence.

**The original suspicion was correct in kind and wrong in degree.** The price
filter is path-blind, and it does admit falling knives. It just admits them
about 9% of the time. AMD is a real instance of a real pattern — a ~9% pattern,
not a pervasive defect.

**The candidate filter is cheap and unjustified.** Rejecting
`days_since_high >= 5` would remove 10.4% of primary alerts and 9.2% of
replication alerts. Cheap cuts both ways: a 10% reduction is easy to justify
*if* it works, and nothing here establishes that it works. Buying it on an
unmeasured effect means paying a real cost for an imagined benefit.

---

## Files in this directory

| file | what it is |
|---|---|
| **[PREREGISTRATION.md](PREREGISTRATION.md)** | Commitments made before any result. Hypothesis, definitions, criterion, floors, MDE, limitations known in advance. Carries a dated correction note. |
| **[FINDINGS.md](FINDINGS.md)** | What was found. Full tables, the verdict against the criterion, exploratory views, defects. |
| **[path_analysis.py](path_analysis.py)** | The confirmatory instrument. Prints numbers and **deliberately prints no verdict** — a script that announces "PASS" is a script that invites adjustment until it does. |
| **[test_path_metrics.py](test_path_metrics.py)** | 52 tests. The fencepost, both boundaries, tie direction, and agreement between the pure functions and the vectorised pass. |

Per-alert output lands in `results/phase2_path/` (gitignored):
`path_alerts_primary.csv`, `path_alerts_replication.csv`,
`confirmatory_summary.csv`.

### A correction worth reading

`PREREGISTRATION.md` originally claimed the primary run would reproduce the
498-alert sample in `results/phase1/signals.csv`. **It does not** — the primary
run produced 115 alerts. That file was generated under an earlier config
(volume 1.50, baseline 63); its `volume_ratio` column runs down to 1.50, and
only 161 of its 498 rows clear today's 1.75 threshold.

The pre-registered sample *definition* — alerts at the live thresholds in
`config.py` — was unchanged and is what ran. Only the equivalence claim was
wrong. It is corrected by a dated note rather than edited out, so the error
stays visible in version history.

The transferable lesson: **a committed result file records the config of the day
it was written, not the config in force now.** Row counts matching is not the
same as thresholds matching.

---

## How to reproduce

```
pytest research/phase2_path/test_path_metrics.py -v
python research/phase2_path/path_analysis.py
```

No network access and no new dependencies. Both runs read cached history
(`cache/backtest_history.pkl`, `cache/universe178_history.pkl`). Spearman
correlations are computed by ranking and taking the ordinary correlation,
because pandas' `method="spearman"` imports scipy, which this repo does not
have.

---

## What would be needed to actually answer the question

**Not more tickers.** 178 tickers over three years yielded 34 stale alerts.
Reaching the 100-alert floor would take roughly 500 tickers; making a 2.0 pp
effect detectable would take several thousand — all still inside the same
2023–2026 regime.

The design has to change, not the scale. **Sample on the path directly** rather
than waiting for the alert condition to produce one: define the pattern
(a sharp rise, a peak, a partial retrace) as the selection event itself, and
measure what follows against a date-matched baseline. That makes the two groups
comparable in size by construction, and it is a new study rather than an
extension of this one.

### Answered after the study, by a descriptive recompute

Two of the questions this study left open have since been settled, counts only
and no test. Tables in [FINDINGS.md](FINDINGS.md).

**Does the live alert definition have the same 82.6% fresh share?** Yes.
Recomputed with the volume baseline excluding the recent window — the live
configuration, which fires ~3.6× more often — the split is **83.8% fresh on 407
episodes** (60-ticker) and **82.8% fresh on 1,096 episodes** (178-ticker). All
four combinations of universe and baseline geometry land between 82.6% and
83.8%.

**Which condition produces it?** The **price** condition. Loosening volume by
3.6× barely moves the distribution, so the clustering at the high is not the
volume filter's doing and not an artefact of the Study 9 ceiling. A stock up 7%
over ten sessions is at or near its ten-session high almost by construction.

A side effect worth recording: the live definition yields **exactly 100 stale
episodes** on the 178-ticker cache, which would just clear the pre-registered
100-alert floor — but the MDE would still be near 8 pp against a 2.0 pp
threshold, so it improves the design without making it adequate.

### Still open

- Does the fresh/stale distinction matter for the *entry timing* of an alert
  already issued, rather than for whether to issue it?
- The alert set here inherits the overlapping volume baseline from
  `backtest.py`, so it is phase-1-comparable but **not** identical to what the
  live screener fires on today. The *shape* of the alerts is now known to be the
  same; whether the forward returns behave the same way is not.
