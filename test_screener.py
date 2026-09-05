"""
Test suite for the screener.

Focused on the pure logic that produces numbers -- the metric calculations, the
streak counting, the cooldown rules and the run-log accounting. These are the
functions whose output ends up in research conclusions, so a silent error here
is worse than a crash.

Nothing here touches the network. Price data is hand-built so the correct answer
is known in advance, and yfinance objects are replaced with small fakes.

    python -m pip install pytest
    pytest -v
"""

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

import config
import screener
import notifier
import heartbeat_monitor as monitor


# ===========================================================================
# Helpers
# ===========================================================================

def make_history(n_days=100, price=100.0, volume=1_000_000):
    """Flat price and volume history. Baseline case: every ratio is 1.0."""
    idx = pd.date_range("2024-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {"Close": [float(price)] * n_days, "Volume": [volume] * n_days},
        index=idx,
    )


class FakeTicker:
    """Stands in for yf.Ticker, exposing only what the screener reads."""

    def __init__(self, cashflow=None, fast_info=None, raise_on_cashflow=False):
        self._cashflow = cashflow
        self.fast_info = fast_info or {}
        self._raise = raise_on_cashflow

    @property
    def quarterly_cashflow(self):
        if self._raise:
            raise RuntimeError("network down")
        return self._cashflow

    @property
    def info(self):
        return {}


def cashflow_frame(label, values):
    """Quarterly cash flow frame in yfinance's shape: rows are line items."""
    cols = pd.date_range("2026-03-31", periods=len(values), freq="-1QE")
    return pd.DataFrame([values], index=[label], columns=cols)


# ===========================================================================
# Dollar volume and price momentum
# ===========================================================================

class TestPriceAndVolume:

    def test_flat_history_gives_ratio_of_one(self):
        """Constant price and volume must produce exactly 1.0 and 0% change."""
        result = screener.compute_price_and_volume(make_history())

        assert result is not None
        assert result["volume_ratio"] == pytest.approx(1.0)
        assert result["price_change"] == pytest.approx(0.0)

    def test_recent_volume_doubling_raises_the_ratio(self):
        df = make_history(n_days=100)
        df.iloc[-config.RECENT_WINDOW_DAYS:, df.columns.get_loc("Volume")] *= 2

        result = screener.compute_price_and_volume(df)

        # Recent window is 2x; baseline includes those days, so the ratio lands
        # between 1 and 2 rather than exactly at 2.
        assert 1.0 < result["volume_ratio"] < 2.0
        assert result["volume_ratio"] > config.VOLUME_SURGE_THRESHOLD

    def test_dollar_volume_uses_price_not_share_count(self):
        """
        The core design decision: a high-priced stock moving the same number of
        shares represents far more money. Ratios are unit-free, so both flat
        series give 1.0 -- but the recorded dollar volume must differ 10x.
        """
        cheap = screener.compute_price_and_volume(
            make_history(price=10.0, volume=1_000_000))
        pricey = screener.compute_price_and_volume(
            make_history(price=100.0, volume=1_000_000))

        assert cheap["volume_ratio"] == pytest.approx(pricey["volume_ratio"])
        assert pricey["recent_avg_dollar_volume"] == pytest.approx(
            cheap["recent_avg_dollar_volume"] * 10)

    def test_price_change_measures_endpoints_only(self):
        """
        Price momentum compares two single closes, not averages. A spike in
        between must not affect the result.
        """
        df = make_history(n_days=100)
        close = df.columns.get_loc("Close")

        df.iloc[-1, close] = 110.0                       # +10% vs 10 days ago
        df.iloc[-5, close] = 500.0                       # noise in the middle

        result = screener.compute_price_and_volume(df)
        assert result["price_change"] == pytest.approx(0.10)

    def test_negative_price_change_is_reported(self):
        df = make_history(n_days=100)
        df.iloc[-1, df.columns.get_loc("Close")] = 80.0

        result = screener.compute_price_and_volume(df)
        assert result["price_change"] == pytest.approx(-0.20)

    def test_insufficient_history_returns_none(self):
        """Fewer bars than the baseline window means 'normal' is undefined."""
        short = make_history(n_days=config.BASELINE_WINDOW_DAYS - 5)
        assert screener.compute_price_and_volume(short) is None

    def test_zero_volume_baseline_returns_none(self):
        """Guards against division by zero on a non-trading instrument."""
        df = make_history(n_days=100, volume=0)
        assert screener.compute_price_and_volume(df) is None

    def test_no_lookahead_in_the_calculation(self):
        """
        Truncating the future must not change today's numbers. If it does, the
        metric is peeking forward and every backtest result is invalid.
        """
        full = make_history(n_days=150)
        full.iloc[-1, full.columns.get_loc("Close")] = 999.0   # extreme future

        truncated = full.iloc[:100]
        a = screener.compute_price_and_volume(truncated)
        b = screener.compute_price_and_volume(full.iloc[:100])

        assert a["volume_ratio"] == pytest.approx(b["volume_ratio"])
        assert a["price_change"] == pytest.approx(b["price_change"])


