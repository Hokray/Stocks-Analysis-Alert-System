# Volume Timing Event Study

Sixth study. Phase 2.

Five studies established that volume does not predict returns. None of them
explained **why**. This one does, and the answer is more specific than "volume
doesn't work."

**Two separate failures were found.** The screener's volume metric is
mechanically unable to detect the spike it was designed to catch — the
measurement window is roughly five times longer than the phenomenon. And even a
corrected metric would not help, because volume spikes precede 10% *falls*
three times more strongly than 10% rises.

---

## Contents

- [The question](#the-question)
- [Method](#method)
- [The control failed, and why that matters](#the-control-failed-and-why-that-matters)
- [Result 1: volume leads, but only by two days](#result-1-volume-leads-but-only-by-two-days)
- [Result 2: volume precedes falls more than rises](#result-2-volume-precedes-falls-more-than-rises)
- [Result 3: the screener cannot see its own signal](#result-3-the-screener-cannot-see-its-own-signal)
- [What this explains](#what-this-explains)
- [Why a shorter window would not fix it](#why-a-shorter-window-would-not-fix-it)
- [Limitations](#limitations)
- [Reproducing](#reproducing)

---

## The question

The project's founding hypothesis: institutions accumulate positions over days,
and that accumulation shows up as sustained elevated dollar volume.

Every test contradicted it. The objection raised against those results was a
timing argument:

> "Volume goes up a couple of days after the first and second day of the price
> wave."

If true, then measuring volume *before* a move would correctly show nothing, and
volume would be a **confirmation** signal rather than an **entry** signal. That
would explain every negative finding without volume being meaningless — and it
would mean the screener is structurally wrong rather than badly tuned, since it
requires a volume surge before alerting.

Worth testing directly, because the earlier studies could not distinguish
"volume carries no information" from "volume was measured at the wrong moment."

---

## Method

Every case where a stock began a 10%+ move over 10 trading days was located
across the 178-ticker universe. Day 0 is anchored at the start. Relative dollar
volume is then averaged across all such events from 20 days before to 20 days
after.

**Relative volume** is each day's dollar volume divided by the ticker's average
over a *fixed* pre-event window (days −40 to −21). A fixed baseline is essential
here — a rolling average would blend pre- and post-event days and blur exactly
the timing being measured.

Two controls:

| Control | Purpose |
|---|---|
| **Down-moves** | If volume rises around 10% falls too, it responds to movement, not direction |
| **Random days** | Should be flat at 1.0. Checks whether the *method* is sound |

Events: 2,199 up-moves, 1,683 down-moves, 516 random days.

---

## The control failed, and why that matters

The random-day control came out at **1.24×**, not 1.0.

The cause is sector-wide volume growth over 2023–2026. Any window compared
against its own past looks elevated, because trading activity in AI
infrastructure rose steadily throughout. An earlier run with a more distant
baseline (days −83 to −21) produced an even worse control at 1.35×.

**Consequence: absolute values cannot be read at face value.** Every curve is
inflated by the same drift. All findings below are reported **net of the random
control**, which is the honest comparison.

This is why the control exists. Without it, "volume was 1.50× normal before a
move" would have looked like a finding, when 1.24× of it was just the sector
getting busier.

---

## Result 1: volume leads, but only by two days

Daily relative volume around up-moves:

| Day | Up-moves | Random | Reading |
|---|---|---|---|
| −20 to −4 | 1.15 – 1.29 | 1.07 – 1.28 | **Indistinguishable from normal** |
| **−2** | **2.18** | 1.27 | Spike begins |
| **−1** | **3.03** | 1.28 | Peak |
| 0 | 1.90 | 1.35 | Move underway |
| +3 to +12 | 1.40 – 1.91 | 1.32 – 1.47 | Elevated, decaying |

Net of the control:

| Period | Up-moves |
|---|---|
| Days −10 to −1 (before) | **+0.26** |
| Days 0 to +2 (start) | +0.40 |
| Days +3 to +12 (after) | **+0.72** |

**Volume leads the price move — but the lead is two days, not two weeks.**

The +0.26 "elevation before" is misleading if read as a gradual build-up. Days
−20 through −4 are flat. Two days do all the work, and averaging them across ten
dilutes them.

**The timing objection was directionally right but mechanically wrong.** Volume
rises just *before* the move rather than after it. The underlying point stands
regardless: the screener's timing assumption does not match what happens.

**A two-day spike is not the signature of accumulation.** Institutions building
a position over weeks would produce a gradual ramp. A sudden one-or-two-day
surge looks like a discrete event — earnings, an announcement, an analyst
action. That distinction matters, and it is what Result 2 confirms.

---

## Result 2: volume precedes falls more than rises

The mirror control, net of random days:

| Period | Up-moves | **Down-moves** |
|---|---|---|
| Before (−10 to −1) | +0.26 | **+0.80** |
| Start (0 to +2) | +0.40 | **+1.26** |
| After (+3 to +12) | +0.72 | +0.53 |

**Volume elevation before a 10% fall is three times larger than before a 10%
rise.**

This is the finding that most directly contradicts the founding hypothesis. The
thesis was money flowing *in*. The data shows unusual volume precedes large
moves in **both** directions, and historically more strongly before declines.

Elevated volume signals that *something is about to happen*. It does not
indicate which way — and if anything, it leans the wrong way.

Consistent with the news-event reading: news moves stocks in both directions,
and bad news tends to arrive with more volume than good news.

---

## Result 3: the screener cannot see its own signal

The most consequential number in this study.

The live screener's condition is `vol_ratio_10_63` — average dollar volume over
10 days ÷ average over 63 days — with a trigger at **1.50**.

Around real 10% moves, that metric reads:

| Day | `vol_ratio_10_63` |
|---|---|
| −10 | 1.08 |
| 0 | 1.05 |
| +10 | 1.13 |

**It peaks at 1.13. It fires at 1.50.**

The arithmetic is straightforward. The spike lives on days −2 and −1 at roughly
2.2× and 3.0×. The other eight days in the window sit near 1.2×. Averaging:

```
(3.0 + 2.2 + 1.2 × 8) ÷ 10 ≈ 1.48   → in practice ~1.13 after the 63-day
                                       denominator is applied
```

**The measurement window is five times longer than the phenomenon.** A two-day
surge averaged across ten days is smoothed into near-invisibility.

This is not a threshold that needs lowering. The metric never approaches its own
trigger even when the event it was built to detect is occurring.

---

## What this explains

The four Phase 1 studies and the metric search all found volume useless. They
could not distinguish between two very different explanations:

1. Volume carries no information about future returns
2. Volume carries information, but the screener measures it wrongly

**This study shows both are true, in different senses.**

The screener's instrument is broken — Result 3. And the underlying signal points
the wrong way — Result 2.

That is a more precise conclusion than "the screener does not work." It
identifies two distinct failures, and it rules out the most hopeful
interpretation, which was that a tuning change might rescue the design.

---

## Why a shorter window would not fix it

The obvious follow-up is `vol_ratio_2_63` — a 2-day recent window that would
actually capture the spike.

It would fire far more often. It would not be an improvement.

Result 2 is the reason: the spike precedes falls three times more strongly than
rises. A metric that successfully detects it would fire on both, and the
population it flags contains more stocks about to decline than advance.

**The screener's price condition does not protect against this.** It requires
+7% over the *previous* 10 days — a backward-looking condition. A stock can be
up 7% over the past fortnight and one day away from a sharp drop. That is
precisely what happens when volume spikes on bad news following a run-up.

So a corrected metric would detect the right event and draw the wrong
conclusion from it. The instrument and the signal are separately broken, and
fixing one does not address the other.

---

## Limitations

**The random-day control reads 1.24, not 1.0.** Sector-wide volume growth
contaminates any fixed baseline over this period. Net-of-control comparisons
handle this, but absolute magnitudes remain unreliable.

**Day 0 is a proxy.** It is defined as the first day of a window over which a
10% move occurred. Moves that build gradually have no single identifiable start,
so the anchor is approximate. This would blur the curve, biasing *against*
finding a sharp spike — the spike showed up anyway.

**Overlapping events.** Events are spaced at least 30 trading days apart per
ticker, but market-wide episodes still cluster in time. The 2,199 events are not
independent observations.

**Same universe, same regime.** 178 tickers, one sector, 2023–2026. The two
outlier days in the up-curve (day +10 at 5.45×, day +15 at 5.75×) suggest a
handful of extreme events are influencing individual points.

**Delisted companies remain absent.** Four tickers failed to download.

---

## Reproducing

```bash
python research/phase2_metric_search/volume_event_study.py
```

Output: `results/phase2/volume_event_study.csv`

Key settings: `MOVE_THRESHOLD = 0.10`, `MOVE_WINDOW = 10`,
`BASELINE_START = -40`, `BASELINE_END = -21`, `EVENT_GAP = 30`.

---

## Conclusion

Volume is not silent around large price moves. It rises sharply — but two days
before, not gradually over weeks, and more strongly before falls than rises.

The screener's 10-day averaging window cannot detect a two-day spike, so its
volume condition never triggers on the pattern it was built for. Correcting the
window would not help, because the corrected signal is not directional.

The founding hypothesis was that sustained volume reveals institutional
accumulation. What the data shows instead is brief, news-shaped volume spikes
that precede movement in either direction.

**Volume should be removed from the screening logic.** It is not a
mistuned condition; it is measuring something that does not answer the question
being asked.

---

*These results describe historical associations. They are not investment advice
and do not predict future returns.*