# Phase 2 — Metric Search

Phase 1 established that the original three conditions do not work. Phase 2 asks
what might.

**Status: ongoing.** Nothing here has been confirmed, and no changes to the live
screener follow from it.

---

## What has been done

**[METRICS_TESTED.md](METRICS_TESTED.md)** — 31 metrics across five families
(volume, momentum, position in range, volatility, trend quality), tested against
a 178-ticker universe over Sep–Nov 2024 and Sep–Nov 2025.

The question is deliberately inverted from Phase 1. Rather than asking *do
volume surges predict returns*, it asks *did stocks that went on to rise 10%
look different beforehand* — and crucially, compares them against the stocks
that did not.

### Why the control group matters

The original framing was "find stocks that rose 10% and see what their metrics
looked like." That cannot answer the question. If winners averaged a volume
ratio of 1.6, it means nothing until you know what non-winners averaged. If both
were 1.6, the metric describes stocks in general, not future winners.

Selecting observations by their outcome and describing them produces patterns
that are real and useless — every lottery winner bought a ticket.

### Controls

**Mirror test.** Each passing metric is re-tested against stocks that *fell*
10%. A metric separating risers but not fallers is directional. One separating
both equally predicts magnitude only, and is useless for entry.

**Permutation test.** Winner labels are shuffled and the whole search re-run 500
times, measuring how many metrics pass by chance. With 31 metrics, some will
separate impressively at random — this quantifies how many.

---

## Current result

Eight metrics passed both periods and both controls, against a random-label
baseline of 0.08 (probability of 8+ by chance: effectively zero).

They collapse into **three findings**, since the five volatility measures
describe one phenomenon:

| Finding | Metrics | Direction |
|---|---|---|
| Volatility | `atr_pct`, `volatility_20d_pct`, `volatility_60d_pct`, `bollinger_width_pct`, `gap_freq_21` | Winners more volatile |
| Established uptrend | `ma50_vs_ma200`, `pct_above_52w_low` | Winners in uptrend, off lows |
| Momentum deceleration | `momentum_accel` | Winners **slowing**, not accelerating |

Together: a pullback within an uptrend.

**No volume metric passed** — including the live screener's own condition
(`vol_ratio_10_63`), at −0.33 and +0.09. A fifth independent line of evidence
against the original thesis.

**One result contradicts the screener directly.** It requires +7% momentum over
10 days; `momentum_accel` says winners were decelerating.

---

## Why this is not yet a finding

Two periods is two observations, both drawn from the same sector during the same
buildout. In Sep–Nov 2024, 72% of the universe rose 10% — a melt-up, where
"which stocks rose" barely discriminates.

Phase 1 is the cautionary tale. The persistence effect was consistent across
three analyses, mechanistically plausible, and statistically clean. It reversed
entirely once the universe changed.

### The prediction, stated in advance

> Among live signals, stocks with above-median 20-day volatility, a 50-day MA
> above their 200-day MA, and negative momentum acceleration will beat the
> universe baseline more often than those without.

Recorded here before testing so the eventual check is genuinely out-of-sample.

---

## Open work

**Volume timing event study.** Phase 1 and Phase 2 both show volume does not
predict a move. They do not show whether volume rises *during* one. If it lags
the price move, volume is confirmation rather than entry signal — which would
explain every result so far, and would mean measuring it on day one correctly
shows nothing.

**More time periods.** Only Sep–Nov has been tested. A seasonal artefact cannot
be ruled out.

**Out-of-sample validation.** The live system accumulates signals no analysis
has seen.

**Transaction costs.** Never modelled. Would make every result worse, not
better.

---

## Running it

From the repository root:

```bash
python research/phase2_metric_search/winner_profile.py   # 5 metrics, first pass
python research/phase2_metric_search/metric_search.py    # 31 metrics + controls
```

Output lands in `results/phase2/`. Universe: `data/tickers_universe.csv` (178
tickers, of which 60 were hand-picked and 118 added neutrally by category).