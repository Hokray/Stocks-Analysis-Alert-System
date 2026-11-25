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
- [Pitfall 4: the universe is selected on today's market cap](#pitfall-4-the-universe-is-selected-on-todays-market-cap)
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
| a2 | exclude warrants, units, rights, preferreds, funds, trusts | NASDAQ `Security Name` text + symbol structure |
| e | secondary net on non-common stock | yfinance `quoteType` + USD currency |

### Amendment: `quoteType` is not sufficient, so the filter moved earlier

A timed trial on 50 random symbols returned warrants (CAIIW, OABIW, RVMDW,
TLNCW), units (SUMAU), rights (MCAHR), preferreds (WRB$H, HPP$C, DTW, REGCO)
and closed-end funds (PFD, PMO). **yfinance reported `quoteType == "EQUITY"`
for all 48 priced names, including the funds and preferreds, and NASDAQ's own
`ETF` flag caught none of them.**

Ranking a warrant on EBIT/EV is meaningless and closed-end funds would pollute
every decile, so exclusion is driven by the NASDAQ `Security Name` text and
symbol structure (`$` or `.` class markers, and the Nasdaq 5th-letter
convention for W/U/R/P), and it runs **before any price request** rather than
after. `quoteType` is retained only as a secondary net.

The filter is deliberately strict: a false reject costs one name out of
thousands, a false accept puts a warrant into a decile.

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
| **Size** | market capitalisation at the rebalance date, computed as annual balance-sheet `Ordinary Shares Number` lagged 6 months × that date's close | tested as reported, not assumed negative |

Enterprise value is computed as market cap + total debt − cash and cash
equivalents, from the same annual statement as the numerator.

Value and quality are each **two** measures. They are reported separately
rather than blended into a composite, because a composite hides which half
carries any result and invites after-the-fact reweighting.

**Size has no predicted direction.** The small-cap premium is contested and has
been weak-to-absent in US data since the 1980s. Predicting a sign and then
finding it would be unconvincing; this study reports what size does.

**Size uses the historical share count, not today's.** The obvious shortcut —
today's shares outstanding × that date's close — is rejected. This universe
contains names diluting 28–72% a year, so today's share count overstates their
historical market cap several-fold, and because heavy diluters underperform,
that error would load systematically onto the historical large-cap buckets and
**manufacture a size effect out of a dilution effect**. Instead the share count
comes from the annual balance sheet at each rebalance date, lagged 6 months —
the same source, the same lag and the same statement as the dilution factor, so
the two cannot disagree about how many shares a company had.

**The cost of that choice, stated in advance.** Size now depends on
balance-sheet coverage, so it is limited to the periods where statements exist
— roughly the same ~3 rebalances as the fundamental factors, not the ~48
monthly ones price alone would allow. **The realised number of size rebalances
and the per-name balance-sheet coverage are reported as numbers.** If coverage
is materially worse than for the other fundamental factors, that is reported
rather than absorbed by silently dropping names.

**Financials are kept.** Banks and insurers have no EBIT, operating income,
gross profit or capex — verified on JPM, which returns none of the four. So
value and quality are *undefined* for them, not missing. They stay in the
universe and in momentum and size, which are price-only and perfectly well
defined for a bank, and they drop out of value and quality by missing data.
**Coverage per factor is reported as a number, not silently absorbed.**

### Negative and undefined values: the pre-registered rule

A loss-making company and a bank are both "no earnings yield", but for
completely different reasons, and treating them the same would be an error.
The rule turns on **whether a measurement exists**:

| case | treatment | why |
|---|---|---|
| EBIT or FCF is **negative**, EV positive | **kept and ranked at its raw value** — which places it below every profitable name | A negative earnings yield is a real measurement, not missing data. The company genuinely sits at the unattractive end of the factor. |
| Enterprise value **≤ 0** (net cash exceeds market cap) | **excluded** from that factor | The ratio inverts: a profitable company with negative EV produces a large *negative* yield and would be ranked as the worst name in the universe when it is arguably the cheapest. This is an artefact of the arithmetic, not a measurement. |
| Total assets **≤ 0** | **excluded** from quality | Same inversion, same reason. |
| Line item **absent** from the statement (financials, and any filer that omits it) | **excluded** from that factor | Nothing was measured. |
| Statement **missing entirely** for that period | **excluded** from that factor at that rebalance | Nothing was measured. |

**Primary treatment: negatives go to the bottom, by raw-value ranking.** Where
the denominator is positive the ratio is monotone in the numerator, so ranking
the raw value sorts negatives below all positives automatically. No separate
bucket and no special-casing is required — which also means no hidden choice
about *how far* below they should sit.

**Why bottom-bucket and not exclusion as primary.** Excluding loss-makers
would delete the distressed end of the distribution — and
[Pitfall 1](#pitfall-1-survivorship-bias) already deletes part of that same end
by survivorship. Stacking a second selection on top of the first would
compound a bias whose direction is already known, and would leave the value
factor measured on profitable survivors only, which is close to measuring
nothing. It would also cut hardest in Healthcare, the largest sector here at
461 names and heavily pre-revenue.

**Robustness check, reported alongside with no criterion attached:** re-rank
value and quality into deciles among **positive-metric names only** (EBIT > 0
and FCF > 0 respectively), and report whether the top-minus-bottom spread moves
materially. If the result depends on where the loss-makers were put, that is
the finding and it gets said.

### Expected coverage, as counts

Stated in advance so the real per-decile sample size is visible before any
analysis runs. Basis: 2,477 names in the universe; 460 Financial Services plus
97 Real Estate as the sectors most likely to lack the needed line items; and
the timed trial's finding that **18 of 24** sampled names (75%) had ≥4 annual
statement periods.

| factor | expected names ranked | expected per decile | binding constraint |
|---|---|---|---|
| Momentum | ~2,477 | ~248 | none — every name passed the 252-session floor |
| Size | ~1,850 | ~185 | balance-sheet share count availability (~75%) |
| Dilution | ~1,850 | ~185 | needs 3 years of share counts, so likely lower in practice |
| Value | ~1,500 | ~150 | ~75% statement coverage on the ~2,017 non-financials |
| Quality | ~1,500 | ~150 | same, minus names with no gross profit line |

These are **expectations, not commitments** — the realised counts are computed
and reported per factor *and per rebalance date*, because coverage falls off in
the earliest years where statements are thinnest. The
[30-names-per-decile floor](#minimum-sample-sizes) is checked against the
realised count at each date, not against these estimates. A factor-date below
the floor is reported as underpowered, not dropped.

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

**Rebalance frequency.** Momentum rebalances **monthly** from 5 years of price
history. Value, quality, dilution **and size** rebalance **once per fiscal year
per ticker**, lagged as described in Pitfall 2 — size joins them because its
share count now comes from the balance sheet.

**Liquidity is a stored field, not only a filter.** Median daily dollar volume
is recorded for every name in the final universe. The funnel's floor is
deliberately permissive — $100k/day, enough to remove names that barely trade —
because the real liquidity question is answered here instead: **every factor
result is re-run with the bottom liquidity quintile excluded, and whether any
decile spread moves materially is reported.** A strict floor in the funnel would
pre-empt that check by discarding the very names it is meant to test. If the
results depend on the least liquid names, that needs saying rather than hiding
behind a threshold chosen in advance.

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
| **Confirmatory** | momentum | price-only, fully backtestable, no fundamental data involved, ~48 monthly rebalances available from 5 years of history | a result here can be believed to the extent the biases below allow |
| **Exploratory** | value, quality, dilution, **size** | yfinance returns 4–5 annual statement periods; with the lag below that is **~3 rebalances**. Size is additionally compromised by selection — see [Pitfall 4](#pitfall-4-the-universe-is-selected-on-todays-market-cap) | a result here is a curiosity, not evidence |

**Three rebalances cannot support a conclusion.** This is stated now, before any
number exists, so that a striking exploratory spread cannot later be presented
as a finding. Dilution is thinner still: a 3-year share change from 4–5 annual
periods yields one or two non-overlapping observations per ticker.

### Amendment: size demoted from confirmatory to exploratory

Size was pre-registered as confirmatory on the grounds that it is price-only
and therefore carries no look-ahead. **That reasoning was wrong, and the error
is structural rather than a matter of how market cap is reconstructed.**

The universe is selected on market cap *as it is today*. Ranking that universe
on *historical* size then links past size to future return by construction, and
no reconstruction method repairs it — the full mechanism is set out in
[Pitfall 4](#pitfall-4-the-universe-is-selected-on-todays-market-cap). Size is
therefore ineligible to pass, and any spread it shows is reported as a
selection artefact rather than as evidence about the size premium.

**The clean fix exists and was not taken.** A universe selected on *liquidity
only*, with no market-cap bound at any point in the funnel, would break the
link: membership would no longer depend on the variable being ranked. That
would require rebuilding the universe and rerunning the 43-minute funnel, and
the decision was made not to rebuild. This is recorded as a deliberate choice,
not an oversight, so that the limitation cannot later be described as
unforeseen.

**Momentum is unaffected in direction, and is biased conservatively.** The same
$10bn ceiling removes the universe's biggest winners — a company that
compounded from $500m to $40bn over the window is excluded *because* it won.
Momentum ranks on past return, so those names would have populated the top
decile. Their absence **understates** any momentum premium. That is the
opposite direction from the size problem: it makes a positive momentum result
*more* credible, not less, and makes a null correspondingly harder to
interpret.

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

**Only momentum can pass.** Value, quality, dilution and size are exploratory
and are **ineligible** regardless of what their spreads look like. No criterion
may be attached to them after the fact, and doing so would be a second shot at a
positive on the same data. With one confirmatory factor there is also only one
confirmatory test, which removes the multiple-comparisons problem that two would
have carried.

---

## Minimum sample sizes

- **30 names per decile** at each rebalance date, so ~300 ranked names minimum.
- **12 rebalance dates** for a confirmatory test.

Both floors are fixed now and are **not** moved after the counts are seen. A
factor below either floor is reported as **underpowered, not dropped silently**.
The fundamental factors — value, quality, dilution and now size — will have ~3
rebalance dates and so fail the second floor by construction, which is why they
are labelled exploratory in advance rather than after the fact. Size fails on
power *and* on confounding; either alone would disqualify it.

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
reported. So momentum has a *chance* of a powered result; it is not guaranteed
one. Size, now exploratory and annual, sits in the n = 3 column with the
fundamental factors and cannot produce an interpretable null either.

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

The scope carries a *second*, distinct problem — companies that are still
listed but crossed the band's boundaries — which is set out separately in
[Pitfall 4](#pitfall-4-the-universe-is-selected-on-todays-market-cap).

---

## Pitfall 2: look-ahead bias in fundamentals

**Direction: unlagged fundamentals would manufacture a result that does not
exist.**

yfinance returns financial statements **as they are now**, not as reported at
the time. Ranking 2023 stocks on figures that only became public in 2026 lets
the ranking use information no investor had, and that alone can produce a
convincing-looking premium out of nothing.

Mitigation, fixed in advance:

- **Momentum is price-only.** No fundamental data enters it, so it carries no
  look-ahead at all. This is why it is the confirmatory test.
- **Size is no longer price-only.** Its share count comes from the annual
  balance sheet, so it is lagged with the fundamental factors and carries the
  same look-ahead exposure they do. It is exploratory for a separate and
  stronger reason — see Pitfall 4.
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

## Pitfall 4: the universe is selected on today's market cap

**Direction: it manufactures a size effect out of nothing. This is not a bias
that distorts a real effect — it creates an apparent one where none need
exist.**

The funnel applies the $100m–$10bn band to market cap **as measured on the day
the universe was built**. Membership is therefore conditional on where a
company ended up, and that conditioning is not neutral with respect to the
variable size ranks on:

- A company worth $400m at the start of the window and $40bn today is
  **excluded** — it grew out of the band. Small-and-rose is removed.
- A company worth $25bn at the start and $3bn today is **included** — it fell
  into the band. Large-and-fell is retained.

Now rank the surviving universe on historical size. The historically-small
bucket has had its winners deleted, and the historically-large bucket has been
stocked with names that were only large *because they were about to fall*. The
ranking has been linked to the future return by the selection step itself.
**A size spread would appear in this data even if the true size premium were
exactly zero**, and its sign is predictable in advance from the selection
alone: it will favour the historically-small bucket's survivors being weak and
the historically-large bucket being weak too, in proportions no analysis here
can separate.

**No reconstruction method fixes this.** Getting the historical market cap
exactly right — point-in-time shares, point-in-time price, audited — would
still leave the universe conditioned on the endpoint. The error is in which
companies are present, not in what number is attached to them.

**What would fix it, and why it was not done.** A universe selected on
**liquidity only**, with no market-cap bound at any stage, breaks the link:
membership would then depend on trading activity rather than on the ranked
variable. That means rebuilding the universe from stage (a) and rerunning the
funnel. **The decision was to keep the existing universe and demote size to
exploratory instead.** Recorded here as a choice made knowingly, before any
factor was computed.

**Consequence.** Size is exploratory, ineligible to pass, and any spread it
produces is reported as a selection artefact. This is separate from and
additional to [Pitfall 1](#pitfall-1-survivorship-bias), which concerns
companies that left the market entirely; Pitfall 4 concerns companies that are
still listed but crossed a boundary this study drew.

**The same selection touches momentum, in the opposite direction.** The $10bn
ceiling removes the window's largest compounders, which are exactly the names
momentum's top decile would have held. Momentum is therefore **understated**,
not inflated — a conservative bias, which strengthens a positive result and
weakens the interpretation of a null.

---

## Decisions recorded in advance

| decision | choice | why |
|---|---|---|
| universe source | NASDAQ Trader | no contact header required; SEC 403s without one, and no personal contact is transmitted |
| scope | market cap $100m–$10bn, mega caps excluded | floor avoids microstructure noise; ceiling stops ~5 names dominating the top size decile |
| financials | kept, value/quality go NaN | undefined, not missing; keeps the confirmatory sample large; coverage reported |
| negative metric values | **kept, ranked at raw value → bottom of the distribution** | a negative earnings yield is a measurement, not a gap; excluding loss-makers would compound the survivorship bias already deleting that same end |
| undefined metric values | **excluded** from that factor only (EV ≤ 0, assets ≤ 0, absent line item, missing statement) | the ratio inverts or was never measured; keeping them would rank a cash-rich profitable company as the worst name in the universe |
| negative/undefined robustness | re-rank among positive-metric names only, no criterion attached | if the result depends on where loss-makers sat, that is the finding |
| bootstrap unit | rebalance date | within-date dependence dominates in a cross-sectional study |
| size status | **exploratory, not confirmatory** | the universe is selected on today's market cap, so ranking on historical size links past size to future return by construction — Pitfall 4 |
| size measurement | balance-sheet `Ordinary Shares Number`, lagged 6 months, × that date's close | today's share count overstates historical cap several-fold for heavy diluters and would manufacture a size effect from a dilution effect; same source and lag as dilution so the two cannot disagree |
| liquidity-only universe | **considered and declined** | it is the clean fix for Pitfall 4, but requires rebuilding the universe and rerunning the funnel; declined knowingly, recorded so the limitation is not later called unforeseen |
| confirmatory horizon | 12 months | the horizon factor premia are quoted at |
| pass threshold | +3.0 pp spread | inside the published 2–5% range |
| security type | name/symbol filter before pricing | `quoteType` returned EQUITY for closed-end funds and preferreds in the trial |
| liquidity | permissive $100k floor, value stored, bottom-quintile robustness check | moves the choice out of a hidden threshold and into a reported result |
| request pacing | adaptive 0.5s–4.0s, escalate on >3 rate errors per 100, relax after 200 clean | a two-hour run that quietly throttled itself should say so in its summary |
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
- **Any claim about the size premium, in either direction.** The universe is
  selected on today's market cap, which links past size to future return by
  construction (Pitfall 4). A size spread here is a selection artefact and
  would appear even if the true premium were zero. This is a stronger
  disclaimer than the one above: value, quality and dilution are merely
  underpowered, whereas size is **confounded**, and more data at this design
  would not help.
- **Generalisation beyond this period.** One market regime, measured on
  survivors.
- **A live trading decision of any kind.** Nothing here is a recommendation, and
  no change to the screener or to any live system follows from it.