# ===========================================================================
# TTM cash from operations
# ===========================================================================

class TestTTMCashFlow:

    def test_sums_the_four_most_recent_quarters(self):
        t = FakeTicker(cashflow=cashflow_frame(
            "Operating Cash Flow", [100.0, 200.0, 300.0, 400.0]))
        assert screener.extract_ttm_cfo(t) == pytest.approx(1000.0)

    def test_ignores_quarters_beyond_the_most_recent_four(self):
        """TTM means twelve months. A fifth quarter must not be included."""
        t = FakeTicker(cashflow=cashflow_frame(
            "Operating Cash Flow", [100.0, 100.0, 100.0, 100.0, 9999.0]))
        assert screener.extract_ttm_cfo(t) == pytest.approx(400.0)

    def test_accepts_alternative_row_labels(self):
        """yfinance has renamed this field across versions."""
        t = FakeTicker(cashflow=cashflow_frame(
            "Total Cash From Operating Activities", [50.0] * 4))
        assert screener.extract_ttm_cfo(t) == pytest.approx(200.0)

    def test_negative_cash_flow_is_preserved(self):
        """Cash-burning companies must return a negative number, not None."""
        t = FakeTicker(cashflow=cashflow_frame(
            "Operating Cash Flow", [-500.0, -400.0, -300.0, -200.0]))
        result = screener.extract_ttm_cfo(t)
        assert result == pytest.approx(-1400.0)
        assert result < 0

    def test_fewer_than_four_quarters_returns_none(self):
        """A partial year is not a TTM figure and must not be treated as one."""
        t = FakeTicker(cashflow=cashflow_frame(
            "Operating Cash Flow", [100.0, 100.0]))
        assert screener.extract_ttm_cfo(t) is None

    def test_missing_or_empty_data_returns_none(self):
        assert screener.extract_ttm_cfo(FakeTicker(cashflow=None)) is None
        assert screener.extract_ttm_cfo(FakeTicker(cashflow=pd.DataFrame())) is None

    def test_unknown_label_returns_none(self):
        t = FakeTicker(cashflow=cashflow_frame("Something Else", [1.0] * 4))
        assert screener.extract_ttm_cfo(t) is None

    def test_network_error_returns_none_rather_than_raising(self):
        """One bad ticker must not abort the whole run."""
        assert screener.extract_ttm_cfo(FakeTicker(raise_on_cashflow=True)) is None


# ===========================================================================
# Market cap
# ===========================================================================

class TestMarketCap:

    def test_reads_camelcase_key(self):
        """yfinance 1.x renamed market_cap to marketCap."""
        t = FakeTicker(fast_info={"marketCap": 1.5e12})
        assert screener.get_market_cap(t) == pytest.approx(1.5e12)

    def test_reads_snakecase_key(self):
        t = FakeTicker(fast_info={"market_cap": 5.0e9})
        assert screener.get_market_cap(t) == pytest.approx(5.0e9)

    def test_falls_back_to_shares_times_price(self):
        t = FakeTicker(fast_info={"shares": 1_000_000, "lastPrice": 250.0})
        assert screener.get_market_cap(t) == pytest.approx(2.5e8)

    def test_returns_none_when_nothing_available(self):
        assert screener.get_market_cap(FakeTicker(fast_info={})) is None


# ===========================================================================
# Streak counting
# ===========================================================================

