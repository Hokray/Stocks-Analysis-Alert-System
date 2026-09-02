# Stocks Analysis Alert System

An automated daily stock screener for AI-infrastructure equities, and eight
studies testing whether its logic works.

**It does not.** No metric tested — volume, momentum, volatility, trend position
or any combination — reliably distinguishes stocks that rise from stocks that
do not, in this universe over this period. Two promising findings were
discovered, tested, and withdrawn.

The system runs unattended and is useful as an attention filter. The hypothesis
it was built to test does not hold.

---

## Contents

- [The original hypothesis](#the-original-hypothesis)
- [Phase 1 — Build and validate](#phase-1--build-and-validate)
- [Phase 2 — Metric search](#phase-2--metric-search)
- [All eight studies](#all-eight-studies)
- [What was learned](#what-was-learned)
- [The live system](#the-live-system)
- [Repository layout](#repository-layout)
- [Running it](#running-it)
- [Methods and references](#methods-and-references)
- [Status](#status)

---

## The original hypothesis

Institutions accumulate positions over days rather than all at once. That should
be visible as **sustained, unusually high dollar volume while the price rises** —
money arriving, and buying rather than selling.

Three conditions, all required:

| # | Condition | Threshold |
|---|---|---|
| 1 | Dollar volume: 10-day average ÷ 63-day average | ≥ 1.50× |
| 2 | Price change over 10 trading days | ≥ +7% |
| 3 | TTM cash from operations | > 0 |

Universe: 60 tickers across six categories — Networking and Optics, Memory and
Storage, Servers and Compute, Data Center Cooling, Data Center Power Supply, and
Neo Cloud.

---

## Phase 1 — Build and validate

**[→ research/phase1_validation/](research/phase1_validation/)**

The screener was built, deployed, then tested against three years of history.

Studies 1–3 each appeared to support a **persistence effect** — stocks that kept
qualifying day after day looked like better signals. Three separate analyses
agreed.

Study 4 showed why. All three shared a biased sample: the 60 tickers were chosen
in 2026 *because* they had performed well over the period being tested. On a
universe selected without hindsight, the effect **inverted** — persistent signals
underperformed by 8.48pp with a confidence interval entirely below zero.

**[FINDINGS.md](research/phase1_validation/FINDINGS.md) summarises all four.**

> **The methodological lesson:** consistency across analyses of the same flawed
> sample is not corroboration. It only shows the flaw is stable. Three analyses
> of a biased sample produce three biased results that agree — and that
> agreement feels like mounting evidence while adding none.

---

## Phase 2 — Metric search

**[→ research/phase2_metric_search/](research/phase2_metric_search/)**

Phase 1 established what does not work. Phase 2 searched for what might.

**31 metrics** across volume, momentum, position in range, volatility and trend
quality, tested on a 178-ticker universe with two controls — a mirror test
(does it separate fallers too?) and a permutation test (how many pass by
chance?).

Eight metrics passed two periods. Then the same failure mode as Phase 1: they
had only been tested on one slice.

Extending to six quarters, **zero of thirty-one survived**. The eight separated
winners in autumn and nowhere else, reversing sign entirely in spring.

A follow-up cross-asset study tested the obvious explanation — that volatile
stocks lead when markets rise — and found a correlation of **+0.05**. Not
supported. The simplest reading is that two quarters out of six agreed by
chance, and the analysis happened to begin with those two.

A separate event study explains *why* volume never worked, in two parts. The
screener's 10-day averaging window cannot detect a spike that lasts two days —
around real 10% moves, its own metric peaks at **1.13** against a trigger of
**1.50**. And correcting the window would not help: volume elevation before a
10% **fall** is three times larger than before a 10% rise.

---

## All eight studies

| # | Study | Question | Answer |
|---|---|---|---|
| 1 | [Backtest](research/phase1_validation/BACKTEST_RESULTS.md) | Do signals beat a date-matched baseline? | Marginally; 85% from three tickers |
| 2 | [Significance](research/phase1_validation/SIGNIFICANCE_TESTING_RESULTS.md) | Is that edge distinguishable from luck? | No |
| 3 | [Exit rules](research/phase1_validation/EXIT_RULES.md) | Does any exit beat a fixed hold? | No |
| 4 | [Universe bias](research/phase1_validation/UNIVERSE_TEST_RESULTS.md) | Does persistence survive a neutral universe? | **No — it reverses** |
| 5 | [Metric search](research/phase2_metric_search/METRICS_TESTED_RESULTS.md) | Do future winners look different beforehand? | Eight metrics in two periods |
| 6 | [Volume timing](research/phase2_metric_search/VOLUME_TIMING.md) | Does volume lead or lag the move? | Leads by ~2 days; precedes falls more |
| 7 | [Multi-period](research/phase2_metric_search/MULTI_PERIOD_TEST.md) | Do those eight hold in other quarters? | **No — zero of thirty-one** |
| 8 | [Cross-asset](research/phase2_metric_search/MARKETS_ANALYSIS.md) | Does market regime explain the failures? | No (+0.05) |

---

## What was learned

**About the strategy**

- The three conditions have no demonstrated predictive power
- The apparent edge was ~85% attributable to three tickers
- Persistence was survivorship bias, and reverses under neutral selection
- The eight Phase 2 metrics were a two-quarter coincidence
- No exit rule improves on a fixed hold
- The screener's hit rate tracks the Nasdaq at +0.83 — a busy week means the
  market rose, not that the screener found something
- Volume spikes are brief and news-shaped, not the gradual ramp accumulation
  would produce

**About method**

- A **date-matched baseline** is essential; raw returns in a bull market are
  meaningless
- **Median before mean**, always — the gap between them is diagnostic
- **Clustered resampling** widened the confidence interval 1.3× and changed the
  conclusion
- **Removing top contributors** is a fast fragility test
- **Universe construction** can create an effect that survives every other test
- **A finding tested on one slice has not been tested** — one universe, one
  season, one regime

**Two bugs worth recording**

The Study 4 interpretation logic checked only `if lo_ci > 0` and reported the
project's single statistically clear result — an interval of −13.11 to −4.36 —
as "includes zero." The assumption baked in was that a significant result would
be *positive*.

Writing the test suite found a live bug: `record_run` returned an untruncated
list while `save_run_log` wrote a capped one to disk. It would never have
crashed and never appeared in a log.

---

## The live system

Runs unattended and is unchanged by the research findings.

| Component | Behaviour |
|---|---|
| Schedule | Weekdays 21:15 UTC, after the US close |
| Alerts | HTML email listing matches, with a persistence tag |
| Deduplication | `alerts_history.json`, committed back each run |
| Run log | `run_log.json`, every run recorded including failures |
| Failure alerts | Immediate email with traceback on any exception |
| Heartbeat | Friday summary of runs completed, failures and gaps |
| Tests | 55 unit tests, run in CI before every scheduled run |

Details in **[docs/MONITORING.md](docs/MONITORING.md)**.

**What it does:** narrows the universe to companies where unusual amounts of
money moved recently. A legitimate attention filter.

**What it does not do:** indicate those companies will outperform.

The persistence tag is **descriptive** — it reports how often a stock qualified.
Study 4 showed it should not be read as signal strength.

**Why the evening schedule:** scheduled GitHub workflows are best-effort. One
run arrived 10 hours 37 minutes late. An evening slot leaves ~16 hours of
tolerance before the next session opens, so even a badly delayed run reads a
complete daily bar. A morning slot had under five.

---

## Repository layout

```
├── config.py                    All thresholds
├── screener.py                  Fetching, metrics, filtering
├── notifier.py                  Email and streak tracking
├── heartbeat_monitor.py         Run log, failure alerts, weekly summary
├── test_screener.py             55 unit tests
├── data/
│   ├── tickers.csv              60 — the live screener's universe
│   ├── tickers_control.csv      124 — Study 4, includes deliberate laggards
│   └── tickers_universe.csv     178 — Phase 2
├── docs/MONITORING.md
├── research/
│   ├── phase1_validation/       Studies 1–4
│   └── phase2_metric_search/    Studies 5–8
└── results/                     Generated output (gitignored)
```

---

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
python -m pip install -r requirements.txt

pytest -q                         # 55 tests
python screener.py                # one screening run
```

Research scripts run from the repository root. Phase 1 must run in order —
`backtest.py` produces the signals the others read:

```bash
python research/phase1_validation/backtest.py
python research/phase1_validation/backtest_analysis.py
python research/phase1_validation/significance_testing.py
python research/phase1_validation/exit_rules.py
python research/phase1_validation/universe_test.py

python research/phase2_metric_search/metric_search.py
python research/phase2_metric_search/multi_period_test.py
python research/phase2_metric_search/volume_event_study.py
python research/phase2_metric_search/regime_analysis.py
```

Downloads are cached under `cache/`, so only the first run of each hits the
network.

Email requires `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD` and `EMAIL_TO` — in `.env`
locally, GitHub Secrets for scheduled runs.

---

## Methods and references

**Techniques used**

| Technique | Where | Purpose |
|---|---|---|
| Date-matched baseline | All studies | Strips out sector-wide moves |
| Clustered bootstrap | Studies 2, 4 | Resamples tickers, not signals — they are not independent |
| Permutation test | Studies 5, 7 | Measures how many metrics pass by chance |
| Mirror test | Studies 5, 6 | Separates direction from magnitude |
| Signal deduplication | All backtests | One surge counts once, not ten times |
| Standardised difference | Studies 5, 7 | Compares metrics on different scales |
| Event study | Study 6 | Aligns on event date to measure timing |

**Data**

- Price and volume: `yfinance` (unofficial Yahoo Finance library)
- Cash flow: quarterly statements via the same source
- Cross-asset: SPY, QQQ, GLD, TLT, UUP, HYG, XLU

**Known data limitations**

Companies delisted or acquired during 2023–2026 return no data, so genuine
failures are absent from every universe here — four tickers failed to download
in the later studies, including Chart Industries, acquired by Baker Hughes in
July 2026. No point-in-time fundamentals are available, so the TTM cash-flow
condition was never backtested. A paid dataset with historical index
constituents would be the correct instrument.

**Reading**

- Marcos López de Prado, *Advances in Financial Machine Learning* — on why most
  backtests are wrong, and overlapping-sample problems specifically
- Ernie Chan, *Quantitative Trading* — accessible introduction to backtest
  methodology

---

## Status

**Phase 1: complete.** Four studies, a clear negative conclusion.

**Phase 2: paused.** Eight studies total. The metric search reached the same
dead end from a different direction.

**The live system continues running**, accumulating out-of-sample data — signals
on dates no analysis has seen. That is the only clean test remaining, and it
needs time rather than work.

**Open threads**

- **Transaction costs** — never modelled; would make every result worse
- **Insider buying (SEC Form 4)** — the one remaining idea not derived from
  price and volume, and therefore worth testing where another price
  transformation is not
- **Out-of-sample validation** — revisit once several months of live signals
  have accumulated

---

## Disclaimer

This is a research and screening tool. It identifies where trading volume has
concentrated within a specific sector. It does not constitute investment advice,
does not predict future prices, and — as eight studies establish — has no
demonstrated ability to select stocks that outperform.