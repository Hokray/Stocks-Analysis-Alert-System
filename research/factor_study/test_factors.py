"""
Tests for the factor construction in factors.py.

    pytest research/factor_study/test_factors.py -v

Nothing here touches the network or reads any cache. Every price series,
statement and expected answer is hand-built, so the correct value is known in
advance rather than compared against whatever the code happens to produce.

The tests run the REAL functions -- `build_panel`, `pick_period`,
`assign_deciles`, `per_date_results` -- rather than reimplementing their
arithmetic. A test that recomputes the formula it is checking passes whenever
the formula is wrong in both places.

Five things are pinned deliberately, because each is a place where a silent
error would still produce a plausible-looking number:

  1. The 12-1 momentum skip. A spike in the skipped month must NOT reach
     momentum, and must reach the forward return. An implementation using
     px[i]/px[i-12] passes a casual eyeball test and fails this one.
  2. The 6-month fundamental lag, at the boundary from both sides. A period
     exactly at the cutoff is eligible; one day later is not. This repo has
     already shipped one off-by-one in window arithmetic -- the volume
     overlap bug, which inflated a result up to 4x before it was caught.
  3. Decile boundaries and ties. Tied values must land in ONE decile, and the
     n-not-divisible-by-ten remainder must go to the MIDDLE deciles so that
     D1 and D10 -- the two the headline spread compares -- are equal in size.
  4. The negative-versus-undefined rule from DESIGN.md. A negative EBIT is a
     measurement and must be KEPT at its raw value; a non-positive enterprise
     value is an artefact and must be EXCLUDED. Conflating them would rank a
     cash-rich profitable company as the worst name in the universe.
  5. The factor specification itself -- which factors are confirmatory and
     which carry the sector exclusion. The split is the single most important
     thing in DESIGN.md, so a config edit that quietly promoted a factor to
     confirmatory should fail a test, not reach FINDINGS.md.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import factors as fx


# ===========================================================================
# Fixtures -- hand-built, 40 month-ends from 2020-01-31
# ===========================================================================

N_MONTHS = 40
DATES = pd.date_range("2020-01-31", periods=N_MONTHS, freq="ME")

# build_panel needs 13 months behind and 12 ahead, so rebalance dates are
# index 13..27. Index 20 is 2021-09-30 (not December, so no fundamentals
# interfere); index 23 is 2021-12-31 (a fundamental date).
MOM_I = 20
FUND_I = 23


def make_universe(symbols, sector="Industrials", mdv=5e6):
    return pd.DataFrame({
        "symbol": symbols,
        "sector": [sector] * len(symbols) if isinstance(sector, str) else sector,
        "median_dollar_volume": [mdv] * len(symbols),
    })


def make_closes(per_symbol):
    """per_symbol: {symbol: list of N_MONTHS closes}."""
    return pd.DataFrame(per_symbol, index=DATES)


def make_fundamentals(per_symbol):
    """per_symbol: {symbol: {period_str: {field: value}}}."""
    out = {}
    for symbol, periods in per_symbol.items():
        df = pd.DataFrame(periods).T
        df.index = pd.to_datetime(df.index)
        for field in fx.FIELDS:
            if field not in df.columns:
                df[field] = np.nan
        out[symbol] = df[list(fx.FIELDS)].sort_index()
    return out


FULL_STATEMENT = {
    "ebit": 100.0,
    "gross_profit": 300.0,
    "total_assets": 1000.0,
    "total_debt": 50.0,
    "cash": 20.0,
    "shares": 1000.0,
    "fcf": 80.0,
}


def statement(**overrides):
    rec = dict(FULL_STATEMENT)
    rec.update(overrides)
    return rec


def panel_for(closes_map, fundamentals_map=None, sector="Industrials"):
    symbols = list(closes_map)
    universe = make_universe(symbols, sector=sector)
    closes = make_closes(closes_map)
    funds = make_fundamentals(fundamentals_map or {})
    return fx.build_panel(universe, closes, funds)


def at(panel, date_index, symbol):
    row = panel[(panel["date"] == DATES[date_index])
                & (panel["symbol"] == symbol)]
    assert len(row) == 1, f"expected one row, got {len(row)}"
    return row.iloc[0]


# ===========================================================================
# 1. The 12-1 momentum skip
# ===========================================================================

class TestMomentumSkip:
    """
    momentum at date i = px[i - 1] / px[i - 13] - 1

    Twelve months of return, ending one month BEFORE the ranking date. The
    skipped month is the whole point of the 12-1 convention: it drops the
    short-term reversal that would otherwise contaminate the signal.
    """

    def test_spike_in_the_skipped_month_does_not_reach_momentum(self):
        closes = [100.0] * N_MONTHS
        closes[MOM_I] = 1000.0            # 10x, in the month that is skipped
        panel = panel_for({"AAA": closes})
        assert at(panel, MOM_I, "AAA")["momentum"] == pytest.approx(0.0)

    def test_that_same_spike_does_reach_the_forward_return(self):
        """The forward return is based at the ranking date's own close."""
        closes = [100.0] * N_MONTHS
        closes[MOM_I] = 1000.0
        panel = panel_for({"AAA": closes})
        assert at(panel, MOM_I, "AAA")["fwd_1m"] == pytest.approx(-0.9)

    def test_the_window_spans_twelve_months_not_thirteen(self):
        closes = [100.0] * N_MONTHS
        closes[MOM_I - 13] = 100.0
        closes[MOM_I - 1] = 200.0
        panel = panel_for({"AAA": closes})
        assert at(panel, MOM_I, "AAA")["momentum"] == pytest.approx(1.0)

    def test_the_bar_before_the_window_start_is_excluded(self):
        """px[i - 14] must not influence momentum."""
        base = [100.0] * N_MONTHS
        base[MOM_I - 1] = 200.0
        plain = panel_for({"AAA": list(base)})
        wild = list(base)
        wild[MOM_I - 14] = 1e6
        shifted = panel_for({"AAA": wild})
        assert (at(plain, MOM_I, "AAA")["momentum"]
                == pytest.approx(at(shifted, MOM_I, "AAA")["momentum"]))

    def test_momentum_is_negative_when_the_window_fell(self):
        closes = [100.0] * N_MONTHS
        closes[MOM_I - 13] = 200.0
        closes[MOM_I - 1] = 100.0
        panel = panel_for({"AAA": closes})
        assert at(panel, MOM_I, "AAA")["momentum"] == pytest.approx(-0.5)

    @pytest.mark.parametrize("horizon,months", list(fx.HORIZONS.items()))
    def test_each_forward_horizon_uses_the_right_month(self, horizon, months):
        closes = [100.0] * N_MONTHS
        closes[MOM_I + months] = 150.0
        panel = panel_for({"AAA": closes})
        assert (at(panel, MOM_I, "AAA")[f"fwd_{horizon}"]
                == pytest.approx(0.5))

    def test_no_rebalance_date_lacks_thirteen_months_of_history(self):
        panel = panel_for({"AAA": [100.0] * N_MONTHS})
        assert panel["date"].min() == DATES[fx.MOMENTUM_LOOKBACK]

    def test_no_rebalance_date_lacks_a_full_forward_window(self):
        panel = panel_for({"AAA": [100.0] * N_MONTHS})
        last = panel["date"].max()
        assert last == DATES[N_MONTHS - 1 - max(fx.HORIZONS.values())]