class TestStreaks:

    def test_counts_qualifying_days_inside_the_window(self):
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(5)]

        count, span = notifier.current_streak(dates)
        assert count == 5

    def test_days_need_not_be_consecutive(self):
        """
        A gap must not reset the count. The metric is 'how many days out of the
        last N', not 'how many in a row' -- matching what was backtested.
        """
        today = datetime.now().date()
        dates = [
            (today - timedelta(days=0)).isoformat(),
            (today - timedelta(days=1)).isoformat(),
            (today - timedelta(days=5)).isoformat(),   # gap on days 2-4
            (today - timedelta(days=6)).isoformat(),
        ]
        count, _ = notifier.current_streak(dates)
        assert count == 4

    def test_dates_outside_the_window_are_excluded(self):
        today = datetime.now().date()
        dates = [
            (today - timedelta(days=1)).isoformat(),
            (today - timedelta(days=2)).isoformat(),
            (today - timedelta(days=config.STREAK_WINDOW_DAYS + 10)).isoformat(),
        ]
        count, _ = notifier.current_streak(dates)
        assert count == 2

    def test_prune_drops_dates_older_than_the_tracking_window(self):
        today = datetime.now().date()
        dates = [
            (today - timedelta(days=5)).isoformat(),
            (today - timedelta(days=200)).isoformat(),
        ]
        kept = notifier.prune_old_dates(dates, window_days=90)
        assert len(kept) == 1

    def test_prune_deduplicates_and_sorts(self):
        today = datetime.now().date()
        d1 = (today - timedelta(days=1)).isoformat()
        d2 = (today - timedelta(days=2)).isoformat()

        kept = notifier.prune_old_dates([d1, d2, d1], window_days=90)
        assert kept == sorted([d2, d1])

    def test_malformed_dates_are_ignored_not_fatal(self):
        today = datetime.now().date()
        dates = [(today - timedelta(days=1)).isoformat(), "not-a-date", ""]

        assert notifier.current_streak(dates)[0] == 1
        assert len(notifier.prune_old_dates(dates)) == 1

    def test_empty_history_gives_zero(self):
        assert notifier.current_streak([]) == (0, 0)


class TestStreakLabels:

    def test_single_day_is_labelled_new(self):
        _, level = notifier.describe_streak(1, 1)
        assert level == "new"

    def test_below_threshold_is_labelled_building(self):
        below = config.PERSISTENT_STREAK_MIN - 1
        _, level = notifier.describe_streak(below, below)
        assert level == "building"

    def test_at_threshold_is_labelled_strong(self):
        n = config.PERSISTENT_STREAK_MIN
        _, level = notifier.describe_streak(n, n)
        assert level == "strong"

    def test_above_threshold_is_labelled_strong(self):
        n = config.PERSISTENT_STREAK_MIN + 5
        _, level = notifier.describe_streak(n, n)
        assert level == "strong"


# ===========================================================================
# Cooldown and history recording
# ===========================================================================

@pytest.fixture
def temp_history(tmp_path, monkeypatch):
    """Point the alert history at a throwaway file."""
    path = tmp_path / "alerts_history.json"
    path.write_text("{}")
    monkeypatch.setattr(config, "ALERTS_HISTORY_FILE", str(path))
    return path


def a_match(ticker="NBIS"):
    return {
        "ticker": ticker, "company": "Test Co", "category": "Neo Cloud",
        "exchange": "NASDAQ", "price": 100.0, "price_change_pct": 10.0,
        "volume_ratio": 1.6, "recent_dollar_vol_musd": 500.0,
        "ttm_cfo_musd": 100.0, "market_cap_busd": 10.0,
    }


