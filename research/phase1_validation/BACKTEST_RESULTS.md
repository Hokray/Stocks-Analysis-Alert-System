# Backtest Results

Validation of the screener's design assumptions against 3 years of historical
data (2023–2026) across the 60-ticker universe.

**Summary in one line:** the base signal does not reliably beat the sector
baseline; the persistence layer does improve it measurably, and that is the one
finding with real support behind it.

---

## Contents

- [Method](#method)
- [Result 1: the base signal does not beat the baseline](#result-1-the-base-signal-does-not-beat-the-baseline)
- [Result 2: three tickers account for 85% of the edge](#result-2-three-tickers-account-for-85-of-the-edge)
- [Result 3: persistence works](#result-3-persistence-works)
- [Result 4: the apparent small-cap edge is not real](#result-4-the-apparent-small-cap-edge-is-not-real)
- [Result 5: category breakdown](#result-5-category-breakdown)
- [What this changes](#what-this-changes)
- [Limitations](#limitations)
- [Reproducing this](#reproducing-this)

---

## Method

Each historical date was evaluated using **only data available up to that
date** — no lookahead. Where the two technical conditions were met, forward
returns were measured at 5, 10, 20 and 30 trading days.

The key comparison is against a **date-matched baseline**: for every signal
date, the average forward return across all 60 tickers in the universe over the
same window.

This matters. A signal returning +8% means nothing if the whole sector returned
+10% — that would make the screener worse than picking at random from the same
list. Matching dates strips out sector-wide moves and isolates the question the
screener actually needs to answer: **did it pick the right names?**

Signals within 10 trading days of a prior signal for the same ticker were
collapsed into one event, so a two-week surge counts once rather than ten times.

**The TTM cash-flow condition was not tested.** yfinance does not provide
historical quarterly statements far enough back, so these results reflect the
two technical conditions only.

`20 days` is used as the reference horizon throughout.

---

## Result 1: the base signal does not beat the baseline

| Horizon | Signals | Mean return | Median return | Baseline | Excess | Hit rate | **Beat baseline** |
|---|---|---|---|---|---|---|---|
| 5d | 495 | 1.89% | 0.36% | 1.14% | +0.75pp | 51.7% | **46.1%** |
| 10d | 495 | 4.58% | 2.59% | 2.72% | +1.86pp | 57.8% | **47.5%** |
| 20d | 493 | 8.03% | 3.18% | 5.49% | +2.54pp | 58.4% | **45.4%** |
| 30d | 493 | 10.96% | 4.74% | 7.61% | +3.35pp | 57.6% | **46.0%** |

Excess return is positive at every horizon, which looks encouraging. It is not.

**`beat_baseline` is under 50% at every horizon.** The majority of signals
underperformed simply buying the average stock in the universe.

The mean is positive only because of the distribution's shape. At 20 days:

- Mean return: **8.03%**
- Median return: **3.18%**
- Baseline mean: **5.49%**
- Best single signal: **+200.4%**
- Worst single signal: **−58.4%**

The **median signal (3.18%) underperformed the average stock (5.49%)**. The gap
between mean and median is the whole story — a small number of very large
winners pull the average above a baseline that most individual signals fell
short of.

**Plain reading:** buying every alert over three years would have produced
roughly the same result as buying random names from the same list.

---

## Result 2: three tickers account for 85% of the edge

Total contribution to cumulative excess return, by ticker:

| Ticker | Total excess (pp) |
|---|---|
| TSSI | 414.1 |
| BE | 351.0 |
| SNDK | 317.4 |
| ALAB | 224.1 |
| BTDR | 222.5 |
| IREN | 121.1 |
| PENG | 119.7 |
| SMCI | 94.1 |
| HUT | 64.2 |
| CIFR | 59.4 |

Removing the top three:

| | Signals | Mean excess | Beat baseline |
|---|---|---|---|
| All signals | 493 | **+2.54pp** | 45.4% |
| Excluding TSSI, BE, SNDK | 441 | **+0.39pp** | 43.8% |

**Three tickers out of sixty carry roughly 85% of the measured edge.** Without
them the strategy is flat.

Those three were among the largest movers of the entire AI cycle — TSSI ran from
roughly $0.28 to $28, BE from ~$10 to ~$300, SNDK from ~$44 to ~$1,562. The
screener did catch them, which is a genuine point in its favour. But *"the
strategy works"* and *"the strategy caught three of the biggest movers of the
cycle"* are different claims, and only the second is supported.

---

## Result 3: persistence works

This is the finding with real support.

Signals were bucketed by how many of the previous 14 trading days also met both
conditions — reconstructing what the live screener's streak counter would have
shown at the time.

| Persistence | Signals | Mean return | Median return | Mean excess | **Beat baseline** |
|---|---|---|---|---|---|
| Brief (1–2 days) | 306 | 7.93% | 2.81% | +1.83pp | **43.1%** |
| Building (3–5 days) | 27 | 0.44% | −4.99% | −1.22pp | 44.4% |
| Persistent (6–9 days) | 37 | 6.21% | 3.33% | +3.04pp | 45.9% |
| **Very persistent (10+ days)** | **123** | **10.48%** | **5.44%** | **+4.99pp** | **51.2%** |

Ignore the "building" row — 27 signals is too few to read anything into.

The comparison that matters is between the two large buckets:

- **Brief (306 signals):** +1.83pp excess, 43.1% beat rate
- **Very persistent (123 signals):** +4.99pp excess, **51.2% beat rate**

The very-persistent group is the **only segment anywhere in this analysis that
crosses a 50% beat rate**, and it does so on a sample of 123 signals.

Identical underlying conditions. The only difference is whether the stock kept
qualifying day after day.

**This validates the core design intuition behind the project** — that a name
appearing repeatedly means more than one that flashes once. It was built on a
hunch and the data supports it.

---

## Result 4: the apparent small-cap edge is not real

| Size at signal | Signals | Mean excess | **Median excess** | Beat baseline |
|---|---|---|---|---|
| Under $2B | 70 | **+11.67pp** | **−1.04pp** | 48.6% |
| $2B – $10B | 134 | +0.57pp | −2.28pp | 40.3% |
| $10B – $50B | 168 | +2.84pp | −0.93pp | 47.6% |
| Over $50B | 121 | −0.96pp | −1.27pp | 46.3% |

The under-$2B mean of +11.67pp looks like a strong edge. It is not.

**The median is −1.04pp.** The typical small-cap signal *underperformed*. And
the beat rate of 48.6% is barely distinguishable from the other buckets.

Mean far above median plus a sub-50% beat rate is the signature of a small
number of extreme winners, not a repeatable edge. This is a lottery-ticket
distribution, not a strategy.

**Design consequence:** `MIN_MARKET_CAP` stays at `0` — but *not* because small
caps are better. The evidence for either setting is weak, and enabling the
filter would remove the outlier upside without a clear justification for doing
so.

---

## Result 5: category breakdown

| Category | Signals | Mean 20d | Excess 20d | Hit rate |
|---|---|---|---|---|
| Servers and Compute | 87 | 11.15% | +6.01pp | 63.2% |
| Neo Cloud | 122 | 9.40% | +3.34pp | 52.5% |
| Data Center Power Supply | 49 | 8.88% | +2.27pp | 49.0% |
| Networking and Optics | 99 | 7.77% | +1.93pp | 67.7% |
| Memory and Storage | 97 | 6.30% | +1.17pp | 56.7% |
| Data Center Cooling | 44 | 1.42% | **−1.93pp** | 52.3% |

Note: `hit_rate` here is the share of signals with a *positive* return, not the
share that beat baseline. Networking's 67.7% hit rate alongside only +1.93pp
excess reflects many small gains during periods when everything was rising.

**Servers and Compute appears strongest — but this is largely one ticker.**
TSSI alone accounts for 24 of that category's 87 signals, and TSSI is the single
largest contributor in the entire dataset. Excluding it, the category advantage
largely disappears. This is not a Dell-and-HPE story.

**Data Center Cooling is the only negative category.** Only 44 signals, so treat
lightly, but there is a plausible mechanism: cooling names are industrials with
lumpy, slow-moving order cycles, where a two-week volume surge more often
reflects an earnings reaction that mean-reverts than sustained accumulation.

---

## What this changes

**Keep:** the system, the universe, the three conditions, and the persistence
tracking.

**Change how alerts are read.** A first alert carries close to no predictive
edge. A signal that has qualified 10+ days out of the last 14 is the one with
evidence behind it. The email already shows this tag — what changes is the
response to each:

- **First alert** → note it, watch whether it recurs
- **Very persistent** → this is the actual signal

**Do not enable `MIN_MARKET_CAP`.** See Result 4.

**Consider dropping Data Center Cooling from alert logic** while keeping it in
the universe for monitoring. Sample is small, so this is a candidate, not a
conclusion.

**What this tool is:** a filter that narrows 60 stocks to a handful worth
researching, where the ones that keep reappearing are meaningfully better than
the ones that flash once.

**What it is not:** a buy signal.

---

## Limitations

**Survivorship bias.** The universe was chosen in 2026, partly because these
companies matter *now*. Backtesting them over 2023–2026 flatters any strategy —
and the results were still weak, which makes them worse than they appear, not
better.

**The persistence result was found by slicing after seeing the data**, not
predicted in advance. That is how spurious patterns get discovered. The trend is
monotonic across both large buckets and the sample is reasonable, which is
reassuring — but this is one test, on one sector, during one unusual market
period. Proper confirmation requires **out-of-sample validation**: letting the
live system run and checking whether the pattern holds going forward.

**Overlapping signals.** Signals cluster in time around hot periods, so they are
not independent observations. The effective sample size is meaningfully smaller
than 493, and no significance test has been run.

**No transaction costs.** Spreads, slippage and taxes are ignored.

**Approximate historical market caps.** Result 4 estimates size as signal-date
price × *current* share count. Several universe members diluted heavily
(IREN, WULF, BTDR), so historical caps are overstated. Adequate for separating
microcap from megacap, which is all that was tested.

**Cash-flow condition untested.** See [Method](#method).

**One regime only.** 2023–2026 was an unusual period dominated by a single
thematic buildout. Nothing here generalises to other sectors or market
conditions.

---

## Reproducing this

```bash
python backtest.py            # downloads history, generates signals
python backtest_analysis.py   # segments by size and persistence
```

Outputs land in `backtest_results/`:

| File | Contents |
|---|---|
| `signals.csv` | Every historical signal with forward and excess returns |
| `signals_enriched.csv` | Same, plus size and persistence buckets |
| `summary.csv` | Headline table by horizon |
| `threshold_sweep.csv` | Performance across threshold combinations |
| `by_category.csv` | Category breakdown |
| `by_size.csv` | Market cap breakdown |
| `by_persistence.csv` | Persistence breakdown |
| `size_x_persistence.csv` | Both dimensions crossed |

---

*These results describe historical behaviour of a screening rule. They are not
investment advice and do not predict future returns.*