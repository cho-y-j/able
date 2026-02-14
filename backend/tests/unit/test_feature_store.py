"""Unit tests for the Feature Store and AI Analyst modules.

Covers:
  - time_patterns.analyze_time_patterns (day-of-week, monthly, streaks, summary)
  - indicator_combos.analyze_indicator_accuracy / find_best_combos
  - fact_sheet.generate_fact_sheet / get_current_signals
  - ai_analyst._parse_ai_response
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from app.analysis.features.time_patterns import analyze_time_patterns, _compute_streaks
from app.analysis.features.indicator_combos import analyze_indicator_accuracy, find_best_combos
from app.analysis.features.fact_sheet import generate_fact_sheet, get_current_signals, _current_streak
from app.services.ai_analyst import _parse_ai_response


# ── Helpers ─────────────────────────────────────────────────────────


def make_test_df(n=200):
    """Create a realistic test OHLCV DataFrame."""
    dates = pd.bdate_range("2024-01-02", periods=n, freq="B")
    np.random.seed(42)
    close = 70000 + np.cumsum(np.random.randn(n) * 500)
    df = pd.DataFrame(
        {
            "open": close - np.random.rand(n) * 200,
            "high": close + np.abs(np.random.randn(n)) * 300,
            "low": close - np.abs(np.random.randn(n)) * 300,
            "close": close,
            "volume": np.random.randint(1_000_000, 10_000_000, n),
        },
        index=dates,
    )
    return df


def _make_mock_signal_generator(df, buy_every=10, sell_every=15):
    """Create a mock signal generator that fires periodic buy/sell signals."""
    entry = pd.Series(False, index=df.index)
    exit_ = pd.Series(False, index=df.index)
    for i in range(0, len(df), buy_every):
        entry.iloc[i] = True
    for i in range(0, len(df), sell_every):
        exit_.iloc[i] = True
    return entry, exit_


# ── Time Patterns ───────────────────────────────────────────────────


class TestTimePatterns:
    """Tests for analyze_time_patterns."""

    def test_returns_expected_top_level_keys(self):
        df = make_test_df(200)
        result = analyze_time_patterns(df)

        assert isinstance(result, dict)
        assert "day_of_week" in result
        assert "monthly" in result
        assert "streaks" in result
        assert "summary" in result

    def test_day_of_week_has_korean_day_names(self):
        df = make_test_df(200)
        result = analyze_time_patterns(df)

        dow = result["day_of_week"]
        korean_days = {"월", "화", "수", "목", "금"}
        # All keys should be Korean day names
        assert set(dow.keys()).issubset(korean_days)
        # With 200 business days we expect all weekdays represented
        assert len(dow) >= 4

    def test_day_of_week_entry_structure(self):
        df = make_test_df(200)
        result = analyze_time_patterns(df)

        for day_name, stats in result["day_of_week"].items():
            assert "win_rate" in stats
            assert "avg_return" in stats
            assert "sample_count" in stats
            assert "avg_up_return" in stats
            assert "avg_down_return" in stats
            assert 0 <= stats["win_rate"] <= 100
            assert stats["sample_count"] > 0
            assert isinstance(stats["avg_return"], float)

    def test_monthly_patterns(self):
        df = make_test_df(250)
        result = analyze_time_patterns(df)

        monthly = result["monthly"]
        assert len(monthly) > 0
        for month_name, stats in monthly.items():
            assert "win_rate" in stats
            assert "avg_return" in stats
            assert "sample_count" in stats
            assert 0 <= stats["win_rate"] <= 100

    def test_week_of_month_patterns(self):
        df = make_test_df(200)
        result = analyze_time_patterns(df)

        assert "week_of_month" in result
        wom = result["week_of_month"]
        valid_labels = {"월초(1-10일)", "월중(11-20일)", "월말(21-31일)"}
        assert set(wom.keys()).issubset(valid_labels)
        for label, stats in wom.items():
            assert "win_rate" in stats
            assert "avg_return" in stats
            assert "sample_count" in stats

    def test_summary_structure(self):
        df = make_test_df(200)
        result = analyze_time_patterns(df)

        summary = result["summary"]
        assert "best_day" in summary
        assert "worst_day" in summary
        assert "total_days" in summary
        assert "overall_win_rate" in summary
        assert summary["total_days"] > 0
        assert 0 <= summary["overall_win_rate"] <= 100
        # best/worst strings contain a day and a percentage
        assert "승률" in summary["best_day"]
        assert "승률" in summary["worst_day"]

    def test_streaks_structure(self):
        df = make_test_df(500)
        result = analyze_time_patterns(df)

        streaks = result["streaks"]
        # With 500 data points we should have some streak patterns
        for key, stats in streaks.items():
            assert "reversal_rate" in stats
            assert "continuation_rate" in stats
            assert "avg_next_return" in stats
            assert "sample_count" in stats
            # reversal_rate + continuation_rate should sum to 100%
            assert abs(stats["reversal_rate"] + stats["continuation_rate"] - 100) < 0.2

    def test_empty_dataframe_returns_empty_dict(self):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = analyze_time_patterns(df)
        assert result == {}

    def test_small_dataframe_below_threshold(self):
        df = make_test_df(20)
        result = analyze_time_patterns(df)
        assert result == {}

    def test_exactly_30_rows(self):
        """30 rows is the threshold; should still work."""
        df = make_test_df(30)
        result = analyze_time_patterns(df)
        assert isinstance(result, dict)
        # May or may not have full data depending on grouping, but should not error
        assert "day_of_week" in result

    def test_with_sample_ohlcv_fixture(self, sample_ohlcv):
        """Test using the shared conftest fixture (500 rows)."""
        result = analyze_time_patterns(sample_ohlcv)
        assert "day_of_week" in result
        assert "monthly" in result
        assert "summary" in result
        assert result["summary"]["total_days"] > 400


class TestComputeStreaks:
    """Tests for the internal _compute_streaks helper."""

    def test_simple_alternating(self):
        up = pd.Series([True, False, True, False])
        streaks = _compute_streaks(up)
        # Each element is its own streak of length 1
        assert len(streaks) == 4

    def test_all_up(self):
        up = pd.Series([True, True, True, True])
        streaks = _compute_streaks(up)
        assert len(streaks) == 1
        assert streaks[0] == (3, 4)  # ends at index 3, length 4 up

    def test_all_down(self):
        up = pd.Series([False, False, False])
        streaks = _compute_streaks(up)
        assert len(streaks) == 1
        assert streaks[0] == (2, -3)  # ends at index 2, length 3 down

    def test_empty_series(self):
        up = pd.Series([], dtype=bool)
        streaks = _compute_streaks(up)
        assert streaks == []


class TestCurrentStreak:
    """Tests for _current_streak helper in fact_sheet module."""

    def test_uptrend(self):
        close = pd.Series([100, 101, 102, 103, 104])
        streak = _current_streak(close)
        assert streak > 0

    def test_downtrend(self):
        close = pd.Series([100, 99, 98, 97, 96])
        streak = _current_streak(close)
        assert streak < 0

    def test_single_value(self):
        close = pd.Series([100])
        streak = _current_streak(close)
        assert streak == 0

    def test_two_values_up(self):
        close = pd.Series([100, 105])
        streak = _current_streak(close)
        assert streak == 1

    def test_two_values_down(self):
        close = pd.Series([105, 100])
        streak = _current_streak(close)
        assert streak == -1


# ── Indicator Combos ────────────────────────────────────────────────


class TestIndicatorAccuracy:
    """Tests for analyze_indicator_accuracy with mocked signal registry."""

    def _mock_registry(self, df):
        """Set up mock signal generators that return deterministic signals."""
        entry_a, exit_a = _make_mock_signal_generator(df, buy_every=8, sell_every=12)
        entry_b, exit_b = _make_mock_signal_generator(df, buy_every=5, sell_every=10)

        def gen_a(data, **kwargs):
            return entry_a, exit_a

        def gen_b(data, **kwargs):
            return entry_b, exit_b

        return {
            "mock_sma_cross": gen_a,
            "mock_rsi_oversold": gen_b,
        }

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_returns_expected_keys(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        result = analyze_indicator_accuracy(df, top_n=10)

        assert "indicators" in result
        assert "ranking_overall" in result
        assert "best_for_up_days" in result
        assert "best_for_down_days" in result

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_ranking_entry_structure(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        result = analyze_indicator_accuracy(df, top_n=10)

        for entry in result["ranking_overall"]:
            assert "name" in entry
            assert "buy_accuracy" in entry
            assert "sell_accuracy" in entry
            assert "combined_accuracy" in entry
            assert 0 <= entry["buy_accuracy"] <= 100
            assert 0 <= entry["sell_accuracy"] <= 100

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_indicator_stats_detail(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        result = analyze_indicator_accuracy(df, top_n=10)

        for name, stats in result["indicators"].items():
            assert "buy_accuracy" in stats
            assert "sell_accuracy" in stats
            assert "combined_accuracy" in stats
            assert "avg_return_on_buy" in stats
            assert "buy_signal_count" in stats
            assert "sell_signal_count" in stats
            assert stats["buy_signal_count"] > 0

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_top_n_limits_ranking(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        result = analyze_indicator_accuracy(df, top_n=1)

        assert len(result["ranking_overall"]) <= 1

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = analyze_indicator_accuracy(df)
        assert result == {}

    def test_short_dataframe(self):
        df = make_test_df(50)
        result = analyze_indicator_accuracy(df)
        assert result == {}

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_generator_that_raises_is_skipped(self, mock_get, mock_list):
        df = make_test_df(200)
        mock_list.return_value = ["bad_signal"]
        mock_get.return_value = lambda data, **kw: (_ for _ in ()).throw(RuntimeError("boom"))

        result = analyze_indicator_accuracy(df)
        assert result == {}


class TestFindBestCombos:
    """Tests for find_best_combos with mocked signal registry."""

    def _mock_registry(self, df):
        entry_a, exit_a = _make_mock_signal_generator(df, buy_every=5, sell_every=10)
        entry_b, exit_b = _make_mock_signal_generator(df, buy_every=7, sell_every=14)
        entry_c, exit_c = _make_mock_signal_generator(df, buy_every=3, sell_every=9)

        return {
            "sig_alpha": lambda data, **kw: (entry_a, exit_a),
            "sig_beta": lambda data, **kw: (entry_b, exit_b),
            "sig_gamma": lambda data, **kw: (entry_c, exit_c),
        }

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_returns_list_of_combos(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        combos = find_best_combos(df, top_n=5)

        assert isinstance(combos, list)
        # With 3 generators we can have at most C(3,2)=3 combos
        assert len(combos) <= 5

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_combo_entry_structure(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        combos = find_best_combos(df, top_n=5)

        for combo in combos:
            assert "combo" in combo
            assert isinstance(combo["combo"], list)
            assert len(combo["combo"]) == 2
            assert "accuracy" in combo
            assert "avg_return" in combo
            assert "signal_count" in combo
            assert combo["signal_count"] >= 3

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_combos_sorted_by_accuracy_descending(self, mock_get, mock_list):
        df = make_test_df(200)
        generators = self._mock_registry(df)
        mock_list.return_value = list(generators.keys())
        mock_get.side_effect = lambda name: generators[name]

        combos = find_best_combos(df, top_n=5)

        if len(combos) >= 2:
            for i in range(len(combos) - 1):
                assert combos[i]["accuracy"] >= combos[i + 1]["accuracy"]

    def test_empty_dataframe(self):
        combos = find_best_combos(pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))
        assert combos == []

    def test_short_dataframe(self):
        combos = find_best_combos(make_test_df(50))
        assert combos == []

    @patch("app.analysis.features.indicator_combos.list_signal_generators")
    @patch("app.analysis.features.indicator_combos.get_signal_generator")
    def test_single_generator_returns_empty(self, mock_get, mock_list):
        """Need at least 2 generators to form a combo."""
        df = make_test_df(200)
        entry, exit_ = _make_mock_signal_generator(df, buy_every=5, sell_every=10)
        mock_list.return_value = ["only_one"]
        mock_get.return_value = lambda data, **kw: (entry, exit_)

        combos = find_best_combos(df)
        assert combos == []


# ── Fact Sheet ──────────────────────────────────────────────────────


class TestGenerateFactSheet:
    """Tests for generate_fact_sheet with mocked dependencies."""

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_generates_non_empty_string(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {}
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930", "삼성전자")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_includes_stock_name_and_code(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {}
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930", "삼성전자")
        assert "005930" in result
        assert "삼성전자" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_includes_current_price_info(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {}
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930", "삼성전자")
        assert "종가" in result
        assert "거래량" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_includes_return_periods(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {}
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930")
        assert "5일 수익률" in result
        assert "20일 수익률" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_includes_fact_sheet_header(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {}
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930", "삼성전자")
        assert "팩트시트" in result
        assert "분석일" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_code_only_label_when_no_name(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {}
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930", stock_name=None)
        assert "005930" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns")
    def test_time_patterns_section_included(self, mock_tp, mock_ia, mock_combos):
        mock_tp.return_value = {
            "day_of_week": {
                "월": {"win_rate": 55.0, "avg_return": 0.05, "sample_count": 40},
            },
            "summary": {
                "best_day": "월 (승률 55.0%)",
                "worst_day": "금 (승률 45.0%)",
                "total_days": 200,
                "overall_win_rate": 51.0,
            },
            "streaks": {},
        }
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930", "삼성전자")
        assert "시간 패턴" in result
        assert "전체 승률" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy")
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns", return_value={})
    def test_indicator_accuracy_section_included(self, mock_tp, mock_ia, mock_combos):
        mock_ia.return_value = {
            "ranking_overall": [
                {
                    "name": "sma_cross",
                    "buy_accuracy": 60.0,
                    "sell_accuracy": 55.0,
                    "combined_accuracy": 57.5,
                }
            ],
        }
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930")
        assert "지표 적중률" in result
        assert "sma_cross" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns", return_value={})
    def test_current_signals_section(self, mock_tp, mock_ia, mock_combos):
        df = make_test_df(200)
        current_signals = {
            "rsi_oversold": {"signal": "buy", "accuracy": 62.5},
            "macd_cross": {"signal": "sell", "accuracy": 58.0},
            "sma_cross": {"signal": "none", "accuracy": 50.0},
        }
        result = generate_fact_sheet(df, "005930", current_signals=current_signals)
        assert "활성 시그널" in result
        assert "매수" in result
        assert "매도" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos")
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns", return_value={})
    def test_best_combos_section(self, mock_tp, mock_ia, mock_combos):
        mock_combos.return_value = [
            {
                "combo": ["sma_cross", "rsi_oversold"],
                "accuracy": 72.5,
                "avg_return": 0.150,
                "signal_count": 12,
            }
        ]
        df = make_test_df(200)
        result = generate_fact_sheet(df, "005930")
        assert "최고 지표 조합" in result
        assert "sma_cross" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns", return_value={})
    def test_macro_data_section(self, mock_tp, mock_ia, mock_combos):
        df = make_test_df(200)
        macro_data = {
            "correlations": {"USD/KRW": 0.45},
            "strongest": [
                {
                    "name": "USD/KRW",
                    "correlation": 0.45,
                    "lead_correlation": 0.12,
                    "win_rate_on_macro_up": 58.0,
                }
            ],
        }
        result = generate_fact_sheet(df, "005930", macro_data=macro_data)
        assert "매크로 상관관계" in result
        assert "USD/KRW" in result

    @patch("app.analysis.features.fact_sheet.find_best_combos", return_value=[])
    @patch("app.analysis.features.fact_sheet.analyze_indicator_accuracy", return_value={})
    @patch("app.analysis.features.fact_sheet.analyze_time_patterns", return_value={})
    def test_empty_dataframe(self, mock_tp, mock_ia, mock_combos):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = generate_fact_sheet(df, "005930")
        # Should still return a string (with header at minimum), not crash
        assert isinstance(result, str)
        assert "005930" in result


class TestGetCurrentSignals:
    """Tests for get_current_signals with mocked signal registry.

    Note: get_current_signals imports list_signal_generators and
    get_signal_generator locally inside the function body, so we must
    patch them on the registry module (the source), not on fact_sheet.
    """

    @patch("app.analysis.signals.registry.list_signal_generators")
    @patch("app.analysis.signals.registry.get_signal_generator")
    def test_returns_dict_with_signal_info(self, mock_get, mock_list):
        df = make_test_df(200)
        entry = pd.Series(False, index=df.index)
        exit_ = pd.Series(False, index=df.index)
        entry.iloc[-1] = True  # Last row has a buy signal

        mock_list.return_value = ["test_indicator"]
        mock_get.return_value = lambda data: (entry, exit_)

        result = get_current_signals(df)

        assert isinstance(result, dict)
        assert "test_indicator" in result
        assert result["test_indicator"]["signal"] == "buy"
        assert "accuracy" in result["test_indicator"]

    @patch("app.analysis.signals.registry.list_signal_generators")
    @patch("app.analysis.signals.registry.get_signal_generator")
    def test_sell_signal_detected(self, mock_get, mock_list):
        df = make_test_df(200)
        entry = pd.Series(False, index=df.index)
        exit_ = pd.Series(False, index=df.index)
        exit_.iloc[-1] = True  # Last row has a sell signal

        mock_list.return_value = ["test_indicator"]
        mock_get.return_value = lambda data: (entry, exit_)

        result = get_current_signals(df)
        assert result["test_indicator"]["signal"] == "sell"

    @patch("app.analysis.signals.registry.list_signal_generators")
    @patch("app.analysis.signals.registry.get_signal_generator")
    def test_no_signal(self, mock_get, mock_list):
        df = make_test_df(200)
        entry = pd.Series(False, index=df.index)
        exit_ = pd.Series(False, index=df.index)

        mock_list.return_value = ["test_indicator"]
        mock_get.return_value = lambda data: (entry, exit_)

        result = get_current_signals(df)
        assert result["test_indicator"]["signal"] == "none"

    @patch("app.analysis.signals.registry.list_signal_generators")
    @patch("app.analysis.signals.registry.get_signal_generator")
    def test_failing_generator_skipped_gracefully(self, mock_get, mock_list):
        df = make_test_df(200)
        mock_list.return_value = ["bad_indicator"]
        mock_get.return_value = lambda data: (_ for _ in ()).throw(RuntimeError("fail"))

        result = get_current_signals(df)
        # Should not crash, bad indicator simply not in results
        assert "bad_indicator" not in result

    @patch("app.analysis.signals.registry.list_signal_generators")
    @patch("app.analysis.signals.registry.get_signal_generator")
    def test_accuracy_calculation(self, mock_get, mock_list):
        df = make_test_df(200)
        # Create entry signals at regular intervals so accuracy can be computed
        entry = pd.Series(False, index=df.index)
        exit_ = pd.Series(False, index=df.index)
        for i in range(0, len(df) - 1, 10):
            entry.iloc[i] = True

        mock_list.return_value = ["periodic_sig"]
        mock_get.return_value = lambda data: (entry, exit_)

        result = get_current_signals(df)
        assert "periodic_sig" in result
        # Accuracy should be a number (computed from >= 3 buy signals)
        assert isinstance(result["periodic_sig"]["accuracy"], float)


# ── AI Analyst (_parse_ai_response) ─────────────────────────────────


class TestParseAiResponse:
    """Tests for _parse_ai_response parsing logic."""

    def test_parse_full_response(self):
        text = (
            "1. 종합 판단: 매수\n"
            "2. 확신도: 7\n"
            "3. 핵심 근거:\n"
            "   - RSI가 과매도 구간 진입\n"
            "   - 20일 이동평균 지지\n"
            "   - 거래량 증가 추세\n"
            "4. 리스크 요인:\n"
            "   - 미중 무역 갈등 심화 가능성\n"
            "   - 환율 변동성 확대\n"
            "5. 뉴스 감성: 긍정\n"
            "6. 추천 진입가: 70,000원 / 손절가: 67,000원 / 목표가: 75,000원\n"
        )
        result = _parse_ai_response(text)

        assert result["decision"] == "매수"
        assert result["confidence"] == 7
        assert len(result["reasoning"]) > 0
        assert len(result["risks"]) > 0
        assert result["news_sentiment"] == "긍정"

    def test_parse_sell_decision(self):
        text = "1. 종합 판단: 매도\n2. 확신도: 8\n5. 뉴스 감성: 부정"
        result = _parse_ai_response(text)
        assert result["decision"] == "매도"
        assert result["confidence"] == 8
        assert result["news_sentiment"] == "부정"

    def test_parse_hold_decision(self):
        text = "1. 종합 판단: 관망\n2. 확신도: 3\n5. 뉴스 감성: 중립"
        result = _parse_ai_response(text)
        assert result["decision"] == "관망"
        assert result["confidence"] == 3
        assert result["news_sentiment"] == "중립"

    def test_empty_string_returns_defaults(self):
        result = _parse_ai_response("")
        assert result["decision"] == "관망"
        assert result["confidence"] == 5
        assert result["news_sentiment"] == "중립"
        assert isinstance(result["price_targets"], dict)

    def test_malformed_response_returns_defaults(self):
        result = _parse_ai_response("이것은 형식에 맞지 않는 응답입니다. 아무 구조 없이 텍스트만 있습니다.")
        assert result["decision"] == "관망"
        assert result["confidence"] == 5
        # reasoning should fall back to using the raw text
        assert len(result["reasoning"]) > 0

    def test_reasoning_fallback_to_raw_text(self):
        text = "Random thoughts about the market without structure."
        result = _parse_ai_response(text)
        # When no structured reasoning found, full text is used
        assert result["reasoning"] == text

    def test_confidence_boundary_values(self):
        text = "확신도: 1"
        result = _parse_ai_response(text)
        assert result["confidence"] == 1

        text = "확신도: 10"
        result = _parse_ai_response(text)
        assert result["confidence"] == 10

    def test_confidence_out_of_range_ignored(self):
        text = "확신도: 15"
        result = _parse_ai_response(text)
        # 15 is out of 1-10 range, so default should remain
        assert result["confidence"] == 5

    def test_parse_combined_decision_keyword(self):
        """종합판단 (no space) should also be recognized."""
        text = "종합판단: 매수"
        result = _parse_ai_response(text)
        assert result["decision"] == "매수"

    def test_all_default_fields_present(self):
        result = _parse_ai_response("")
        assert "decision" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "risks" in result
        assert "news_sentiment" in result
        assert "price_targets" in result

    def test_negative_sentiment(self):
        text = "5. 뉴스 감성: 부정"
        result = _parse_ai_response(text)
        assert result["news_sentiment"] == "부정"

    def test_neutral_sentiment_default(self):
        text = "5. 뉴스 감성: 혼조"
        result = _parse_ai_response(text)
        # Neither 긍정 nor 부정, so defaults to 중립
        assert result["news_sentiment"] == "중립"

    def test_multiline_reasoning_captured(self):
        """The parser scans for any line containing '근거' and captures up to 4
        lines from that point (excluding lines with 리스크/뉴스 감성/추천).
        Because '근거' appears in sub-lines too, the last match wins."""
        text = (
            "3. 핵심 근거:\n"
            "   - RSI 과매도 진입\n"
            "   - 이동평균 지지\n"
            "   - 거래량 증가\n"
            "4. 리스크 요인:\n"
            "   - 리스크 1\n"
        )
        result = _parse_ai_response(text)
        # The first "근거" match captures the header + next 3 detail lines
        assert "핵심 근거" in result["reasoning"]
        assert "RSI" in result["reasoning"]

    def test_multiline_risks_captured(self):
        text = (
            "4. 리스크 요인:\n"
            "   - 환율 리스크\n"
            "   - 금리 인상 우려\n"
            "5. 뉴스 감성: 중립\n"
        )
        result = _parse_ai_response(text)
        assert "환율 리스크" in result["risks"]
