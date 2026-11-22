# Pre-registration: does the PATH of a price move predict what happens next?

Phase 2, path study. Written **before** any result was computed.

The price filter measures `(close_today - close_10_sessions_ago) / close_10_sessions_ago`.
That is endpoint-only and path-blind. A stock that rose 25% and fell back to
+10% is indistinguishable from one still climbing at +10%. The suspicion is
that the second is a better signal and the first is a falling knife.

This document fixes the hypothesis, the definitions, the pass criterion and the
power of the design before the numbers exist. Anything not written here is not
a preregistered claim.

---

## Correction, 2026-11-21, after the step-5 run

This document stated that the primary run reproduces the 498-alert sample in
`results/phase1/signals.csv`. **It does not.** At the current live thresholds the
same cache yields **115 alerts**.

`signals.csv` was generated under an earlier config -- volume surge 1.50 and
baseline window 63 sessions -- both since changed to 1.75 and 30 (see the
comments in `config.py`). Its `volume_ratio` column runs down to 1.50, below
today's threshold; only 161 of those 498 alerts clear 1.75.

The preregistered **sample definition** -- alerts at the live thresholds in
`config.py` -- is unchanged, and is what was run. Only the claim of equivalence
to the phase-1 sample was wrong. No threshold, cut, horizon, floor or criterion
in this document was altered.

The original claim is left in place below rather than edited out, so the error
stays visible in version history. Its practical consequence is recorded in
`phase2_path_readme.md`: the study ran on roughly a quarter of the sample this
document led the reader to expect, which made an already-marginal design
decisively underpowered.

---

## Contents

