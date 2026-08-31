# Phase 1 — Build and Validate

The screener was built, deployed, and then tested against three years of
historical data. This directory contains the four validation studies and the
scripts that produced them.

**Read [FINDINGS.md](FINDINGS.md) first.** It summarises all four.

---

## The studies, in order

| # | Study | Script | Question | Answer |
|---|---|---|---|---|
| 1 | [Backtest](BACKTEST_RESULTS.md) | `backtest.py`, `backtest_analysis.py` | Do signals beat a date-matched baseline? | Marginally; 85% from 3 tickers |
| 2 | [Significance](SIGNIFICANCE_TESTING.md) | `significance_testing.py` | Is that edge distinguishable from luck? | No |
| 3 | [Exit rules](EXIT_RULES.md) | `exit_rules.py` | Does any exit beat a fixed hold? | No |
| 4 | [Universe bias](UNIVERSE_TEST.md) | `universe_test.py` | Does persistence survive a neutral universe? | **No — it reverses** |

They must be read in order. Studies 1–3 build toward a conclusion that Study 4
overturns, and that sequence is the substance of the work.

---

## Why the earlier documents were not rewritten

Studies 1–3 report a "persistence" effect that Study 4 disproves. Those
documents carry a note pointing forward, but their conclusions are left as
originally written.

Editing them to look prescient would remove the most useful thing here: a record
of a plausible finding being believed, tested, and withdrawn. Three analyses
agreed with each other because they shared a biased sample — that only became
visible by changing the sample, and the sequence is what makes the lesson
legible.

---

## Running them

From the repository root, in order:

```bash
python research/phase1_validation/backtest.py            # generates signals
python research/phase1_validation/backtest_analysis.py   # size + persistence
python research/phase1_validation/significance_testing.py
python research/phase1_validation/exit_rules.py
python research/phase1_validation/universe_test.py
```

`backtest.py` must run first — the others read its output. Downloads are cached
under `cache/`, so only the first run hits the network.

Output lands in `results/phase1/`.

---

## Method notes

**Date-matched baseline.** Every signal is measured against the average return
of the whole universe over the same window. Raw returns during a rising market
say nothing.

**No lookahead.** Metrics at any date use only data up to that date. A unit test
(`test_no_lookahead_in_the_calculation`) enforces this; if it fails, every
result here is void.

**Signal deduplication.** Signals within 10 trading days of a prior one for the
same ticker collapse into a single event, so one two-week surge is not counted
ten times.

**Clustered resampling.** Bootstrap intervals resample *tickers*, not individual
signals. TSSI contributed 24 signals from one stock in one period — not 24
independent observations. This widened the confidence interval by 1.3× and
changed the conclusion.

---

## Data

| File | Contents |
|---|---|
| `data/tickers.csv` | The 60 hand-picked tickers the live screener uses |
| `data/tickers_control.csv` | 124 tickers for Study 4, including deliberate laggards |