class TestCooldownAndRecording:

    def test_first_sighting_is_sent(self, temp_history):
        to_send, _ = notifier.record_and_filter([a_match()], {})
        assert len(to_send) == 1
        assert to_send[0]["streak_level"] == "new"

    def test_qualifying_day_is_recorded_even_when_not_emailed(self, temp_history):
        """
        The point of the design: a day inside the cooldown must still count
        toward the streak, or persistence can never accumulate.
        """
        history = {"NBIS": {
            "qualifying_dates": [],
            "last_emailed": datetime.now().isoformat(),   # just emailed
        }}

        to_send, history = notifier.record_and_filter([a_match()], history)

        assert to_send == []                                    # suppressed
        assert len(history["NBIS"]["qualifying_dates"]) == 1     # still recorded

    def test_same_day_twice_does_not_double_count(self, temp_history):
        """Two runs on one date must not inflate the streak."""
        history = {}
        _, history = notifier.record_and_filter([a_match()], history)
        _, history = notifier.record_and_filter([a_match()], history)

        assert len(history["NBIS"]["qualifying_dates"]) == 1

    def test_crossing_the_persistence_threshold_breaks_the_cooldown(self, temp_history):
        """
        Reaching persistent status is the signal worth interrupting for, so it
        sends even inside the cooldown -- but only once.
        """
        today = datetime.now().date()
        prior = [
            (today - timedelta(days=i)).isoformat()
            for i in range(1, config.PERSISTENT_STREAK_MIN)
        ]
        history = {"NBIS": {
            "qualifying_dates": prior,
            "last_emailed": datetime.now().isoformat(),
        }}

        to_send, history = notifier.record_and_filter([a_match()], history)

        assert len(to_send) == 1
        assert to_send[0]["streak_level"] == "strong"
        assert history["NBIS"]["persistence_notified"] is True

    def test_persistence_alert_does_not_repeat(self, temp_history):
        today = datetime.now().date()
        prior = [
            (today - timedelta(days=i)).isoformat()
            for i in range(1, config.PERSISTENT_STREAK_MIN + 2)
        ]
        history = {"NBIS": {
            "qualifying_dates": prior,
            "last_emailed": datetime.now().isoformat(),
            "persistence_notified": True,
        }}

        to_send, _ = notifier.record_and_filter([a_match()], history)
        assert to_send == []

    def test_each_ticker_has_its_own_cooldown(self, temp_history):
        """A new ticker must alert even if another was just emailed."""
        history = {"NBIS": {
            "qualifying_dates": [],
            "last_emailed": datetime.now().isoformat(),
        }}

        to_send, _ = notifier.record_and_filter(
            [a_match("NBIS"), a_match("IREN")], history)

        assert [m["ticker"] for m in to_send] == ["IREN"]

    def test_expired_cooldown_allows_a_new_email(self, temp_history):
        old = datetime.now() - timedelta(days=config.ALERT_COOLDOWN_DAYS + 1)
        history = {"NBIS": {
            "qualifying_dates": [],
            "last_emailed": old.isoformat(),
        }}

        to_send, _ = notifier.record_and_filter([a_match()], history)
        assert len(to_send) == 1


# ===========================================================================
# Monitoring
# ===========================================================================

@pytest.fixture
def temp_run_log(tmp_path, monkeypatch):
    path = tmp_path / "run_log.json"
    path.write_text("[]")
    monkeypatch.setattr(monitor, "RUN_LOG_FILE", str(path))
    return path


class TestRunLog:

    def test_successful_run_is_appended(self, temp_run_log):
        entries = monitor.record_run("ok", tickers_screened=60,
                                     matches=[a_match()])

        assert len(entries) == 1
        assert entries[0]["status"] == "ok"
        assert entries[0]["match_count"] == 1
        assert entries[0]["matches"] == ["NBIS"]

    def test_failed_run_is_appended_with_the_error(self, temp_run_log):
        entries = monitor.record_run("error", error=ValueError("boom"))

        assert entries[0]["status"] == "error"
        assert "boom" in entries[0]["error"]

    def test_entries_persist_across_calls(self, temp_run_log):
        monitor.record_run("ok", tickers_screened=60)
        entries = monitor.record_run("ok", tickers_screened=60)
        assert len(entries) == 2

    def test_log_is_capped(self, temp_run_log, monkeypatch):
        monkeypatch.setattr(monitor, "MAX_LOG_ENTRIES", 5)
        for _ in range(10):
            entries = monitor.record_run("ok")
        assert len(entries) == 5

    def test_corrupt_log_does_not_crash(self, temp_run_log):
        temp_run_log.write_text("{ not json")
        assert monitor.load_run_log() == []


class TestWeekdayCounting:

    def test_counts_only_monday_to_friday(self):
        # 2026-08-24 is a Monday, 2026-08-30 a Sunday
        start = datetime(2026, 8, 24).date()
        end = datetime(2026, 8, 30).date()
        assert monitor._expected_weekdays(start, end) == 5

    def test_single_weekend_day_counts_zero(self):
        sat = datetime(2026, 8, 29).date()
        assert monitor._expected_weekdays(sat, sat) == 0


