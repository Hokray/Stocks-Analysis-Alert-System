# Metrics Tested

Reference for Study 5 (`backtest/metric_search.py`). Thirty-one metrics were
tested to find which ones separated stocks that went on to rise 10% from those
that did not.

**Method.** Every metric measured on the **first trading day** of a period, using
only data available up to that point. Stocks then labelled by what they did over
the following three months. The reported figure is the **separation** between
winners and non-winners, in pooled standard deviations.

| Separation | Reading |
|---|---|
| under 0.2 | negligible |
| 0.2 – 0.5 | small |
| 0.5 – 0.8 | moderate |
| over 0.8 | large |

A metric **passes** only if it reaches 0.30 in *both* periods *and* points the
same direction in both. Eight did, against a random-label baseline of 0.08.

Universe: 178 tickers across the six categories (172 usable). Periods:
Sep–Nov 2024 and Sep–Nov 2025.

---

## Contents

- [Volume and liquidity](#volume-and-liquidity)
- [Momentum](#momentum)
- [Position in range](#position-in-range)
- [Volatility](#volatility)
- [Shape and trend quality](#shape-and-trend-quality)
- [Full results table](#full-results-table)
- [What passed, and what it means](#what-passed-and-what-it-means)
- [Why eight passes is really three findings](#why-eight-passes-is-really-three-findings)
- [Caveats](#caveats)

---

## Volume and liquidity

Whether unusual amounts of money were changing hands. **This family contains the
screener's own core condition, and not one metric in it passed.**

| Metric | Definition | 2024 | 2025 | Passed |
|---|---|---|---|---|
| `vol_ratio_10_63` | Avg daily dollar volume 10d ÷ 63d — **the live screener's condition** | −0.33 | +0.09 | No |
| `vol_ratio_5_21` | Same, shorter windows | −0.39 | −0.03 | No |
| `vol_ratio_21_126` | Same, longer windows | +0.07 | +0.45 | No |
| `dollar_vol_musd` | Avg daily dollar volume, $M | +0.02 | −0.07 | No |
| `share_vol_ratio` | Share count version, no price weighting | −0.32 | −0.10 | No |
| `up_volume_share` | Share of 21-day dollar volume on up days | +0.06 | +0.08 | No |
| `obv_slope_21` | On-balance-volume change over 21 days | −0.29 | −0.19 | No |
| `ad_slope_21` | Accumulation/distribution line slope | +0.15 | +0.25 | No |

`up_volume_share` and `ad_slope_21` were included specifically to test buying
pressure directly rather than inferring it from price. Both came back near zero.

---

## Momentum

Recent price change over various lookbacks.

| Metric | Definition | 2024 | 2025 | Passed |
|---|---|---|---|---|
| `return_5d_pct` | 5-day return | −0.48 | +0.53 | No — sign flips |
| `return_10d_pct` | 10-day return — **the screener's condition** | −0.30 | +0.38 | No — sign flips |
| `return_21d_pct` | 21-day return | +0.09 | +0.44 | No |
| `return_63d_pct` | 63-day return | +0.22 | +0.66 | No |
| `return_126d_pct` | 126-day return | +0.24 | +0.70 | No |
| **`momentum_accel`** | 10-day return **minus** 21-day return | **−0.44** | **−0.32** | **Yes** |

The short-lookback returns flipped sign between periods — strong separation in
each, opposite directions. That is the signature of noise, not signal.

`momentum_accel` is the interesting one, and it is **negative**: winners had
10-day momentum *below* their 21-day momentum. They were decelerating, not
accelerating.

---

## Position in range

Where the price sits relative to its own recent history.

| Metric | Definition | 2024 | 2025 | Passed |
|---|---|---|---|---|
| **`pct_above_52w_low`** | % above the 1-year low | **+0.34** | **+0.44** | **Yes** |
| **`ma50_vs_ma200`** | 50-day MA vs 200-day MA — classic uptrend test | **+0.33** | **+0.47** | **Yes** |
| `pct_off_52w_high` | % below the 1-year high | −0.34 | +0.17 | No |
| `pct_vs_ma50` | % above/below the 50-day MA | −0.21 | +0.55 | No |
| `pct_vs_ma200` | % above/below the 200-day MA | +0.14 | +0.66 | No |
| `close_in_21d_range` | Where close sits in the 21-day high–low range | +0.01 | +0.31 | No |

---

## Volatility

How much the stock moves day to day. Five different instruments, one underlying
phenomenon — all five passed.

| Metric | Definition | 2024 | 2025 | Passed |
|---|---|---|---|---|
| **`atr_pct`** | Average true range over 14 days, % of price | **+0.49** | **+0.55** | **Yes** |
| **`volatility_20d_pct`** | Annualised SD of daily returns, 20 days | **+0.51** | **+0.48** | **Yes** |
| **`volatility_60d_pct`** | Same, 60 days | **+0.62** | **+0.45** | **Yes** |
| **`bollinger_width_pct`** | Bollinger band width | **+0.51** | **+0.48** | **Yes** |
| **`gap_freq_21`** | % of last 21 days moving more than 5% | **+0.63** | **+0.46** | **Yes** |
| `vol_of_vol` | 20-day vol ÷ 60-day vol — is volatility itself rising? | −0.02 | +0.06 | No |

Note `vol_of_vol` failing while the level metrics pass: what mattered was *being*
volatile, not *becoming* more volatile.

---

## Shape and trend quality

The character of the price path rather than its direction.

| Metric | Definition | 2024 | 2025 | Passed |
|---|---|---|---|---|
| `rsi_14` | Relative strength index | −0.25 | +0.46 | No — sign flips |
| `pct_up_days_21` | % of last 21 days that closed higher | +0.08 | +0.14 | No |
| `max_dd_63d_pct` | Worst drawdown in last 63 days | −0.34 | +0.17 | No |
| `return_skew_63` | Skew of the 63-day return distribution | +0.01 | +0.24 | No |
| `trend_r2_63` | R² of a line fitted to log price — trend smoothness | +0.09 | +0.30 | No |

`trend_r2_63` was included to test whether a *smooth* climb differs from a
chaotic one reaching the same place. It did not separate.

---

## Full results table

Sorted by weakest of the two periods.

| Metric | 2024 | 2025 | Consistent | Passed |
|---|---|---|---|---|
| atr_pct | 0.49 | 0.55 | Yes | **Yes** |
| return_5d_pct | −0.48 | 0.53 | No | No |
| volatility_20d_pct | 0.51 | 0.48 | Yes | **Yes** |
| bollinger_width_pct | 0.51 | 0.48 | Yes | **Yes** |
| gap_freq_21 | 0.63 | 0.46 | Yes | **Yes** |
| volatility_60d_pct | 0.62 | 0.45 | Yes | **Yes** |
| pct_above_52w_low | 0.34 | 0.44 | Yes | **Yes** |
| ma50_vs_ma200 | 0.33 | 0.47 | Yes | **Yes** |
| momentum_accel | −0.44 | −0.32 | Yes | **Yes** |
| return_10d_pct | −0.30 | 0.38 | No | No |
| rsi_14 | −0.25 | 0.46 | No | No |
| return_126d_pct | 0.24 | 0.70 | Yes | No |
| return_63d_pct | 0.22 | 0.66 | Yes | No |
| pct_vs_ma50 | −0.21 | 0.55 | No | No |
| obv_slope_21 | −0.29 | −0.19 | Yes | No |
| max_dd_63d_pct | −0.34 | 0.17 | No | No |
| pct_off_52w_high | −0.34 | 0.17 | No | No |
| ad_slope_21 | 0.15 | 0.25 | Yes | No |
| pct_vs_ma200 | 0.14 | 0.66 | Yes | No |
| share_vol_ratio | −0.32 | −0.10 | Yes | No |
| vol_ratio_10_63 | −0.33 | 0.09 | No | No |
| trend_r2_63 | 0.09 | 0.30 | Yes | No |
| return_21d_pct | 0.09 | 0.44 | Yes | No |
| pct_up_days_21 | 0.08 | 0.14 | Yes | No |
| vol_ratio_21_126 | 0.07 | 0.45 | Yes | No |
| up_volume_share | 0.06 | 0.08 | Yes | No |
| vol_ratio_5_21 | −0.39 | −0.03 | Yes | No |
| vol_of_vol | −0.02 | 0.06 | No | No |
| dollar_vol_musd | 0.02 | −0.07 | No | No |
| return_skew_63 | 0.01 | 0.24 | Yes | No |
| close_in_21d_range | 0.01 | 0.31 | Yes | No |

---

## What passed, and what it means

Eight metrics, forming a coherent picture. A stock that went on to rise 10% over
the following three months typically looked like this beforehand:

1. **Volatile** — bouncing around noticeably more than average
2. **In an established uptrend** — 50-day MA above 200-day, well off its lows
3. **Recently cooling** — 10-day momentum below 21-day momentum

That describes a **pullback within an uptrend**: a stock that has been climbing,
is not at its high, and has paused.

### The mirror test

Every passing metric was re-tested against stocks that **fell** 10%. A metric
that identifies "things that move a lot" should separate fallers too. None did:

| Metric | Risers | Fallers | Verdict |
|---|---|---|---|
| atr_pct | +0.52 | −0.02 | Directional |
| volatility_20d_pct | +0.49 | −0.04 | Directional |
| bollinger_width_pct | +0.49 | −0.04 | Directional |
| gap_freq_21 | +0.55 | −0.21 | Directional |
| volatility_60d_pct | +0.53 | −0.06 | Directional |
| pct_above_52w_low | +0.39 | −0.30 | Directional |
| ma50_vs_ma200 | +0.40 | −0.32 | Directional |
| momentum_accel | −0.38 | +0.40 | Directional |

`momentum_accel` flips cleanly — negative for risers, positive for fallers.

This was the expected failure point. Volatility separating risers but *not*
fallers was not the predicted outcome. **However, the 2024 mirror test rests on
only 9 stocks that fell 10%**, so it is largely carried by 2025.

### The permutation control

Labels were shuffled at random and the entire search re-run 500 times:

| | Metrics passing |
|---|---|
| Real labels | **8** |
| Random labels, average | 0.08 |
| Random labels, 95th percentile | 1 |
| Chance of 8+ by luck | **0.0%** |

Not a chance result.

### The finding that matters most

**No volume metric passed.** Eight of thirty-one cleared the bar and none came
from the volume family — the family containing the screener's own core
condition.

This is a fifth independent line of evidence against the original thesis,
approached from the opposite direction: instead of asking whether volume surges
predict returns, it asked whether future winners had volume surges. Same answer.

**And one passing metric contradicts the screener directly.** The live screener
requires **+7% momentum over 10 days**. `momentum_accel` says winners were
*decelerating*. If that holds, the entry condition is pointed the wrong way.

---

## Why eight passes is really three findings

The permutation control assumes 31 independent tests. They are not.

`atr_pct`, `volatility_20d_pct`, `volatility_60d_pct`, `bollinger_width_pct` and
`gap_freq_21` are five ways of measuring the same thing — how much a stock moves.
Like recording height in inches, centimetres and feet: three numbers, one fact.

`pct_above_52w_low` and `ma50_vs_ma200` both describe position within an uptrend
and are strongly related.

So the honest count is **three findings, not eight**:

1. Volatility
2. Established uptrend
3. Momentum deceleration

The permutation p-value overstates the result accordingly. It remains well
outside chance — but three correlated findings are less impressive than eight
independent ones.

---

## Caveats

**The 2024 base rate was extreme.** 121 of 168 tickers — **72%** — rose 10%+.
When nearly three quarters of a universe goes up, "which stocks rose" barely
discriminates. Only 9 fell 10%, making the 2024 mirror test nearly meaningless.

**Two periods is two observations**, both inside the same AI capex buildout.
Not independent samples of market behaviour.

**Only Sep–Nov was tested.** Whether these metrics work in other months is
unknown. A seasonal artefact cannot be ruled out.

**Survivorship bias persists.** Better than the original 60, but companies
delisted during the window still return no data. Four failed to download here:
CSWI, THR, COMM, BITF.

**This is exactly where Study 4 stood** before the universe test: consistent
across periods, mechanistically plausible, statistically clean — and it reversed
completely once the sample changed. Nothing here has yet faced an equivalent
test.

---

## Status

**Hypothesis, not finding.** The correct next step is to state the prediction in
advance and test it against data this analysis has never seen:

> Among live signals, stocks with above-median 20-day volatility, a 50-day MA
> above their 200-day MA, and negative momentum acceleration will beat the
> universe baseline more often than those without.

No changes to the live screener follow from this document. Confirming it
requires out-of-sample data, additional time periods, and a clustered
significance test.

---

*These results describe historical associations. They are not investment advice
and do not predict future returns.*