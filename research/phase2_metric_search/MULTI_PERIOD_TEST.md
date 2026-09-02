# Multi-Period Robustness Test

Seventh study. Phase 2.

The metric search found eight metrics that separated future winners from
non-winners across Sep–Nov 2024 and Sep–Nov 2025. This tested whether they hold
in other quarters.

**None do. Zero of the eight, and zero of all thirty-one, survived six
periods.** The eight were a seasonal artefact — they separate in autumn and not
otherwise, and several reverse sign entirely in spring.

---

## Contents

- [Why this was run](#why-this-was-run)
- [Method](#method)
- [Result 1: nothing survives](#result-1-nothing-survives)
- [Result 2: the signs reverse](#result-2-the-signs-reverse)
- [Result 3: it is a seasonal artefact](#result-3-it-is-a-seasonal-artefact)
- [Result 4: volume confirmed dead a seventh time](#result-4-volume-confirmed-dead-a-seventh-time)
- [What this changed](#what-this-changed)
- [Limitations](#limitations)

---

## Why this was run

The metric search tested 31 metrics against two periods and found eight passing
both, with a permutation control putting the odds of that by chance at
effectively zero.

Two problems with stopping there.

**Two observations is a thin basis.** A pattern that appears twice can appear
twice by luck.

**Both windows were the same season.** Sep–Nov 2024 and Sep–Nov 2025. A pattern
appearing only in autumn is a calendar coincidence, not a market effect, and
nothing in a two-autumn sample can tell the difference.

Phase 1 Study 4 is the direct precedent: an effect that held across three
analyses collapsed once the sample changed. Changing the sample is the only test
that finds this class of error.

---

## Method

The identical search, extended to six non-overlapping quarters:

- Mar–May 2024
- Jun–Aug 2024
- **Sep–Nov 2024** ← original
- Mar–May 2025
- Jun–Aug 2025
- **Sep–Nov 2025** ← original

History extended back to June 2022, since the metrics need roughly 252 trading
days of lookback and covering March 2024 requires more history than the earlier
run had.

**Pass criteria:** same direction in *all six* periods, and at least 0.30 SD in
at least four of them.

The direction requirement is the strict half. A metric that flips sign between
quarters is describing noise, however large the individual gaps look.

**How much stricter this is:** on pure random data, the two-period criteria
produce at least one false hit about 2% of the time. The six-period criteria
produce **zero** across 200 simulated trials.

Universe: 178 tickers, 172 usable. Same as the metric search.

---

## Result 1: nothing survives

**0 of 31 metrics passed. 0 of the original 8.**

`same_direction` is False for every single metric in the table. Not one pointed
the same way across all six quarters.

The permutation control returned 0.00 average hits on shuffled labels — matching
the real search exactly. The result is indistinguishable from chance because
both are zero.

---

## Result 2: the signs reverse

The failure is not weakness. It is reversal.

**20-day volatility**, the strongest of the eight:

| Period | Separation |
|---|---|
| Mar–May 2024 | **−0.38** |
| Jun–Aug 2024 | +0.05 |
| **Sep–Nov 2024** | **+0.51** |
| Mar–May 2025 | +0.57 |
| Jun–Aug 2025 | −0.10 |
| **Sep–Nov 2025** | **+0.48** |

In autumn, volatile stocks outperformed by ~0.5 SD. In spring 2024 they
*under*performed by nearly the same margin.

All eight show this pattern. Same size gaps, opposite directions, depending on
the quarter.

A real effect does not reverse direction between adjacent quarters. Two windows
happening to agree is what noise looks like when you only check twice.

---

## Result 3: it is a seasonal artefact

Averaging the two autumn periods against the four others:

| Metric | Autumn mean | Other seasons | Autumn-only |
|---|---|---|---|
| gap_freq_21 | +0.55 | **+0.04** | Yes |
| atr_pct | +0.52 | **+0.04** | Yes |
| volatility_60d_pct | +0.53 | **+0.09** | Yes |
| volatility_20d_pct | +0.49 | **+0.04** | Yes |
| bollinger_width_pct | +0.49 | **+0.04** | Yes |
| ma50_vs_ma200 | +0.40 | **+0.05** | Yes |
| pct_above_52w_low | +0.39 | **−0.00** | Yes |
| momentum_accel | −0.38 | **+0.07** | Yes |
| return_126d_pct | +0.47 | +0.06 | Yes |
| return_63d_pct | +0.44 | −0.08 | Yes |
| pct_vs_ma200 | +0.40 | −0.01 | Yes |

Eleven metrics separate meaningfully in autumn and essentially not at all in any
other season. Autumn values of 0.4–0.55; everything else near 0.04.

**All eight of the original finding are in that list.**

Sep–Nov happened to be the window the analysis started with, and it happens to
be the one where these patterns appear.

### Is it really "seasonal"?

Probably not, in the sense of a recurring calendar effect. Compare the two
springs:

| Metric | Mar–May 2024 | Mar–May 2025 |
|---|---|---|
| volatility_20d | **−0.38** | **+0.57** |
| gap_freq_21 | **−0.34** | **+0.50** |
| atr_pct | **−0.33** | **+0.43** |

Same season, different years, opposite signs. So "spring behaves one way" is
also false.

The two autumns agreeing is most likely coincidence rather than a calendar
mechanism. **A follow-up cross-asset study tested the obvious alternative
explanation — that volatile stocks lead when markets rise — and found a
correlation of +0.05 between market regime and volatility separation. No
support.** See [MARKETS_ANALYSIS.md](MARKETS_ANALYSIS.md).

No mechanism is required. Two quarters aligning out of six is unremarkable.

---

## Result 4: volume confirmed dead a seventh time

`vol_ratio_10_63`, the live screener's condition, across six quarters:

```
+0.12   −0.01   −0.33   −0.05   −0.14   +0.09
```

Signs scattered, magnitudes near zero, `n_meaningful` = 1 of 6.

Every volume metric behaved the same way. `up_volume_share`, `ad_slope_21`,
`obv_slope_21`, `dollar_vol_musd` — all near zero, none consistent.

---

## What this changed

**The Phase 2 candidate finding is withdrawn.** Volatility, established uptrend
and momentum deceleration do not hold outside autumn.

**Screener v2 was not built.** The plan had been to construct a second screener
on those metrics. This test ran first, specifically to check them, and it killed
the plan before any code was written.

That is the test doing its job. The cost was one script; the alternative was
building and deploying a system on a seasonal coincidence.

**No changes to the live screener.**

**Two findings have now been withdrawn this way** — the persistence effect in
Phase 1 (killed by changing the universe) and this one (killed by changing the
time period). Same failure mode both times: a pattern that looked robust because
it had only been tested on one narrow slice.

---

## Limitations

**Six quarters is still few.** A metric could be real and fail here through
noise in one quarter. But the burden runs the other way — the eight were
presented as robust, and they are not.

**Base rates vary enormously**, from 37% to 72% of the universe rising 10%. In a
quarter where 72% of stocks rose, "which ones rose" barely discriminates, so
that period contributes less information than its row suggests.

**Same universe, same sector, same overall regime.** 2024–2026, AI
infrastructure. Nothing here generalises further.

**Four tickers failed to download** — COMM, CSWI, BITF, THR — the ongoing
survivorship limitation.

---

## Reproducing

```bash
python research/phase2_metric_search/multi_period_test.py
```

Output: `results/phase2/multi_period_test.csv`

Settings: `MOVE_THRESHOLD = 0.10`, `SEPARATION_BAR = 0.30`,
`N_PERMUTATIONS = 300`, six periods defined in `PERIODS`.

---

## Conclusion

Eight metrics that looked robust across two periods hold in none of six. They
separate winners in autumn and not otherwise, and reverse sign in spring.

The most likely explanation is the simplest: two quarters out of six agreed by
chance, and the analysis began with those two.

**The lesson repeats Phase 1.** A finding that has only been tested on one slice
of data — one universe, one season, one regime — has not been tested. The
question is never whether a pattern is visible, but whether it survives being
looked at from somewhere else.

---

*These results describe historical associations. They are not investment advice
and do not predict future returns.*