# ===========================================================================
# 2. The 6-month fundamental lag
# ===========================================================================

class TestFundamentalLag:
    """
    The lag runs from each ticker's OWN fiscal year end, not a shared calendar
    date. Year ends in this universe fall in several different months, so a
    single global rebalance would give some tickers a 4-month lag and others
    15 months.
    """

    def frame(self, periods):
        df = pd.DataFrame({p: dict(FULL_STATEMENT) for p in periods}).T
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    def test_picks_the_most_recent_period_old_enough(self):
        df = self.frame(["2020-03-31", "2021-03-31", "2021-09-30"])
        picked = fx.pick_period(df, pd.Timestamp("2021-12-31"))
        assert picked == pd.Timestamp("2021-03-31")

    def test_a_period_exactly_at_the_cutoff_is_eligible(self):
        """as_of minus 6 months is 2021-06-30, which must be INCLUDED."""
        df = self.frame(["2021-06-30"])
        assert fx.pick_period(df, pd.Timestamp("2021-12-31")) is not None

    def test_a_period_one_day_past_the_cutoff_is_not_eligible(self):
        df = self.frame(["2021-07-01"])
        assert fx.pick_period(df, pd.Timestamp("2021-12-31")) is None

    def test_returns_none_when_every_period_is_too_recent(self):
        df = self.frame(["2021-09-30", "2021-12-31"])
        assert fx.pick_period(df, pd.Timestamp("2021-12-31")) is None

    def test_a_non_december_year_end_gets_its_own_lag(self):
        """An August filer uses its August statement, not a December one."""
        df = self.frame(["2021-08-31", "2020-08-31"])
        assert (fx.pick_period(df, pd.Timestamp("2022-06-30"))
                == pd.Timestamp("2021-08-31"))

    def test_fundamentals_are_absent_on_non_fundamental_dates(self):
        funds = {"AAA": {"2021-03-31": statement()}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isnan(at(panel, MOM_I, "AAA")["ebit_ev"])

    def test_fundamentals_are_present_on_a_fundamental_date(self):
        funds = {"AAA": {"2021-03-31": statement()}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isfinite(at(panel, FUND_I, "AAA")["ebit_ev"])

    def test_a_too_recent_statement_yields_no_factor_value(self):
        """Published after the cutoff, so no investor had it. Must be NaN."""
        funds = {"AAA": {"2021-09-30": statement()}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isnan(at(panel, FUND_I, "AAA")["ebit_ev"])


# ===========================================================================
# 3. Size uses the LAGGED share count, never today's
# ===========================================================================

class TestSizeUsesLaggedShares:
    """
    DESIGN.md rejects today's share count explicitly: this universe contains
    names diluting 28-72% a year, so today's count overstates historical market
    cap several-fold, and because heavy diluters underperform that error would
    load onto the historical large-cap buckets and manufacture a size effect
    out of a dilution effect.
    """

    def test_market_cap_uses_the_lagged_period_not_a_later_one(self):
        funds = {"AAA": {
            "2021-03-31": statement(shares=1_000.0),     # eligible
            "2021-09-30": statement(shares=10_000.0),    # too recent
        }}
        closes = [100.0] * N_MONTHS
        panel = panel_for({"AAA": closes}, funds)
        assert at(panel, FUND_I, "AAA")["size"] == pytest.approx(100_000.0)

    def test_market_cap_uses_the_rebalance_date_close(self):
        funds = {"AAA": {"2021-03-31": statement(shares=1_000.0)}}
        closes = [100.0] * N_MONTHS
        closes[FUND_I] = 7.0
        panel = panel_for({"AAA": closes}, funds)
        assert at(panel, FUND_I, "AAA")["size"] == pytest.approx(7_000.0)

    def test_no_share_count_means_no_size_and_no_value(self):
        funds = {"AAA": {"2021-03-31": statement(shares=np.nan)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        row = at(panel, FUND_I, "AAA")
        assert np.isnan(row["size"])
        assert np.isnan(row["ebit_ev"])


# ===========================================================================
# 4. Dilution
# ===========================================================================

class TestDilution:

    def test_a_doubling_of_shares_is_plus_one(self):
        funds = {"AAA": {
            "2018-03-31": statement(shares=100.0),
            "2021-03-31": statement(shares=200.0),
        }}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert at(panel, FUND_I, "AAA")["dilution"] == pytest.approx(1.0)

    def test_a_buyback_is_negative(self):
        funds = {"AAA": {
            "2018-03-31": statement(shares=200.0),
            "2021-03-31": statement(shares=100.0),
        }}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert at(panel, FUND_I, "AAA")["dilution"] == pytest.approx(-0.5)

    def test_no_period_near_three_years_back_yields_nan(self):
        """2019-03-31 is two years back, outside the 200-day tolerance."""
        funds = {"AAA": {
            "2019-03-31": statement(shares=100.0),
            "2021-03-31": statement(shares=200.0),
        }}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isnan(at(panel, FUND_I, "AAA")["dilution"])

    def test_lower_dilution_is_the_attractive_end(self):
        spec = {c: (h, s) for c, _, h, _, s, _ in
                [(f[0], f[1], f[2], f[3], f[4], f[5]) for f in fx.FACTORS]}
        higher_is_better, _ = spec["dilution"]
        assert higher_is_better is False


# ===========================================================================
# 5. Negative versus undefined -- the DESIGN.md rule
# ===========================================================================

class TestNegativeVersusUndefined:
    """
    A negative earnings yield is a MEASUREMENT and is kept at its raw value,
    which places it below every profitable name without any special-casing.
    A non-positive enterprise value is an ARTEFACT -- the ratio inverts, and a
    cash-rich profitable company would be ranked the worst name in the
    universe -- so it is excluded.
    """

    def test_negative_ebit_is_kept_and_is_negative(self):
        funds = {"AAA": {"2021-03-31": statement(ebit=-100.0)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        value = at(panel, FUND_I, "AAA")["ebit_ev"]
        assert np.isfinite(value) and value < 0

    def test_negative_fcf_is_kept_and_is_negative(self):
        funds = {"AAA": {"2021-03-31": statement(fcf=-80.0)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        value = at(panel, FUND_I, "AAA")["fcf_ev"]
        assert np.isfinite(value) and value < 0

    def test_negative_enterprise_value_is_excluded(self):
        """Cash far exceeds market cap plus debt, so EV <= 0."""
        funds = {"AAA": {"2021-03-31": statement(cash=10_000_000.0)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        row = at(panel, FUND_I, "AAA")
        assert np.isnan(row["ebit_ev"])
        assert np.isnan(row["fcf_ev"])

    def test_non_positive_total_assets_excludes_quality(self):
        funds = {"AAA": {"2021-03-31": statement(total_assets=0.0)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isnan(at(panel, FUND_I, "AAA")["gp_assets"])

    def test_an_absent_debt_line_excludes_value(self):
        funds = {"AAA": {"2021-03-31": statement(total_debt=np.nan)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isnan(at(panel, FUND_I, "AAA")["ebit_ev"])

    def test_an_absent_debt_line_does_not_block_quality(self):
        """Quality needs no enterprise value, so it survives."""
        funds = {"AAA": {"2021-03-31": statement(total_debt=np.nan)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert np.isfinite(at(panel, FUND_I, "AAA")["gp_assets"])

    def test_negative_gross_profit_is_kept(self):
        funds = {"AAA": {"2021-03-31": statement(gross_profit=-300.0)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        value = at(panel, FUND_I, "AAA")["gp_assets"]
        assert np.isfinite(value) and value < 0

    @pytest.mark.parametrize("fcf,expected", [(80.0, 1.0), (-80.0, 0.0),
                                              (0.0, 0.0)])
    def test_positive_fcf_binary(self, fcf, expected):
        funds = {"AAA": {"2021-03-31": statement(fcf=fcf)}}
        panel = panel_for({"AAA": [100.0] * N_MONTHS}, funds)
        assert at(panel, FUND_I, "AAA")["fcf_positive"] == expected


# ===========================================================================
# 6. Decile boundaries and ties
# ===========================================================================

class TestDeciles:

    def test_a_round_hundred_splits_evenly(self):
        d = fx.assign_deciles(pd.Series(range(100)), True)
        assert sorted(d.value_counts().tolist()) == [10] * 10

    def test_known_input_ranking_highest_goes_to_decile_ten(self):
        values = pd.Series(range(1, 101))
        d = fx.assign_deciles(values, True)
        assert d.iloc[-1] == 10
        assert d.iloc[0] == 1

    def test_direction_inverts_when_lower_is_better(self):
        values = pd.Series(range(1, 101))
        d = fx.assign_deciles(values, False)
        assert d.iloc[0] == 10, "lowest value is the attractive end"
        assert d.iloc[-1] == 1

    def test_the_extreme_deciles_are_always_equal_in_size(self):
        """D1 and D10 are what the headline spread compares."""
        for n in range(10, 60):
            d = fx.assign_deciles(pd.Series(range(n)), True)
            assert (d == 1).sum() == (d == 10).sum(), f"n={n}"

    def test_the_remainder_goes_to_the_middle(self):
        d = fx.assign_deciles(pd.Series(range(25)), True)
        sizes = [int((d == k).sum()) for k in range(1, 11)]
        assert sizes[0] == sizes[9] == min(sizes)
        assert max(sizes) in sizes[2:8]

    def test_a_tie_group_lands_in_exactly_one_decile(self):
        values = pd.Series([5.0] * 20 + list(range(100, 180)))
        d = fx.assign_deciles(values, True)
        tied = set(d[values == 5.0].dropna().tolist())
        assert len(tied) == 1, f"tie split across deciles {tied}"

    def test_an_all_tied_column_lands_in_one_decile(self):
        d = fx.assign_deciles(pd.Series([7.0] * 50), True)
        assert len(set(d.dropna().tolist())) == 1

    def test_fewer_than_ten_names_produces_no_deciles(self):
        d = fx.assign_deciles(pd.Series(range(9)), True)
        assert d.isna().all()

    def test_nan_values_never_receive_a_decile(self):
        values = pd.Series([np.nan] * 5 + list(range(20)))
        d = fx.assign_deciles(values, True)
        assert d.iloc[:5].isna().all()

    @pytest.mark.parametrize("n", [10, 11, 19, 20, 37, 100, 247])
    def test_every_decile_label_is_used(self, n):
        d = fx.assign_deciles(pd.Series(range(n)), True)
        assert set(d.dropna().unique()) == set(range(1, 11))


# ===========================================================================
# 7. Spread, IC and the statistics
# ===========================================================================

class TestSpreadAndIC:

    def frame(self, n=100, slope=1.0, dates=3):
        """A panel where forward return rises with the factor value."""
        rows = []
        for d in range(dates):
            for i in range(n):
                rows.append({
                    "date": pd.Timestamp("2023-01-31") + pd.DateOffset(months=d),
                    "symbol": f"S{i}",
                    "sector": "Industrials",
                    "median_dollar_volume": 5e6,
                    "factor": float(i),
                    "fwd_12m": slope * i / 100.0,
                })
        return pd.DataFrame(rows)

    def test_spread_is_positive_when_the_factor_works(self):
        res = fx.per_date_results(self.frame(), "factor", True, "12m", False)
        assert (res["spread"] > 0).all()

    def test_spread_flips_sign_with_the_direction_flag(self):
        up = fx.per_date_results(self.frame(), "factor", True, "12m", False)
        down = fx.per_date_results(self.frame(), "factor", False, "12m", False)
        assert up["spread"].mean() == pytest.approx(-down["spread"].mean())

    def test_spread_is_in_percentage_points(self):
        """A 1.0 fractional difference must report as 100 pp, not 1.0."""
        res = fx.per_date_results(self.frame(n=100, slope=1.0), "factor",
                                  True, "12m", False)
        assert res["spread"].iloc[0] > 50

    def test_ic_is_positive_when_the_factor_works(self):
        res = fx.per_date_results(self.frame(), "factor", True, "12m", False)
        assert (res["ic"] > 0.9).all()

    def test_ic_is_positive_for_a_lower_is_better_factor_that_works(self):
        """The direction flag must be applied to the IC too, not just the spread."""
        df = self.frame()
        df["fwd_12m"] = -df["fwd_12m"]
        res = fx.per_date_results(df, "factor", False, "12m", False)
        assert (res["ic"] > 0.9).all()

    def test_one_row_per_rebalance_date(self):
        res = fx.per_date_results(self.frame(dates=5), "factor", True, "12m",
                                  False)
        assert len(res) == 5

    def test_rows_with_no_forward_return_are_dropped(self):
        df = self.frame()
        df.loc[df["symbol"] == "S0", "fwd_12m"] = np.nan
        res = fx.per_date_results(df, "factor", True, "12m", False)
        assert (res["n"] == 99).all()

    def test_binary_mode_splits_on_zero(self):
        df = self.frame(n=100)
        df["factor"] = (df["factor"] >= 50).astype(float)
        res = fx.per_date_results(df, "factor", True, "12m", True)
        assert (res["n_top"] == 50).all() and (res["n_bottom"] == 50).all()


class TestBootstrapAndMDE:

    def test_the_bootstrap_is_deterministic(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert fx.bootstrap_ci(vals) == fx.bootstrap_ci(vals)

    def test_a_constant_series_has_a_zero_width_interval(self):
        lo, hi = fx.bootstrap_ci([4.0] * 20)
        assert lo == pytest.approx(4.0) and hi == pytest.approx(4.0)

    def test_the_interval_brackets_the_mean(self):
        vals = list(np.random.default_rng(1).normal(5.0, 2.0, 50))
        lo, hi = fx.bootstrap_ci(vals)
        assert lo < np.mean(vals) < hi

    def test_resampling_dates_gives_a_wider_interval_than_resampling_rows(self):
        """
        The by-date bootstrap must NOT be narrow. Three dates carry far less
        information than the 300 rows inside them, and an interval that did not
        reflect that would be the exact error DESIGN.md warns about.
        """
        three_dates = [1.0, 9.0, 5.0]
        lo, hi = fx.bootstrap_ci(three_dates)
        assert (hi - lo) > 3.0

    def test_mde_matches_the_preregistered_formula(self):
        vals = [1.0, 3.0, 5.0, 7.0, 9.0]
        expected = fx.Z_POWER * np.std(vals, ddof=1) / np.sqrt(len(vals))
        assert fx.mde(vals) == pytest.approx(expected)

    def test_mde_shrinks_with_more_dates(self):
        rng = np.random.default_rng(7)
        few = fx.mde(list(rng.normal(0, 10, 12)))
        many = fx.mde(list(rng.normal(0, 10, 48)))
        assert many < few

    def test_a_single_date_cannot_produce_an_mde(self):
        assert np.isnan(fx.mde([3.0]))

    def test_spearman_without_scipy(self):
        assert fx.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
        assert fx.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)

    def test_spearman_is_rank_based_not_level_based(self):
        """A monotone but wildly non-linear relation is still rank-perfect."""
        assert fx.spearman([1, 2, 3, 4], [1, 10, 1000, 1e9]) == pytest.approx(1.0)


# ===========================================================================
# 8. The sector exclusion and the factor specification
# ===========================================================================

class TestFundamentalLoading:
    """
    The cache stores an absent value as JSON null, which arrives as a Python
    None and makes the whole column object-dtype. np.isfinite RAISES on object
    dtype rather than returning False, so the loader must coerce.

    The hand-built fixtures above are all clean floats, which is tidier than
    the real cache -- this class reads an actual file with nulls in it, which
    is how the real data arrives.
    """

    def write(self, tmp_path, payload):
        path = tmp_path / "AAA.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def load(self, tmp_path, payload):
        self.write(tmp_path, payload)
        original = fx.fundamental_path
        fx.fundamental_path = lambda s: str(tmp_path / f"{s}.json")
        try:
            return fx.load_fundamentals(["AAA"])
        finally:
            fx.fundamental_path = original

    def test_json_nulls_become_float_nan_not_none(self, tmp_path):
        out = self.load(tmp_path, {
            "symbol": "AAA",
            "income": {"EBIT": {"2021-03-31": None}},
            "balance": {"Total Assets": {"2021-03-31": 1000.0}},
            "cashflow": {},
        })
        df = out["AAA"]
        assert df["ebit"].dtype.kind == "f", "object dtype breaks np.isfinite"
        assert np.isnan(df.loc[pd.Timestamp("2021-03-31"), "ebit"])

    def test_every_expected_field_exists_even_when_absent(self, tmp_path):
        out = self.load(tmp_path, {
            "symbol": "AAA",
            "income": {"EBIT": {"2021-03-31": 5.0}},
            "balance": {},
            "cashflow": {},
        })
        assert list(out["AAA"].columns) == list(fx.FIELDS)

    def test_all_columns_are_numeric(self, tmp_path):
        out = self.load(tmp_path, {
            "symbol": "AAA",
            "income": {"EBIT": {"2021-03-31": None, "2020-03-31": 5.0}},
            "balance": {"Total Debt": {"2021-03-31": None}},
            "cashflow": {"Free Cash Flow": {"2021-03-31": 1.5}},
        })
        assert all(k == "f" for k in out["AAA"].dtypes.map(lambda d: d.kind))

    def test_a_ticker_with_no_statements_is_skipped(self, tmp_path):
        out = self.load(tmp_path, {"symbol": "AAA", "income": {},
                                   "balance": {}, "cashflow": {}})
        assert "AAA" not in out


class TestSectorExclusion:

    def panel(self):
        rows = []
        for sector in ("Industrials", "Financial Services", "Real Estate"):
            rows.append({"date": pd.Timestamp("2023-12-31"), "symbol": sector[:3],
                         "sector": sector, "median_dollar_volume": 5e6,
                         "ebit_ev": 0.1, "momentum": 0.2})
        return pd.DataFrame(rows)

    def test_excluded_sectors_are_dropped_when_the_flag_is_set(self):
        kept = fx.eligible(self.panel(), "ebit_ev", True)["sector"].tolist()
        assert kept == ["Industrials"]

    def test_excluded_sectors_are_kept_when_the_flag_is_not_set(self):
        kept = fx.eligible(self.panel(), "momentum", False)["sector"]
        assert len(kept) == 3

    def test_the_exclusion_set_is_exactly_financials_and_real_estate(self):
        assert fx.SECTOR_EXCLUDED == {"Financial Services", "Real Estate"}


class TestFactorSpecification:
    """
    The confirmatory/exploratory split is the single most important thing in
    DESIGN.md. A config edit that quietly promoted a factor should fail here
    rather than reach FINDINGS.md.
    """

    def spec(self):
        return {f[0]: {"label": f[1], "higher": f[2], "confirmatory": f[3],
                       "sector_excl": f[4], "binary": f[5]} for f in fx.FACTORS}

    def test_momentum_is_the_only_confirmatory_factor(self):
        confirmatory = [c for c, s in self.spec().items() if s["confirmatory"]]
        assert confirmatory == ["momentum"]

    def test_size_is_not_confirmatory(self):
        """Demoted: the universe is selected on today's market cap."""
        assert self.spec()["size"]["confirmatory"] is False

    @pytest.mark.parametrize("column", ["ebit_ev", "fcf_ev", "gp_assets",
                                        "fcf_positive"])
    def test_value_and_quality_carry_the_sector_exclusion(self, column):
        assert self.spec()[column]["sector_excl"] is True

    @pytest.mark.parametrize("column", ["momentum", "dilution", "size"])
    def test_dilution_momentum_and_size_keep_financials(self, column):
        """Scoped exclusion: a share count and a past return suit a bank fine."""
        assert self.spec()[column]["sector_excl"] is False

    def test_the_preregistered_constants_are_unchanged(self):
        assert fx.PASS_THRESHOLD_PP == 3.0
        assert fx.MIN_PER_DECILE == 30
        assert fx.MIN_DATES == 12
        assert fx.CONFIRMATORY_HORIZON == "12m"
        assert fx.BOOTSTRAP_ITERS == 10_000
        assert fx.SEED == 42
        assert fx.FUNDAMENTAL_LAG_MONTHS == 6
        assert fx.MOMENTUM_LOOKBACK == 13
        assert fx.DILUTION_YEARS == 3
        assert fx.Z_POWER == 2.80
