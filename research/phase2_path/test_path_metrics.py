"""
Tests for the two path metrics.

The arithmetic under test is a window index subtraction:

    days_since_high = (recent_n - 1) - argmax(last recent_n closes)

This repo has already shipped one off-by-one in exactly this kind of index
arithmetic -- the volume window overlap bug, which inflated an apparent result
by up to 4x before it was caught. So the fencepost is pinned here explicitly,
from both ends and at every position in between, rather than trusted.

Three things are covered deliberately:

  1. Every peak position from 0 to recent_n - 1, so an off-by-one cannot hide
     in the middle of the range where it would still look plausible.
  2. Both boundaries on their own: peak-is-today must be 0, peak-at-window-
     start must be recent_n - 1. An implementation with the subtraction
     reversed passes a midpoint test and fails these.
  3. That the vectorised rolling pass agrees with the pure functions. The study
     reads its numbers from the rolling pass, so a window that silently drifts
     by one bar there would corrupt every result while the unit tests stayed
     green.

Nothing here touches the network or reads any cache. Every array is hand-built
so the correct answer is known in advance.

    pytest research/phase2_path/test_path_metrics.py -v
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import path_analysis as pa


# ===========================================================================
# Helpers
# ===========================================================================

def peak_at(position, recent_n=10, base=100.0, peak=200.0):
    """
    `recent_n` closes, all equal to `base` except a single clear peak at
    `position` (0 = oldest bar in the window).

    One unambiguous maximum, so the expected answer is arithmetic rather than a
    judgement call: days_since_high must be (recent_n - 1) - position.
    """
    closes = [base] * recent_n
    closes[position] = peak
    return closes


def frame_from(closes, start="2024-01-01"):
    """A price frame shaped like the ones the study builds."""
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame({"Close": [float(c) for c in closes]}, index=idx)


# ===========================================================================
# days_since_high
# ===========================================================================

class TestDaysSinceHigh:

    def test_known_array_with_an_obvious_peak(self):
        # Peak 20.0 sits at index 3 of ten closes, so the window peaked
        # 9 - 3 = 6 sessions ago. Worked by hand, not by running the code.
        closes = [10, 11, 12, 20, 13, 12, 11, 10, 9, 8]
        assert pa.days_since_high(closes, recent_n=10) == 6

    def test_peak_is_today(self):
        """The upper fencepost: a window still climbing scores 0."""
        closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert pa.days_since_high(closes, recent_n=10) == 0

    def test_peak_is_window_start(self):
        """The lower fencepost: a window falling the whole way scores 9."""
        closes = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        assert pa.days_since_high(closes, recent_n=10) == 9

    @pytest.mark.parametrize("position", range(10))
    def test_every_peak_position_in_the_window(self, position):
        """
        Sweeps the whole range. An implementation off by one, or with the
        subtraction the wrong way round, fails somewhere in here even if it
        happens to agree at the midpoint.
        """
        closes = peak_at(position, recent_n=10)
        assert pa.days_since_high(closes, recent_n=10) == 9 - position

    def test_result_is_always_inside_the_window(self):
        rng = np.random.default_rng(0)
        for _ in range(200):
            closes = rng.normal(100, 10, size=10)
            assert 0 <= pa.days_since_high(closes, recent_n=10) <= 9

    def test_ties_go_to_the_earlier_bar(self):
        """
        Two bars at the same high are scored as the STALER of the two. That is
        the conservative direction -- a tie never flatters the fresh group --
        and it is a deliberate choice, so it is pinned.
        """
        closes = [100, 200, 100, 100, 100, 100, 100, 100, 200, 100]
        assert pa.days_since_high(closes, recent_n=10) == 8

    def test_a_flat_window_counts_as_stale(self):
        """
        Every close equal means the first bar is the argmax, so a flat window
        reads as having peaked at the start. Defensible -- nothing about a flat
        window is fresh -- but surprising enough to pin.
        """
        assert pa.days_since_high([100] * 10, recent_n=10) == 9

    def test_only_the_last_recent_n_closes_are_used(self):
        """
        A much higher close before the window must be ignored. If the window
        were taken from the wrong end, this returns 9 instead of 0.
        """
        closes = [999, 999, 999] + [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert pa.days_since_high(closes, recent_n=10) == 0

    def test_exactly_recent_n_closes_is_enough(self):
        assert pa.days_since_high([1] * 10, recent_n=10) == 9

    def test_too_few_closes_raises(self):
        with pytest.raises(ValueError):
            pa.days_since_high([1, 2, 3], recent_n=10)

    def test_single_bar_window_is_always_zero(self):
        assert pa.days_since_high([42], recent_n=1) == 0

    def test_window_of_zero_or_less_raises(self):
        with pytest.raises(ValueError):
            pa.days_since_high([1, 2, 3], recent_n=0)

    def test_accepts_list_series_and_array_alike(self):
        closes = [10, 11, 12, 20, 13, 12, 11, 10, 9, 8]
        expected = 6
        assert pa.days_since_high(closes, recent_n=10) == expected
        assert pa.days_since_high(np.array(closes), recent_n=10) == expected
        assert pa.days_since_high(pd.Series(closes), recent_n=10) == expected

    def test_returns_a_plain_int(self):
        """
        The value is written to CSV and compared against integer buckets, so a
        numpy type leaking out here would show up as 6.0 in the output.
        """
        value = pa.days_since_high([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], recent_n=10)
        assert isinstance(value, int)

    def test_defaults_to_the_configured_window(self):
        """Default recent_n must track config, not a hardcoded 10."""
        assert pa.RECENT_N == 10
        closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert pa.days_since_high(closes) == pa.days_since_high(closes, 10)


# ===========================================================================
# drawdown_from_high
# ===========================================================================

class TestDrawdownFromHigh:

    def test_peak_is_today_means_no_drawdown(self):
        closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert pa.drawdown_from_high(closes, recent_n=10) == 0.0

    def test_known_numbers(self):
        # High 200, last close 150: (200 - 150) / 200 = 0.25.
        closes = [100, 200, 100, 100, 100, 100, 100, 100, 100, 150]
        assert pa.drawdown_from_high(closes, recent_n=10) == pytest.approx(0.25)

    def test_peak_at_window_start_with_a_fall(self):
        closes = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
        assert pa.drawdown_from_high(closes, recent_n=10) == pytest.approx(0.9)

    def test_flat_window_has_no_drawdown(self):
        assert pa.drawdown_from_high([100] * 10, recent_n=10) == 0.0

    def test_never_negative(self):
        rng = np.random.default_rng(1)
        for _ in range(200):
            closes = rng.normal(100, 15, size=10)
            assert pa.drawdown_from_high(closes, recent_n=10) >= 0.0

    def test_only_the_last_recent_n_closes_are_used(self):
        """A crash before the window must not count against today."""
        closes = [1000, 1000, 1000] + [100] * 10
        assert pa.drawdown_from_high(closes, recent_n=10) == 0.0

    def test_non_positive_high_returns_nan_rather_than_dividing_by_zero(self):
        assert np.isnan(pa.drawdown_from_high([0.0] * 10, recent_n=10))
        assert np.isnan(pa.drawdown_from_high([-5.0] * 10, recent_n=10))

    def test_too_few_closes_raises(self):
        with pytest.raises(ValueError):
            pa.drawdown_from_high([1, 2, 3], recent_n=10)

    def test_returns_a_plain_float(self):
        value = pa.drawdown_from_high([100] * 9 + [50], recent_n=10)
        assert isinstance(value, float)

    def test_zero_drawdown_exactly_when_peak_is_today(self):
        """
        The two metrics must agree about freshness at the boundary: drawdown is
        zero if and only if days_since_high is 0, for strictly-varying closes.
        """
        rng = np.random.default_rng(2)
        for _ in range(200):
            closes = rng.normal(100, 10, size=10)
            fresh_today = pa.days_since_high(closes, 10) == 0
            no_drawdown = pa.drawdown_from_high(closes, 10) == 0.0
            assert fresh_today == no_drawdown


# ===========================================================================
# The preregistered fresh/stale cut
# ===========================================================================

class TestClassify:

    @pytest.mark.parametrize("days,expected", [
        (0, "fresh"),
        (1, "fresh"),
        (2, "fresh"),     # last fresh bucket
        (3, "dropped"),   # first dropped bucket
        (4, "dropped"),   # last dropped bucket
        (5, "stale"),     # first stale bucket
        (6, "stale"),
        (9, "stale"),
    ])
    def test_every_bucket_lands_where_preregistered(self, days, expected):
        assert pa.classify(days) == expected

    def test_missing_metric_is_unknown_not_fresh(self):
        """
        A nan must never be swept into fresh -- that would put unscored alerts
        into the group the hypothesis predicts will win.
        """
        assert pa.classify(np.nan) == "unknown"
        assert pa.classify(None) == "unknown"

    def test_the_cut_matches_the_preregistered_constants(self):
        assert pa.FRESH_MAX == 2
        assert pa.STALE_MIN == 5
        assert pa.classify(pa.FRESH_MAX) == "fresh"
        assert pa.classify(pa.STALE_MIN) == "stale"

    def test_no_bucket_is_left_unclassified(self):
        labels = {pa.classify(d) for d in range(pa.RECENT_N)}
        assert labels == {"fresh", "dropped", "stale"}


# ===========================================================================
# The vectorised pass must agree with the pure functions
# ===========================================================================

class TestVectorisedPathMetrics:
    """
    The study reads its numbers from add_path_metrics, not from the pure
    functions directly. A rolling window that drifts by one bar there would
    corrupt every result while the unit tests above stayed green, so the two
    are checked against each other on a hand-built series.
    """

    def test_matches_the_pure_function_at_every_row(self):
        rng = np.random.default_rng(3)
        closes = rng.normal(100, 10, size=60).tolist()
        out = pa.add_path_metrics(frame_from(closes))

        for i in range(len(closes)):
            if i < pa.RECENT_N - 1:
                assert pd.isna(out["days_since_high"].iloc[i])
                continue
            window = closes[: i + 1]
            assert out["days_since_high"].iloc[i] == pa.days_since_high(window)
            assert out["drawdown_from_high"].iloc[i] == pytest.approx(
                pa.drawdown_from_high(window)
            )

    def test_the_window_ends_on_the_current_bar(self):
        """
        A trailing window includes today. If the rolling pass were shifted by
        one, this row would read 1 instead of 0 -- the exact off-by-one this
        study is about, in the code that produces its numbers.
        """
        closes = [100] * 20
        closes[14] = 500          # peak on the bar being inspected
        out = pa.add_path_metrics(frame_from(closes))
        assert out["days_since_high"].iloc[14] == 0
        assert out["days_since_high"].iloc[15] == 1

    def test_first_rows_are_nan_not_silently_filled(self):
        """
        Fewer than RECENT_N closes means the metric is undefined. A zero there
        would read as 'peaked today' and land in the fresh group.
        """
        out = pa.add_path_metrics(frame_from([100] * 15))
        assert out["days_since_high"].iloc[: pa.RECENT_N - 1].isna().all()
        assert out["days_since_high"].iloc[pa.RECENT_N - 1 :].notna().all()

    def test_forward_returns_look_forward_by_the_right_number_of_bars(self):
        """
        Forward returns are the outcome being measured. The shift direction is
        pinned here: a sign error would make the study measure the past.
        """
        closes = [100 + i for i in range(40)]
        out = pa.add_path_metrics(frame_from(closes))

        for h in pa.HORIZONS:
            expected = closes[5 + h] / closes[5] - 1
            assert out[f"fwd_{h}d"].iloc[5] == pytest.approx(expected)

    def test_every_study_horizon_is_present(self):
        out = pa.add_path_metrics(frame_from([100 + i for i in range(40)]))
        for h in pa.HORIZONS:
            assert f"fwd_{h}d" in out
        assert pa.CONFIRMATORY_HORIZON in pa.HORIZONS

    def test_forward_returns_run_off_the_end_as_nan(self):
        out = pa.add_path_metrics(frame_from([100 + i for i in range(40)]))
        assert out["fwd_21d"].iloc[-1:].isna().all()
        assert out["fwd_21d"].iloc[-21:].isna().all()

    def test_does_not_mutate_the_input_frame(self):
        frame = frame_from([100 + i for i in range(40)])
        before = list(frame.columns)
        pa.add_path_metrics(frame)
        assert list(frame.columns) == before