- [Correction, 2026-11-21, after the step-5 run](#correction-2026-11-21-after-the-step-5-run)
- [Hypothesis](#hypothesis)
- [The two path metrics](#the-two-path-metrics)
- [Fresh versus stale](#fresh-versus-stale)
- [Forward returns and the baseline](#forward-returns-and-the-baseline)
- [Sample: primary and replication](#sample-primary-and-replication)
- [The pass criterion](#the-pass-criterion)
- [Minimum detectable effect](#minimum-detectable-effect)
- [The three outcomes step 5 may report](#the-three-outcomes-step-5-may-report)
- [Secondary and exploratory, with no criterion attached](#secondary-and-exploratory-with-no-criterion-attached)
- [Cost of the candidate filter](#cost-of-the-candidate-filter)
- [Inherited conventions, confirmed in the code](#inherited-conventions-confirmed-in-the-code)
- [Limitations known in advance](#limitations-known-in-advance)
- [What this study does not do](#what-this-study-does-not-do)

---

## Hypothesis

**Alerts where the 10-session high is recent outperform alerts where the high is
stale.**

Direction is specified in advance: fresh is predicted to beat stale. A
significant difference in the opposite direction is not a pass. It is a finding,
and it would be reported as one, but it fails this hypothesis.

---

## The two path metrics

Both are computed at the moment of each alert, over the last `recent_n` closes,
where `recent_n = config.RECENT_WINDOW_DAYS = 10`. Let `closes` be those
`recent_n` closes, oldest first, with `closes[-1]` being the alert day.

```
days_since_high    = (recent_n - 1) - argmax(closes)
drawdown_from_high = (max(closes) - closes[-1]) / max(closes)
```

`days_since_high` is 0 when the stock peaked today and 9 when it peaked at the
window start. `argmax` takes the **first** occurrence on ties, which is the
conservative choice: a tie between an earlier and a later bar at the same price
is recorded as the staler of the two, so the fresh group is never flattered by a
tie.

`drawdown_from_high` is 0 when the alert day *is* the high and positive
otherwise. It cannot be negative by construction.

### A known one-bar asymmetry, accepted deliberately

The live screener's price change uses `history["Close"].iloc[-(recent_n + 1)]`
as its starting price (`screener.py:117`), so it spans `recent_n + 1` closes —
11 bars for a 10-session change. The path metrics above span `recent_n` closes,
10 bars. The two windows are therefore offset by one bar: the price filter's
reference bar sits one session before the high-search window begins.

This is intentional. The high-search window should cover the move itself, not
the bar the move is measured from. It is recorded here so that it is a stated
choice rather than a discovered bug, and step 4 pins it with explicit fencepost
tests — this repo has already shipped one off-by-one in exactly this kind of
index arithmetic.

---

## Fresh versus stale

**Confirmatory split, one comparison only:**

| group | `days_since_high` |
|---|---|
| fresh | 0, 1, 2 |
| stale | 5, 6, 7, 8, 9 |
| dropped | 3, 4 |

Buckets 3 and 4 are genuinely ambiguous. Lumping them in with stale would
dilute the contrast being measured, so they are excluded from the confirmatory
test. The cost is sample size and the fact that this test alone does not say
where a live cutoff should sit.

Reporting all ten buckets as the test would be the forking-paths trap: with ten
buckets some split always looks good, and there would be no honest way to say
whether it was found or invented. The ten-bucket view is reported, but as
exploratory description only — see below.

---

## Forward returns and the baseline

Forward return at horizon `h`, in sessions, for an alert on date `d`:

```
fwd_h  = close[d + h] / close[d] - 1
```

The baseline is the **date-matched universe mean**: for each date, the
cross-sectional mean of `fwd_h` across every usable ticker in the sample,
computed by `build_baseline` in `research/phase1_validation/backtest.py:194`.

```
excess_h = fwd_h - baseline_h[d]
```

Excess return, not raw return, is the quantity tested. A group that returned
+8% where the universe returned +8% found nothing.

**Horizons: 5, 10 and 21 sessions.**

**The confirmatory horizon is 10 sessions, and only 10.** It is the horizon that
matches the window the metric is computed over, which is why it was chosen —
not because it looked best, which could not have been known when this was
written. Horizons 5 and 21 are reported as supporting evidence with no
criterion attached. A real effect should point the same way at all three; if 10
passes while 5 and 21 point the other way, that is noise and will be said so.

---

## Sample: primary and replication

| role | cache | tickers | coverage |
|---|---|---|---|
| **primary** | `cache/backtest_history.pkl` | 60 | 2023-08-28 → 2026-08-25 |
| replication | `cache/universe178_history.pkl` | 178 | 2023-06-01 → 2026-08-28 |

Alerts are the trigger rows at the live thresholds (`VOLUME_SURGE_THRESHOLD =
1.75`, `PRICE_CHANGE_THRESHOLD = 0.07`). On the primary cache this reproduces
the existing 498-alert sample in `results/phase1/signals.csv`, of which 495 have
a 10-session excess return.

> **This last sentence is wrong.** See the correction at the top of this
> document. The sample definition in the sentence before it stands.

The 60-ticker set is primary because every phase-1 finding was measured on it,
so this study stays comparable to them. Its survivorship bias is real but bites
less here than usual: it would wreck a question like "what return do alerts
earn", because surviving names drift up, but this study compares two groups
*inside* the same biased universe and the bias lands on both arms roughly
equally. The difference between fresh and stale is far more robust to it than
the levels are.

The 178-ticker set deliberately includes laggards, distributors and names with
no AI story, so it is the harder test of whether the effect is an artefact of
how the ticker list was built.

### Disagreement rule, fixed in advance

Declaring both runs without a rule for conflict would be two shots at a positive
result. Therefore:

| primary (60) | replication (178) | reported as |
|---|---|---|
| pass | pass | **pass** |
| pass | fail | **fragile** — not a pass |
| fail | pass | **fail**, with the replication noted as a reason to look again |
| fail | fail | **fail** |

---

## The pass criterion

The study passes if **all** of the following hold on the primary sample:

1. The quantity is the **fresh-minus-stale difference in mean 10-session excess
   return**, in percentage points.
2. The 95% confidence interval on that difference, from a **bootstrap clustered
   by ticker** (10,000 iterations, seed 42, the method in
   `research/phase1_validation/significance_testing.py:48`), **excludes zero on
   the positive side**.
3. The point estimate is **at least +2.0 pp**.
4. Both groups meet the minimum sample size below.

Clustering by ticker, not by alert, is the honest choice: one ticker contributed
24 alerts to the existing sample, all from the same stock over overlapping
periods, driven by the same underlying move. Those are not 24 independent
pieces of evidence.

Condition 3 exists because the interval alone can clear zero on a difference too
small to be worth losing alerts over. +2.0 pp is a judgement call about what
would justify changing a live filter, fixed now so it cannot be revised toward
whatever the data turns out to show.

### Minimum sample size

**100 alerts and 20 distinct tickers, per group.** Both floors, because 100
alerts drawn from 3 tickers is nearer 3 pieces of evidence than 100, and the
clustered bootstrap resamples tickers, so the ticker count is what sets the real
width of the interval.

These floors are fixed now and are **not** moved after the counts are seen. A
group below either floor is reported as **underpowered, not dropped silently**.

---

## Minimum detectable effect

Recorded before any result, so that a null can be told apart from a design that
could never have found anything.

The dispersion input is the standard deviation of 10-session excess return
across the existing 495-alert primary sample: **17.16 pp**. This is a marginal
dispersion of the outcome variable; it carries no information about the
fresh/stale contrast, so measuring it now does not peek at the hypothesis.

The clustering design effect was also measured on that sample: the
clustered-by-ticker bootstrap standard error of the mean is **0.767 pp** against
**0.771 pp** for the i.i.d. standard error, a ratio of **0.99**. At the
10-session horizon, clustering costs essentially nothing — unlike the 20-session
horizon, where phase 1 found it mattered. The tables below therefore use no
clustering inflation, and step 5 reports the actual clustered interval
regardless.

For a two-group difference with `n` per group:

```
CI half-width (what a difference must exceed for its 95% CI to clear zero)
    = 1.96 * 17.16 * sqrt(2/n)

MDE at 80% power (the smallest true effect this design would reliably detect)
    = 2.80 * 17.16 * sqrt(2/n)
```

| n per group | 95% CI half-width | MDE at 80% power |
|---|---|---|
| 100 | 4.76 pp | 6.79 pp |
| 150 | 3.88 pp | 5.55 pp |
| 200 | 3.36 pp | 4.81 pp |
| 250 | 3.01 pp | 4.30 pp |

**The primary MDE is the 80%-power column.** The exact value is read off the row
matching the actual group counts; the formula and the dispersion are fixed here.

### This design is very likely underpowered against its own threshold

At every plausible group size for this sample, the MDE **exceeds the 2.0 pp pass
threshold** — by roughly a factor of two. Detecting a true 2.0 pp difference at
80% power would need about **1,150 alerts per group**, against the few hundred
available.

This is recorded now, in advance, because it determines how a null must be read.
A null from this design will **not** mean "the path does not matter". It will
mean the study could not see an effect of the size worth acting on. Only an
effect several times larger than the threshold is detectable here, which makes a
pass informative and a null nearly uninformative about the 2.0 pp question.

---

## The three outcomes step 5 may report

Not two. Exactly one of these:

1. **Pass** — all four pass conditions met.
2. **Interpretable null** — criterion not met, and the MDE at the realised group
   sizes is **below** 2.0 pp. The design could have seen an effect worth acting
   on, and did not. Evidence against the hypothesis at the threshold that
   matters.
3. **Underpowered** — criterion not met, and the MDE is **above** 2.0 pp. The
   study could not have detected an effect worth acting on. This must be said
   plainly, and must not be reported as evidence against the hypothesis.

Given the table above, outcome 3 is the likely one if the effect is not large.

---

## Secondary and exploratory, with no criterion attached

None of the following can produce a pass. They are description.

- **Monotonicity, a stated secondary expectation.** Mean excess return by each
  of the ten `days_since_high` buckets. If the recency of the high genuinely
  matters, returns should decline roughly smoothly as `days_since_high` rises. A
  smooth gradient is evidence of a mechanism. If only bucket 7 is bad while 6
  and 8 are fine, that is noise wearing a result's clothes — worth knowing even
  if the confirmatory test passes.
- **`drawdown_from_high`.** Reported descriptively and as a continuous
  correlate of forward excess return. It gets **no** pass criterion: the
  hypothesis names the recency of the high, not the depth of the pullback, and
  giving drawdown its own criterion would be a second shot at a positive.
  Making it confirmatory later would require its own preregistered threshold and
  a correction for testing twice.
- **Horizons 5 and 21.**
- **The 178-ticker replication**, which can downgrade a pass to fragile per the
  disagreement rule but cannot create one.
- **`data/snapshots/`**, as an out-of-sample look only. 57 daily files,
  2026-08-26 onward. They hold no per-ticker daily close series, so path metrics
  must come from the pickles, and forward returns run past the pickles' end —
  the 21-session horizon only completes for snapshot dates before roughly
  mid-October 2026. Too small and too truncated to confirm anything.

---

## Cost of the candidate filter

Reported whatever the outcome, because a filter that improves returns while
removing most alerts may still not be worth it.

The candidate filter is **reject alerts with `days_since_high` >= 5**, mirroring
the confirmatory stale definition. Reported as the fraction of historical alerts
it would have removed.

The `>= 3` variant is reported alongside it, because the dropped middle means
`>= 5` understates what a live filter would actually cost: buckets 3 and 4 are
excluded from the test but a live filter would have to make a decision about
them.

---

## Inherited conventions, confirmed in the code

- **`SIGNAL_GAP_DAYS = 10` counts trading sessions, not calendar days.**
  Confirmed at `backtest.py:183`: the gap is `len(df.loc[kept[-1]:d]) - 1`, a
  count of rows in a frame indexed by trading sessions. Alerts closer than 10
  sessions to the previous alert for the same ticker are treated as
  continuations of one episode rather than new events. Without this, a single
  two-week surge counts as ten alerts and inflates the sample.
- **`build_baseline` includes that date's alerting tickers** in the
  cross-sectional mean. Confirmed at `backtest.py:204`: it concatenates the
  forward-return column of every usable ticker frame and takes the row mean,
  with no exclusion of names that triggered that day. See the limitations note
  below.

Both are inherited unchanged so that this study's alert set is identical to the
one phase 1 measured.

---

## Limitations known in advance

1. **Underpowered against its own threshold.** The central limitation. See the
   MDE section.
2. **Alerting tickers are inside their own baseline.** An alert's own forward
   return contributes to the mean it is compared against, which shrinks every
   excess return slightly toward zero. In a difference of two groups this mostly
   cancels — but only to the extent that the two groups share dates. Where fresh
   and stale alerts cluster on different dates, the cancellation is partial and
   a small bias survives. With ~60 tickers in the baseline the per-alert
   contribution is roughly 1/60, so the residual is small relative to the
   effects being discussed. Noted, not corrected: correcting it would change the
   baseline definition and break comparability with phase 1.
3. **Survivorship bias** in the 60-ticker universe. Argued above to be largely
   common to both arms; the 178-ticker replication is the check.
4. **Overlapping periods.** Alerts close together in time share market
   conditions and are not independent, even after the 10-session gap rule. The
   clustered bootstrap addresses clustering within a ticker, not across tickers
   on the same date.
5. **One sector, one regime.** The 2023-2026 AI buildout. Nothing here
   generalises to other sectors or other regimes.
6. **No point-in-time fundamentals.** The TTM cash-flow gate is not applied
   historically, so these alerts reflect the two technical conditions only.
   Inherited from phase 1.
7. **No costs.** Spreads, slippage and taxes are ignored.
8. **Adjusted closes.** History is `auto_adjust=True`, so splits and dividends
   are back-adjusted. The path of a move is measured on adjusted prices, which
   is correct for returns but means the "high" is not the headline price a
   trader saw at the time.

---

## What this study does not do

It does not change the screener. `screener.py`, `config.py`, `notifier.py` and
`snapshot.py` are untouched. This is measurement only.

If the result is positive, whether to act on it is a separate decision, made
afterwards, and would need its own out-of-sample validation before anything goes
live.
