# Factor Study — Design and Pre-registration

A separate research line from the screener studies (phases 1–4), which are
paused and untouched. This shares nothing with them except general repo
conventions.

**Goal.** Learn and apply systematic equity factor research over a broad US
universe, and measure whether standard factors — value, quality, dilution,
momentum, size — rank forward returns in this market.

**What the output is.** A research finding plus a ranked decile table.

**What the output is not.** This is **not a recommendation engine**, not a buy
list, and not a set of top picks. It must never describe itself as one. The unit
of analysis is the decile, never the individual name — see
[Pitfall 3](#pitfall-3-small-effect-large-noise).

Everything below is fixed **before** any factor is computed. Nothing here may be
revised after seeing results.

---

## Contents

- [Universe](#universe)
- [Factor definitions](#factor-definitions)
- [Method](#method)
- [Confirmatory versus exploratory](#confirmatory-versus-exploratory)
- [The pre-registered pass criterion](#the-pre-registered-pass-criterion)
- [Minimum sample sizes](#minimum-sample-sizes)
- [Minimum detectable effect](#minimum-detectable-effect)
- [The three outcomes the write-up may report](#the-three-outcomes-the-write-up-may-report)
- [Pitfall 1: survivorship bias](#pitfall-1-survivorship-bias)
- [Pitfall 2: look-ahead bias in fundamentals](#pitfall-2-look-ahead-bias-in-fundamentals)
- [Pitfall 3: small effect, large noise](#pitfall-3-small-effect-large-noise)
- [Decisions recorded in advance](#decisions-recorded-in-advance)
- [What this study cannot support](#what-this-study-cannot-support)

---

## Universe

Built by a staged funnel, each stage cached per ticker and resumable, because a
crash at ticker 4,000 must not lose the first 3,999.

| stage | action | source |
|---|---|---|
| a | full US symbol list | NASDAQ Trader `nasdaqtraded.txt` + `otherlisted.txt` |
| b | batch price download; drop anything without recent trading | yfinance bulk |
| c | liquidity floor on median daily dollar volume | computed from (b) |
| d | market cap for survivors only, then apply the scope band below | yfinance |
| e | exclude ETFs, funds, trusts, non-common stock | NASDAQ `ETF` flag + yfinance `quoteType` |

### Pre-registered scope: $100m to $10bn, mega caps excluded

The study universe is companies with a market capitalisation of **at least
$100 million and at most $10 billion**. Anything above $10bn is excluded, so
mega caps are out by construction.

Both bounds are fixed now, before any factor is computed, and are not revised
after seeing results.

**Why a floor at $100m.** Below it, prices are dominated by microstructure —
wide spreads, thin books, single trades moving the quote. A factor spread
measured there is not reachable by anyone and is as likely to reflect stale
quotes as anything economic.

**Why a ceiling at $10bn.** Mega caps are a handful of names that would
otherwise dominate the top size decile and make the size factor a test of
roughly five companies. Excluding them keeps the cross-section wide enough for
decile ranking to mean something.

**What this costs, stated in advance.** It makes this a small- and mid-cap
study, and **it is the band where survivorship bias bites hardest** — delisting
and bankruptcy rates are far higher at $100m than at $10bn. So the bias
described in [Pitfall 1](#pitfall-1-survivorship-bias) is *worse* in this
universe than it would be in a large-cap one, not milder. It also means no
result here transfers to large caps, where most published factor evidence was
measured.

**Why NASDAQ Trader and not SEC.** The SEC file returns **403** without a
contact address in the User-Agent, and its fair-access policy expects a real
one. The NASDAQ Trader files need no contact header, carry `ETF` and
`Test Issue` flags that do part of stage (e) before a single price request, and
cover ~10,600 non-ETF symbols across the two files. No personal contact
information is transmitted by any script in this study.

**Price history: 5 years, daily, adjusted.** That is what sets how many
momentum rebalances exist, which is the binding constraint on the only factors
that can be powered here.

---

## Factor definitions

Fixed now. Not revised after seeing results.

| factor | definition | direction |
|---|---|---|
| **Value** | earnings yield (EBIT / enterprise value) **and** free-cash-flow yield (FCF / enterprise value) | higher is better |
| **Quality** | gross profitability (gross profit / total assets) **and** positive free cash flow | higher is better |
| **Dilution** | 3-year change in shares outstanding | **lower** is better |
| **Momentum** | 12-month return skipping the most recent month (standard 12-1) | higher is better |
| **Size** | market capitalisation | tested as reported, not assumed negative |

Enterprise value is computed as market cap + total debt − cash and cash
equivalents, from the same annual statement as the numerator.

Value and quality are each **two** measures. They are reported separately
rather than blended into a composite, because a composite hides which half
carries any result and invites after-the-fact reweighting.

**Size has no predicted direction.** The small-cap premium is contested and has
been weak-to-absent in US data since the 1980s. Predicting a sign and then
finding it would be unconvincing; this study reports what size does.

**Financials are kept.** Banks and insurers have no EBIT, operating income,
gross profit or capex — verified on JPM, which returns none of the four. So
value and quality are *undefined* for them, not missing. They stay in the
universe and in momentum and size, which are price-only and perfectly well
defined for a bank, and they drop out of value and quality by missing data.
**Coverage per factor is reported as a number, not silently absorbed.**

---

## Method

1. **Rank the universe cross-sectionally into deciles** on each factor at each
   rebalance date. Decile 10 is the most attractive end by the direction above;
   decile 1 is the least.
2. **Measure forward returns** at 1, 3, 6 and 12 months from each rebalance
   date, equal-weighted within decile.
3. **Report the top-minus-bottom decile spread** with a bootstrap 95% CI.
4. **Report the information coefficient** — the Spearman rank correlation
   between factor rank and forward return, computed per rebalance date and then
   averaged.

**Ties and boundaries.** Deciles are assigned by rank with ties broken by
average rank, so an exact tie cannot land in two deciles. Where the universe is
not divisible by ten, the remainder goes to the middle deciles, never to the top
or bottom — the extremes are what the headline number compares, so they must not
differ in size.

**The bootstrap resamples rebalance DATES, not tickers.** Each resampled date
brings its entire cross-section along. In a cross-sectional factor study the
dominant dependence is that every name on one date shares the same market move:
one bad quarter moves all ten deciles together. Resampling tickers would treat a
single market-wide quarter as hundreds of independent observations and produce
an interval far too narrow. 10,000 iterations, seed 42.

**Spearman without scipy.** scipy is not installed and no new dependency is
permitted, so `pandas.corr(method="spearman")` raises `ModuleNotFoundError`.
Rank correlation is computed by ranking both inputs and taking the ordinary
correlation, which is the same number; pandas' default ranking averages ties,
which is the tie correction Spearman calls for.

**Rebalance frequency.** Momentum and size rebalance **monthly** from 5 years
of price history. Value, quality and dilution rebalance **once per fiscal year
per ticker**, lagged as described in Pitfall 2.

**Overlapping windows.** Monthly rebalances with a 12-month forward return
overlap by construction, so those observations are not independent. The by-date
bootstrap addresses within-date dependence, not across-date overlap. A
**non-overlapping annual** version of the confirmatory test is therefore
reported alongside as a robustness check, with no criterion attached.

---

## Confirmatory versus exploratory

This split is the single most important thing in this document.

| | factors | why | status |
|---|---|---|---|
| **Confirmatory** | momentum, size | price-only, fully backtestable, no fundamental data involved, ~48 monthly rebalances available from 5 years of history | a result here can be believed to the extent the biases below allow |
| **Exploratory** | value, quality, dilution | yfinance returns 4–5 annual statement periods; with the lag below that is **~3 rebalances** | a result here is a curiosity, not evidence |

**Three rebalances cannot support a conclusion.** This is stated now, before any
number exists, so that a striking exploratory spread cannot later be presented
as a finding. Dilution is thinner still: a 3-year share change from 4–5 annual
periods yields one or two non-overlapping observations per ticker.

---

## The pre-registered pass criterion

A factor **passes** only if all of the following hold at the **12-month**
horizon, which is the confirmatory horizon:

1. The quantity is the **top-minus-bottom decile spread** in forward return.
2. Its **by-date bootstrap 95% CI lower bound is above zero**.
3. The point estimate is **at least +3.0 pp** over the 12-month horizon.
4. The **information coefficient is positive** at the same horizon.
5. The sample meets the minimum sizes below.

Horizons 1, 3 and 6 months are reported as supporting evidence with **no
criterion attached**. A real effect should point the same way at all four.

**Why +3.0 pp.** Published factor premia run roughly 2–5% a year. A threshold
below that range would let ordinary noise qualify as a result; far above it
would reject real effects. 3.0 pp sits inside the published range and is fixed
now so it cannot drift toward whatever the data turns out to show.

**Only momentum and size can pass.** Value, quality and dilution are exploratory
by construction and are **ineligible** regardless of what their spreads look
like. No criterion may be attached to them after the fact, and doing so would be
a second shot at a positive on the same data.

---

## Minimum sample sizes

- **30 names per decile** at each rebalance date, so ~300 ranked names minimum.
- **12 rebalance dates** for a confirmatory test.

Both floors are fixed now and are **not** moved after the counts are seen. A
factor below either floor is reported as **underpowered, not dropped silently**.
The fundamental factors will have ~3 rebalance dates and so fail the second
floor by construction — which is why they are labelled exploratory in advance
rather than after the fact.

---

## Minimum detectable effect

A null is ambiguous between two different worlds: the effect is not there, or
the design cannot see it. The MDE separates them, so the formula and the power
constants are fixed here and only the dispersion comes from the data.

For a mean spread across `n` independent rebalance dates:

```
MDE at 80% power = 2.80 * SD(spread across dates) / sqrt(n)
95% CI half-width = 1.96 * SD(spread across dates) / sqrt(n)
```

`2.80 = 1.96 + 0.84`. The realised numbers are computed at analysis time from
the observed dispersion of per-date spreads; what follows is what the design can
reach at plausible dispersions, recorded before any data exists.

| SD of 12-month spread across dates | n = 3 (fundamentals) | n = 12 | n = 48 (monthly, 5y) |
|---|---|---|---|
| 10 pp | 16.2 pp | 8.1 pp | 4.0 pp |
| 20 pp | 32.3 pp | 16.2 pp | 8.1 pp |
| 30 pp | 48.5 pp | 24.2 pp | 12.1 pp |

**What this says in advance.** At **n = 3** the MDE is 16–49 pp against a 3.0 pp
threshold — five to sixteen times too blunt. **The exploratory factors cannot
produce an interpretable null.** Their result will be uninformative whatever it
is, and that is known now, not discovered later.

Even at n = 48 the MDE clears 3.0 pp only if the across-date SD of the spread is
under about 10 pp. Whether it is cannot be known in advance — it is measured and
reported. So momentum and size have a *chance* of a powered result; they are not
guaranteed one.

The overlapping-window caveat applies: 48 monthly rebalances with 12-month
forward returns are not 48 independent observations, so the effective `n` is
smaller than 48 and the realised MDE correspondingly worse. The non-overlapping
annual check exists for this reason.

---

## The three outcomes the write-up may report

For each confirmatory factor, exactly one of:

1. **Pass** — all five criteria met.
2. **Interpretable null** — criterion not met, and the realised MDE is **below**
   3.0 pp. The design could have seen an effect worth caring about and did not.
3. **Underpowered** — criterion not met, and the realised MDE is **above**
   3.0 pp. The study could not have detected an effect of that size, and must
   say so rather than reporting a null.

---

## Pitfall 1: survivorship bias

**Direction: it inflates measured returns, and it inflates them most in the
cheap and distressed bucket — exactly where a value factor lives.**

The universe is built from companies listed *today*. Everything that went
bankrupt, was delisted or was acquired at a loss is absent. Those names did not
fail at random: they failed disproportionately out of the cheap, high-yield,
distressed end of the distribution. So the bottom-price/top-value decile is
measured using only the members that survived, and its return is biased upward.

The expected effect is to **overstate** any value premium, and to flatter every
factor's absolute return. A measured value spread is an upper bound, not an
estimate.

This is not a correctable flaw. It needs point-in-time constituent data, which
is not available here.

**No forward archive is being collected.** A daily snapshot of factor inputs as
known on each date was specified and then dropped from the plan. That archive
would have been the only survivorship-free and look-ahead-free data this line
could ever have, accumulating from the day it started. Without it this bias has
**no remediation path** — it is stated, its direction named, and lived with. It
does not shrink over time.

Concrete scale, from the repo's own data: **6 of the 178 tickers** in the
screener's live universe no longer return price data — GREE, THR, GTLS, BITF,
CSWI, COMM. That is 3.4% gone in roughly three years from a hand-picked list of
established names. A broad small-cap universe attrits considerably faster.

**The pre-registered scope makes this worse, not better.** The $100m–$10bn band
is precisely where delisting and bankruptcy rates are highest. A large-cap study
would suffer less from this bias; this one suffers more. That is an accepted cost
of the scope, recorded before any result.

---

## Pitfall 2: look-ahead bias in fundamentals

**Direction: unlagged fundamentals would manufacture a result that does not
exist.**

yfinance returns financial statements **as they are now**, not as reported at
the time. Ranking 2023 stocks on figures that only became public in 2026 lets
the ranking use information no investor had, and that alone can produce a
convincing-looking premium out of nothing.

Mitigation, fixed in advance:

- **Momentum and size are price-only.** No fundamental data enters them, so
  they carry no look-ahead at all. This is why they are the confirmatory tests.
- **Value, quality and dilution are lagged at least 6 months from each ticker's
  own fiscal year end**, approximating when the figures were actually public.
- **The lag runs from each ticker's own fiscal year end, not a shared calendar
  date.** Verified necessary: a sample of nine companies had year ends in
  August, September and December. A single global rebalance date would give some
  tickers a 4-month lag and others 15 months.
- Statement depth of 4–5 annual periods leaves **~3 usable rebalances**, which
  is why these factors are exploratory.

A 6-month lag is an approximation, not a guarantee. Annual reports are usually
filed within 60–90 days, so 6 months is conservative for most filers and
occasionally still too short for a late one. Restatements are invisible to this
method entirely: a restated figure appears as though it were the original.

---

## Pitfall 3: small effect, large noise

**Direction: it makes individual names look informative when they are not.**

Factor premia are a few percent a year. Single-name dispersion is tens of
percent — the screener studies measured 20–28 pp standard deviations on
individual 10-session excess returns. The signal is an order of magnitude
smaller than the noise it sits in.

Consequences, binding on every output of this study:

- **The decile is the unit of analysis.** Not the name.
- **No individual ticker is reported as a conclusion**, ranked as a pick, or
  described as attractive. A name's presence in a decile says what its factor
  rank was, not what it will do.
- **No buy list, no top picks, no recommendation section** — in the code
  output, in `FINDINGS.md`, or anywhere else.
- A decile table is the deliverable. A reader who extracts a name from it and
  trades it is doing something this study does not support.

---

## Decisions recorded in advance

| decision | choice | why |
|---|---|---|
| universe source | NASDAQ Trader | no contact header required; SEC 403s without one, and no personal contact is transmitted |
| scope | market cap $100m–$10bn, mega caps excluded | floor avoids microstructure noise; ceiling stops ~5 names dominating the top size decile |
| financials | kept, value/quality go NaN | undefined, not missing; keeps the confirmatory sample large; coverage reported |
| bootstrap unit | rebalance date | within-date dependence dominates in a cross-sectional study |
| confirmatory horizon | 12 months | the horizon factor premia are quoted at |
| pass threshold | +3.0 pp spread | inside the published 2–5% range |
| helper code | copied, not imported | this line shares nothing with phases 1–4, so a later edit there cannot silently change factor results |
| forward archive | not built | dropped from the plan; consequence recorded in Pitfall 1 |

---

## What this study cannot support

- **Any claim about an individual stock.** See Pitfall 3.
- **An unbiased estimate of the value premium.** Survivorship bias runs in a
  known direction and cannot be removed. The measured number is an upper bound.
- **Any conclusion from value, quality or dilution.** ~3 rebalances with an MDE
  five to sixteen times the threshold. These are exploratory, ineligible to
  pass, and cannot produce an interpretable null either.
- **Generalisation beyond this period.** One market regime, measured on
  survivors.
- **A live trading decision of any kind.** Nothing here is a recommendation, and
  no change to the screener or to any live system follows from it.
