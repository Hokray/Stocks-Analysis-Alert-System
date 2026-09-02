# Cross-Asset Market Analysis

Eighth study. Phase 2.

Every previous study looked *within* the sector — which stock beats which. This
looks at the level above: was capital flowing into equities at all during each
quarter, or into gold and bonds instead?

**Two results.** The share of the universe rising 10% tracks the Nasdaq at +0.83
— the screener's hit rate is set mostly by market direction, not by its own
logic. And a proposed explanation for the previous study's failure was tested
and **not supported**.

---

## Contents

- [The question](#the-question)
- [Method](#method)
- [Result 1: quarterly returns by asset class](#result-1-quarterly-returns-by-asset-class)
- [Result 2: rotation is real, but messier than the model assumes](#result-2-rotation-is-real-but-messier-than-the-model-assumes)
- [Result 3: the screener tracks the Nasdaq](#result-3-the-screener-tracks-the-nasdaq)
- [Result 4: a hypothesis that failed](#result-4-a-hypothesis-that-failed)
- [What this is useful for](#what-this-is-useful-for)
- [Limitations](#limitations)

---

## The question

Two motivations.

**A general one.** Capital rotates between asset classes. When money flows into
gold and Treasuries it is often leaving equities, and vice versa. Is that
visible in this period, and does it mark quarters where stocks were favoured?

**A specific one.** The multi-period test found metric separation swinging from
+0.57 to −0.38 across quarters with no stock-specific explanation. The obvious
candidate was market regime: volatile stocks amplify whatever the market does,
so in a rising quarter they lead and in a falling one they lag. That would make
the eight metrics a measure of beta rather than of anything predictive.

Worth testing rather than asserting.

---

## Method

Seven ETFs as asset-class proxies:

| Ticker | Represents | Side |
|---|---|---|
| SPY | S&P 500 | Risk-on |
| QQQ | Nasdaq 100 | Risk-on |
| HYG | High-yield credit | Risk-on |
| GLD | Gold | Risk-off |
| TLT | 20+ year Treasuries | Risk-off |
| UUP | US Dollar | Risk-off |
| XLU | Utilities | Defensive equity |

**Regime score** = mean(SPY, QQQ, HYG) − mean(GLD, TLT, UUP), in percentage
points per quarter. Positive means capital favoured risk over safety.

Deliberately crude. It is a directional summary, not a factor model.

Nine quarters, of which six overlap the periods used in the multi-period test.

---

## Result 1: quarterly returns by asset class

| Period | SPY | QQQ | GLD | TLT | UUP | HYG | XLU | Score | Regime |
|---|---|---|---|---|---|---|---|---|---|
| Mar–May 2024 | 3.15 | 1.28 | 11.62 | −3.60 | 2.25 | 0.98 | 18.80 | −1.62 | mixed |
| Jun–Aug 2024 | 7.14 | 5.27 | 6.48 | 6.03 | −0.88 | 4.11 | 6.98 | +1.63 | mixed |
| Sep–Nov 2024 | 9.48 | 10.53 | 6.64 | −3.23 | 5.40 | 2.74 | 9.60 | +4.65 | risk-on |
| Dec–Feb 24/25 | −1.23 | −1.22 | 8.15 | −0.80 | 2.29 | 1.58 | −1.57 | −3.50 | risk-off |
| Mar–May 2025 | 1.27 | 4.59 | 13.82 | −6.12 | −5.70 | 0.98 | 4.00 | +1.61 | mixed |
| Jun–Aug 2025 | 9.15 | 9.14 | 2.05 | 2.46 | 0.40 | 3.12 | 3.32 | +5.50 | risk-on |
| Sep–Nov 2025 | 7.03 | 9.61 | 19.13 | 6.10 | 2.40 | 1.74 | 8.57 | −3.08 | risk-off |
| Dec–Feb 25/26 | 1.14 | −1.47 | 24.12 | 3.10 | −0.69 | 1.28 | 8.66 | **−8.53** | strong risk-off |
| Mar–May 2026 | 10.51 | 21.57 | −14.87 | −3.56 | 1.21 | 1.05 | −5.57 | **+16.78** | strong risk-on |

---

## Result 2: rotation is real, but messier than the model assumes

Four of nine quarters saw safe havens outperform equities.

**The clearest case of genuine rotation — Mar–May 2026:**

| | Return |
|---|---|
| Nasdaq | **+21.57%** |
| Gold | **−14.87%** |

Money leaving gold, entering equities. Textbook.

**But the model breaks in Sep–Nov 2025:**

| | Return |
|---|---|
| Gold | +19.13% |
| Nasdaq | +9.61% |
| S&P 500 | +7.03% |
| Treasuries | +6.10% |

**Everything rose at once.** Gold rose most, so the score labels the quarter
"risk-off" — but equities did perfectly well.

The rotation model assumes a fixed pot of capital being reallocated. That
assumption fails when the pot grows: liquidity expands, and every asset class
rises together. Sep–Nov 2025 and Dec–Feb 2025/26 both show this.

**Gold also had its own drivers in this period** — central bank accumulation and
currency-debasement concerns — largely independent of equity risk appetite. A
+24% quarter for gold says more about gold than about how investors felt about
stocks. That materially weakens GLD as a risk-off proxy here.

---

## Result 3: the screener tracks the Nasdaq

| Period | QQQ | Universe rising 10%+ | Regime |
|---|---|---|---|
| Mar–May 2024 | +1.28% | **39%** | mixed |
| Jun–Aug 2024 | +5.27% | **37%** | mixed |
| Sep–Nov 2024 | +10.53% | **72%** | risk-on |
| Mar–May 2025 | +4.59% | **44%** | mixed |
| Jun–Aug 2025 | +9.14% | **63%** | risk-on |
| Sep–Nov 2025 | +9.61% | **51%** | risk-off |

**Correlation, QQQ return vs share rising 10%+: +0.83**
**Correlation, regime score vs share rising 10%+: +0.63**

Nasdaq up 10%, roughly 70% of the universe clears 10%. Nasdaq up 1%, roughly
39% does.

**This is not a discovery.** AI-infrastructure names are high-beta Nasdaq
stocks; that they rise together is close to definitional.

**The consequence is real, though.** The screener's hit rate is largely
determined by market direction rather than by stock selection. A month with many
alerts means the sector rose, not that the screener found something. A quiet
month means the opposite.

It also justifies, retroactively, the **date-matched baseline** used in every
earlier study. Without comparing each signal against what the rest of the
universe did on the same day, the screener would have appeared skilful simply
for operating during a bull market.

---

## Result 4: a hypothesis that failed

The main reason for running this study was to test whether market regime
explained the multi-period failure.

**Correlation, regime score vs volatility separation: +0.05.**

No relationship. Two quarters make the point directly:

| Period | Regime | QQQ | Volatility separation |
|---|---|---|---|
| Jun–Aug 2025 | **strongest risk-on** | +9.14% | **−0.10** |
| Mar–May 2025 | mixed | +4.59% | **+0.57** |

If volatility separation were beta-driven, the strong quarter should show the
strong separation. It shows the opposite.

**The beta explanation is not supported.** It was a plausible mechanism for why
the eight metrics worked in autumn, and the data does not back it.

That leaves the multi-period failure without a mechanism — which is fine. The
simplest reading is that two quarters out of six agreed by chance, and the
analysis happened to begin with those two. Coincidence requires no explanation.

Worth recording explicitly: this hypothesis was stated, tested, and rejected.
It would have been easy to assert the beta story in the previous document and
never check it.

---

## What this is useful for

**Not as a signal.** It is market-wide, so it is identical for every stock on a
given day and contributes nothing to choosing between them. Under the
date-matched methodology it cancels out entirely.

**Not as a forecast.** Asset classes reprice simultaneously. Observing risk-off
tells you what has already happened, not what is coming.

**As context, it is genuinely useful.** Knowing the screener's output volume is
driven by the market means alert counts should not be read as a measure of the
screener's performance. A busy week is a rising market.

---

## Limitations

**Nine quarters, six overlapping.** Far too few for statistical claims. With six
points, |r| exceeds 0.6 about 21% of the time on pure noise and 0.7 about 12% of
the time. The +0.83 is only convincing because the mechanism is obvious
independently of the data.

**One regime.** 2024–2026 was a sustained equity bull market with few genuine
risk-off quarters. Nothing here establishes how the screener behaves in a
sustained downturn.

**Gold is a poor risk-off proxy in this period.** See Result 2.

**ETFs are approximations.** SPY is not "equities" and GLD is not "gold" —
they are tradable proxies with their own flows.

---

## Reproducing

```bash
python research/phase2_metric_search/regime_analysis.py
```

Outputs: `results/phase2/regime_analysis.csv`,
`results/phase2/regime_vs_screener.csv`

---

## Conclusion

Capital rotation between asset classes is visible in this period — four of nine
quarters saw safe havens beat equities, and Mar–May 2026 shows a textbook
rotation with the Nasdaq up 21% while gold fell 15%.

But it is not usable as a screening signal. It is market-wide, it is
simultaneous rather than leading, and in this sample gold moved for reasons of
its own.

The durable finding is narrower and more useful: **the screener's hit rate is
mostly a function of the Nasdaq.** That is context for reading its output, and
confirmation that the date-matched baseline was necessary throughout.

And one hypothesis — that market regime explained the multi-period failure —
was tested and rejected.

---

*These results describe historical associations. They are not investment advice
and do not predict future returns.*