class TestWeeklySummary:

    def test_runs_and_missing_days_reconcile(self, temp_run_log, tmp_path,
                                             monkeypatch):
        """
        actual_runs + missing_dates must equal expected_runs. An early version
        counted weekend runs in the total while the weekday they did not cover
        still showed as missing, so the summary contradicted itself.
        """
        monkeypatch.setattr(config, "ALERTS_HISTORY_FILE",
                            str(tmp_path / "none.json"))

        today = datetime.now().date()
        entries = []
        for i in range(7):
            d = today - timedelta(days=i)
            entries.append({
                "timestamp": f"{d.isoformat()}T21:15:00",
                "date": d.isoformat(),
                "status": "ok", "tickers_screened": 60,
                "match_count": 0, "matches": [], "near_misses": [],
                "error": None,
            })
        monitor.save_run_log(entries)

        s = monitor.build_weekly_summary()
        assert s["actual_runs"] + len(s["missing_dates"]) == s["expected_runs"]

    def test_failures_are_counted(self, temp_run_log, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "ALERTS_HISTORY_FILE",
                            str(tmp_path / "none.json"))

        # Use a known weekday so the entry is definitely counted
        d = datetime.now().date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)

        monitor.save_run_log([{
            "timestamp": f"{d.isoformat()}T21:15:00", "date": d.isoformat(),
            "status": "error", "tickers_screened": 0, "match_count": 0,
            "matches": [], "near_misses": [], "error": "HTTPError 429",
        }])

        s = monitor.build_weekly_summary()
        assert s["failed_runs"] == 1

    def test_summary_renders_without_error(self, temp_run_log, tmp_path,
                                           monkeypatch):
        monkeypatch.setattr(config, "ALERTS_HISTORY_FILE",
                            str(tmp_path / "none.json"))
        s = monitor.build_weekly_summary()
        text = monitor.format_weekly_plaintext(s)
        assert "Screener weekly summary" in text

    def test_multiple_runs_on_one_day_count_once(self, temp_run_log, tmp_path,
                                                 monkeypatch):
        """
        Three runs on one date must count as one day. A duplicated record_run
        call produced two entries per run, and the weekly summary reported
        "8 of 5 runs" alongside a missing day -- arithmetically impossible.
        """
        monkeypatch.setattr(config, "ALERTS_HISTORY_FILE",
                            str(tmp_path / "none.json"))

        d = datetime.now().date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)

        entries = [{
            "timestamp": f"{d.isoformat()}T{h:02d}:00:00", "date": d.isoformat(),
            "status": "ok", "tickers_screened": 60, "match_count": 0,
            "matches": [], "near_misses": [], "error": None,
        } for h in (9, 14, 21)]
        monitor.save_run_log(entries)

        s = monitor.build_weekly_summary()
        assert s["actual_runs"] == 1
        assert d.isoformat() not in s["missing_dates"]


class TestNearMisses:

    def _results(self):
        return pd.DataFrame([
            # ticker, ratio, price change, cfo passed, matched
            {"ticker": "AAA", "volume_ratio": 1.47, "price_change_pct": 6.8,
             "pass_cfo": True, "MATCH": False},
            {"ticker": "BBB", "volume_ratio": 0.55, "price_change_pct": -12.0,
             "pass_cfo": True, "MATCH": False},
            {"ticker": "CCC", "volume_ratio": 1.60, "price_change_pct": 9.0,
             "pass_cfo": True, "MATCH": True},
            {"ticker": "DDD", "volume_ratio": 1.49, "price_change_pct": 6.9,
             "pass_cfo": False, "MATCH": False},
        ])

    def test_closest_non_matching_ticker_is_first(self):
        near = monitor.find_near_misses(self._results(), top_n=2)
        assert near[0]["ticker"] == "AAA"

    def test_matches_are_excluded(self):
        near = monitor.find_near_misses(self._results(), top_n=4)
        assert "CCC" not in [n["ticker"] for n in near]

    def test_cash_flow_failures_are_excluded(self):
        """DDD is numerically closest but fails the quality gate."""
        near = monitor.find_near_misses(self._results(), top_n=4)
        assert "DDD" not in [n["ticker"] for n in near]

    def test_empty_input_returns_empty_list(self):
        assert monitor.find_near_misses(pd.DataFrame()) == []
        assert monitor.find_near_misses(None) == []

    

# ===========================================================================
# Threshold consistency
# ===========================================================================

class TestConfig:

    def test_windows_are_ordered(self):
        assert config.RECENT_WINDOW_DAYS < config.BASELINE_WINDOW_DAYS

    def test_volume_threshold_is_above_normal(self):
        """A threshold at or below 1.0 would fire on ordinary activity."""
        assert config.VOLUME_SURGE_THRESHOLD > 1.0

    def test_streak_threshold_fits_inside_its_window(self):
        """
        PERSISTENT_STREAK_MIN must be reachable. If it exceeds the number of
        trading days in the window, the green tier can never trigger.
        """
        approx_trading_days = config.STREAK_WINDOW_DAYS * 5 / 7
        assert config.PERSISTENT_STREAK_MIN <= approx_trading_days