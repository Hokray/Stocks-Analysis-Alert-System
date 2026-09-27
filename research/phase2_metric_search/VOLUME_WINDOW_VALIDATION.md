# Volume Window Validation

Ninth study. Phase 2.

Prompted by a proposal to change the screener's volume condition:

> recent window 10 days → 5 days ("catch the wave earlier")
> baseline window 63 days → 20 days ("only 1 month")

**The proposal was half right, and the half that was right was the half I
argued against.**

Shortening the *baseline* is supported by the data. Shortening the *recent*
window is not — the strongest configurations all keep it at 10. A measurement
bug was also found and fixed along the way, and it had been inflating the
apparent result by up to 4×.

This is the first configuration change in the project backed by a
pre-registered test.

---

## Contents

- [Why this was run](#why-this-was-run)
- [Part 1: the sweep](#part-1-the-sweep)
- [Test 1: the window overlap bug](#test-1-the-window-overlap-bug)
- [Test 2: volatility versus direction](#test-2-volatility-versus-direction)
- [Test 3: per-quarter stability, pre-registered](#test-3-per-quarter-stability-pre-registered)
- [Who was right about what](#who-was-right-about-what)
- [Configuration changes](#configuration-changes)
- [Limitations](#limitations)
- [Conclusion](#conclusion)

---

## Why this was run

The volume event study (Study 6) established a specific defect. Around a real
10% move, volume spikes on days −2 and −1 at roughly 2.2× and 3.0× normal.
Everything from day −20 to day −4 is flat.

The live screener averages **10 days**. A two-day spike diluted across ten days
is smoothed into invisibility: around those same events, `vol_ratio_10_63` reads
**1.13** against a trigger of **1.50**. The metric never approaches its own
threshold even when the thing it was built to detect is happening.

So the window lengths were worth revisiting. The question was which window, and
in which direction.

---

## Part 1: the sweep

Eleven recent/baseline pairs × four triggers, evaluated across six quarters.

**Result: every one of the top six rows by edge had `recent = 10`.** Not one
shorter recent window placed.

There was also a dose-response at two of the three baselines — a stricter
trigger producing a larger edge:

| baseline | 1.35 | 1.50 | 1.75 |
|---|---|---|---|
| 20 | 11.83 | 16.67 | 13.09 |
| 30 | 6.81 | 13.01 | **17.04** |
| 63 | — | 7.83 | 12.57 |

Monotone at 30 and 63. Noise does not usually arrange itself in a gradient, and
there is a plausible mechanism: a 2-day window is dominated by single-day events
(earnings, index rebalances) which mean-revert, whereas a sustained 10-day
elevation is a different phenomenon.

Two configurations were taken forward: **10/30 @ 1.75** (best edge) and
**10/20 @ 1.50** (runner-up).

---

## Test 1: the window overlap bug

The sweep computed the ratio as:

```python
dv.rolling(recent_n).mean() / dv.rolling(base_n).mean()
```

The baseline **includes** the recent window. At 10/20, half the denominator is
the numerator — and the ratio is mathematically capped at `base_n / recent_n`.

Verified directly: with a 50× spike injected into the recent window, the
overlapping ratio at 10/20 tops out at **1.96** against a ceiling of 2.0. With a
separate baseline the same spike reaches **50.0**.

So a 1.75 trigger on a 10/20 pair was being tested against a wall at 2.0. That
is why only 189 observations survived in that cell of the sweep and why 10/20
broke the dose-response.

Recomputing both configurations with a **separate** baseline — the `base_n` days
*ending* `recent_n` days ago:

| Config | Baseline | Ceiling | Signals fired | Fire rate | Rise edge |
|---|---|---|---|---|---|
| 10/30 @ 1.75 | overlapping | 3.0 | 1,492 | 2.34% | **+17.04pp** |
| 10/30 @ 1.75 | **separate** | none | 5,569 | 8.74% | **+10.24pp** |
| 10/20 @ 1.50 | overlapping | 2.0 | 1,106 | 1.73% | **+16.67pp** |
| 10/20 @ 1.50 | **separate** | none | 9,424 | 14.77% | **+4.69pp** |

**10/20's edge collapsed from 16.67pp to 4.69pp — a 3.6× reduction.** Its
apparent strength in the sweep was largely the ceiling artificially restricting
which days could fire.

10/30 held up better, dropping from 17.04 to 10.24, and is the clearly superior
configuration once both are measured consistently.

**Everything below uses the separate baseline.** The live screener's current
10/63 pair has a ceiling of 6.3, well above its 1.50 trigger, so the bug was not
distorting live behaviour — but the definition should be clean, and it would
start binding immediately on any shorter baseline.

---

## Test 2: volatility versus direction

The sweep reported precision against a base rate of *rises only*. That cannot
distinguish between two very different signals.

Adding the fall side:

| Config | Rise precision | Rise base | **Rise edge** | Fall precision | Fall base | **Fall edge** |
|---|---|---|---|---|---|---|
| 10/30 @ 1.75 | 27.74% | 17.51% | **+10.24pp** | 11.92% | 9.43% | **+2.50pp** |
| 10/20 @ 1.50 | 22.23% | 17.54% | **+4.69pp** | 9.71% | 9.44% | **+0.27pp** |

For 10/30, firing raises the probability of a rise by a factor of **1.58** and
of a fall by **1.26**. Both go up — that is the volatility component. Rises go
up more — that is the directional component.

### The conditional test

The sharper question: *given that a 10% move is coming, does the metric predict
which way?*

| Config | Rises, when fired | Rises, all moves | **Direction edge** |
|---|---|---|---|
| 10/30 @ 1.75 | 69.94% | 65.00% | **+4.94pp** |
| 10/20 @ 1.50 | 69.60% | 65.02% | **+4.58pp** |

Directional content exists, and it is modest. Roughly 5 percentage points on a
base of 65%.

**The honest characterisation: this is mostly a volatility detector with a small
directional tilt.** Most of the +10.24pp rise edge comes from the metric
identifying that *something* is about to happen — and rises simply outnumber
falls roughly 2:1 in this universe over this period.

That 65/35 split is itself suspect. Survivorship bias inflates rises and
suppresses falls: every company that fell 40% and delisted is absent. In a
neutral universe the base split would be closer to even, and the directional
edge would likely look smaller.

---

## Test 3: per-quarter stability, pre-registered

Study 4 and the multi-period test both died because an average across quarters
concealed a reversal. So the threshold was fixed **before running**:

> Positive edge in at least **5 of 6** quarters, and the worst quarter still
> above **zero**. Only the two pre-registered configurations tested. No
> re-sweeping afterwards.

**10/30 @ 1.75**

| Quarter | Signals | Rise edge | Direction edge |
|---|---|---|---|
| Mar–May 2024 | 871 | +5.18 | +3.87 |
| Jun–Aug 2024 | 867 | +10.81 | +13.96 |
| Sep–Nov 2024 | 1,198 | +17.35 | +3.24 |
| Mar–May 2025 | 440 | +2.17 | **−6.43** |
| Jun–Aug 2025 | 1,044 | +6.12 | **−3.28** |
| Sep–Nov 2025 | 1,149 | +13.55 | +3.49 |

**6/6 positive. Worst quarter +2.17pp. PASS.**

**10/20 @ 1.50**

| Quarter | Signals | Rise edge | Direction edge |
|---|---|---|---|
| Mar–May 2024 | 1,394 | +2.04 | +4.78 |
| Jun–Aug 2024 | 1,401 | +8.47 | +13.05 |
| Sep–Nov 2024 | 2,112 | +5.43 | **−0.28** |
| Mar–May 2025 | 941 | +1.15 | +0.49 |
| Jun–Aug 2025 | 1,650 | +0.95 | **−2.29** |
| Sep–Nov 2025 | 1,926 | +7.35 | +4.25 |

**6/6 positive. Worst quarter +0.95pp. PASS.**

### The important asterisk

Both configurations pass the test **as written**, and the test was written
first. That stands.

But note the `direction_edge_pp` column: **4 of 6 positive for both**, with two
clearly negative quarters each. The pre-registration was on `rise_edge_pp`,
which Test 2 then showed to be a blend of volatility and direction.

**The volatility component is stable across all six quarters. The directional
component is not.**

This is not moving the goalposts — the threshold is not being revised, and the
result is not being reclassified as a failure. It is the decomposition telling
us *what* passed. What survived six quarters is a reliable detector of impending
movement, carrying a directional tilt that appears in four quarters and reverses
in two.

That is worth having, and it is a smaller claim than the headline number
suggests.

---

## Who was right about what

**The proposal — half validated.**

| Proposed | Verdict |
|---|---|
| recent 10 → 5 | **Not supported.** Every top configuration keeps recent = 10 |
| baseline 63 → 20 | **Direction correct.** Shorter baselines beat 63; 30 outperformed 20 once the overlap bug was fixed |

The underlying instinct — that the windows were wrong and the metric was too
sluggish — was right, and Study 6 had already demonstrated the mechanism. The
specific numbers needed testing rather than adopting.

**My own error, recorded.**

Earlier in this investigation I argued from the event study's spike shape that
*shorter* recent windows would work better, and produced arithmetic suggesting
3/63 or 2/63 would fire where 10/63 does not. The sweep found the opposite:
every top row had recent = 10, and no short-recent pair placed at all.

The spike shape was measured correctly. The inference from it was wrong. A
2-day window catches the spike but also catches every one-day news event that
mean-reverts; a 10-day window measures sustained elevation, which is the
different and apparently more informative phenomenon.

---

## Configuration changes

**`config.py`**

```python
RECENT_WINDOW_DAYS = 10          # unchanged — sweep found recent=10 dominates
BASELINE_WINDOW_DAYS = 30        # was 63
BASELINE_EXCLUDES_RECENT = True  # new — baseline ends where recent begins
VOLUME_SURGE_THRESHOLD = 1.75    # was 1.50
```

**`screener.py`** — the baseline must now exclude the recent window:

```python
recent_avg = dollar_volume.tail(recent_n).mean()

if getattr(config, "BASELINE_EXCLUDES_RECENT", False):
    baseline_avg = dollar_volume.iloc[-(recent_n + baseline_n):-recent_n].mean()
else:
    baseline_avg = dollar_volume.tail(baseline_n).mean()
```

The history-length guard also needs updating, from `baseline_n + 1` to
`recent_n + baseline_n + 1`.

**Unit tests** — `test_recent_volume_doubling_raises_the_ratio` asserts the
ratio lands strictly between 1.0 and 2.0, which was true only because the
overlapping baseline diluted it. With a separate baseline, doubling the recent
window gives exactly 2.0 and the assertion fails. The test needs its bound
changed, and that failure is the test correctly detecting the definition change.

**Email copy** — "3-month normal" becomes roughly six weeks.

### Why this is safe to change now

Earlier reasoning held that changing the live screener would reset the
out-of-sample experiment. That is no longer true.

The daily snapshot archive stores `close` and `volume` for all 178 tickers every
trading day. **Any** window combination can be recomputed from it
retrospectively, so the config change and the out-of-sample test are now
decoupled. Record the change date and both old and new configurations remain
testable.

### What to expect

The volume condition alone fires on 8.74% of ticker-days. The screener ANDs it
with price momentum and positive TTM cash flow, so the alert rate will be far
lower than that — but the net effect of a nearer baseline (which raises the
denominator in a growing sector) against a separate baseline (which lowers it)
is not predictable from these numbers.

Watch the alert rate for two weeks. If it floods, raise the trigger rather than
lengthening the baseline again.

---

## Limitations

**Configurations selected in-sample.** The two pre-registered configs came from
a sweep over the same six quarters used to test them. The pre-registration
protects against picking a new winner after seeing per-quarter results; it does
not undo the original selection.

**Effective sample size is far below the headline.** 5,569 signals sounds
decisive, but volume spikes persist for days, the forward window overlaps
between adjacent days, and sector names move together. The independent event
count is plausibly in the tens, not the thousands.

**Survivorship bias.** A 17.5% base rate for a 10% rise is high, and the 65/35
rise/fall split among big moves is inflated by the absence of delisted
companies. The directional edge is the figure most exposed to this.

**One regime.** 2024–2026, one sector, an equity bull market throughout.

**No transaction costs**, as throughout the project.

---

## Reproducing

```bash
python research/phase2_metric_search/volume_window_sweep.py
python research/phase2_metric_search/volume_validation.py
```

| Output | Contents |
|---|---|
| `results/phase2/volume_window_sweep.csv` | Full 11×4 grid |
| `results/phase2/volume_direction.csv` | Both-sided precision and conditional test |
| `results/phase2/volume_stability_*.csv` | Per-quarter breakdown per config |
| `results/phase2/volume_stability_verdict.csv` | Pass/fail summary |

---

## Conclusion

Three findings, in descending order of confidence.

**A measurement bug was found and fixed.** The baseline window included the
recent window, imposing a mathematical ceiling on the ratio. Removing it cut the
apparent edge of one candidate configuration by 3.6×. Any window pair where the
baseline is a small multiple of the recent window was affected.

**The window lengths were genuinely wrong, and are now better.** `10/30 @ 1.75`
with a separate baseline produced a positive edge in all six quarters with a
worst case of +2.17pp, against a threshold fixed in advance. This is the first
configuration change in the project supported by a pre-registered test.

**What passed is mostly a volatility detector.** The directional component is
roughly 5pp and appears in four of six quarters. The metric reliably identifies
that a large move is approaching; it identifies the *direction* only weakly.

After eight studies producing negative results and two formally withdrawn
findings, this is a modest positive — and stating its size accurately matters
more than that it is positive at all.

---

---

## Change log

| Date | Change |
|---|---|
| 2026-09-27 | `BASELINE_WINDOW_DAYS` 63 → 30; `BASELINE_EXCLUDES_RECENT` added, set `True`; `VOLUME_SURGE_THRESHOLD` 1.50 → 1.75. `RECENT_WINDOW_DAYS` unchanged at 10. |

The date matters. The daily snapshot archive stores raw `close` and `volume` for
all 178 tickers, so any window pair can be recomputed retrospectively — the old
`10/63 @ 1.50` configuration and the new `10/30 @ 1.75` one remain separately
testable on data neither has seen. Signals from before this date belong to the
old configuration; signals after it belong to the new one.

*These results describe historical associations. They are not investment advice
and do not predict future returns.*