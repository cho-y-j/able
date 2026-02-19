"""Tests for intraday analysis service."""

import numpy as np
import pandas as pd
import pytest

from app.services.intraday_analysis import (
    minute_data_to_df,
    extract_minute_factors,
    generate_minute_signals,
    compute_minute_summary,
)


def _make_minute_data(n=60, base_price=50000, with_volume_spike=False):
    """Generate synthetic minute OHLCV data."""
    np.random.seed(42)
    data = []
    price = base_price
    for i in range(n):
        change = np.random.randn() * 50
        o = price
        h = price + abs(np.random.randn() * 30)
        l = price - abs(np.random.randn() * 30)
        c = price + change
        vol = int(np.random.exponential(10000))
        if with_volume_spike and i == n - 1:
            vol = vol * 10  # Volume spike at the end

        hour = 9 + (i // 60)
        minute = i % 60
        time_str = f"{hour:02d}{minute:02d}00"

        data.append({
            "time": time_str,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": vol,
        })
        price = c
    return data


class TestMinuteDataToDf:
    def test_converts_to_df(self):
        data = _make_minute_data(30)
        df = minute_data_to_df(data)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 30
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]

    def test_empty_input(self):
        df = minute_data_to_df([])
        assert df.empty

    def test_sorted_by_time(self):
        # Reverse order input (like KIS returns)
        data = _make_minute_data(20)
        data.reverse()
        df = minute_data_to_df(data)
        times = df["time"].tolist()
        assert times == sorted(times)

    def test_numeric_columns(self):
        data = [{"time": "090000", "open": "50000", "high": "50100",
                 "low": "49900", "close": "50050", "volume": "1000"}]
        df = minute_data_to_df(data)
        assert df["close"].dtype in [np.float64, np.int64]


class TestExtractMinuteFactors:
    def test_extracts_factors(self):
        data = _make_minute_data(60)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        assert isinstance(factors, dict)
        assert len(factors) > 0

    def test_has_key_factors(self):
        data = _make_minute_data(60)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        # Should have at least RSI, MACD, BB, VWAP
        expected = {"rsi_9m", "macd_hist_m", "bb_position_m", "vwap"}
        assert expected.issubset(set(factors.keys()))

    def test_empty_df(self):
        df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        factors = extract_minute_factors(df)
        assert factors == {}

    def test_short_df(self):
        data = _make_minute_data(3)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        assert factors == {}

    def test_no_nan_values(self):
        data = _make_minute_data(60)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        for name, val in factors.items():
            assert not np.isnan(val), f"Factor {name} is NaN"
            assert not np.isinf(val), f"Factor {name} is Inf"

    def test_rsi_range(self):
        data = _make_minute_data(60)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        if "rsi_9m" in factors:
            assert 0 <= factors["rsi_9m"] <= 100

    def test_bb_position_range(self):
        data = _make_minute_data(60)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        if "bb_position_m" in factors:
            assert -1 <= factors["bb_position_m"] <= 2  # Can slightly exceed 0-1

    def test_session_position_range(self):
        data = _make_minute_data(60)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        if "session_position" in factors:
            assert 0 <= factors["session_position"] <= 1

    def test_vwap_computed(self):
        data = _make_minute_data(30)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        if "vwap" in factors:
            assert factors["vwap"] > 0

    def test_volume_spike_detected(self):
        data = _make_minute_data(60, with_volume_spike=True)
        df = minute_data_to_df(data)
        factors = extract_minute_factors(df)
        if "vol_spike_m" in factors:
            assert factors["vol_spike_m"] > 2.0  # Should be elevated


class TestGenerateMinuteSignals:
    def test_generates_signals(self):
        factors = {
            "rsi_9m": 20.0,
            "macd_cross_m": 1.0,
            "bb_position_m": 0.05,
            "vol_spike_m": 5.0,
            "roc_5m": 1.0,
        }
        signals = generate_minute_signals(factors)
        assert len(signals) > 0

    def test_rsi_oversold(self):
        signals = generate_minute_signals({"rsi_9m": 20.0})
        assert any("과매도" in s["name"] for s in signals)
        assert all(s["direction"] == "bullish" for s in signals)

    def test_rsi_overbought(self):
        signals = generate_minute_signals({"rsi_9m": 80.0})
        assert any("과매수" in s["name"] for s in signals)
        assert all(s["direction"] == "bearish" for s in signals)

    def test_macd_golden_cross(self):
        signals = generate_minute_signals({"macd_cross_m": 1.0})
        assert any("골든크로스" in s["name"] for s in signals)

    def test_macd_dead_cross(self):
        signals = generate_minute_signals({"macd_cross_m": -1.0})
        assert any("데드크로스" in s["name"] for s in signals)

    def test_volume_spike(self):
        signals = generate_minute_signals({"vol_spike_m": 5.0, "roc_5m": 2.0})
        assert any("거래량" in s["name"] for s in signals)

    def test_empty_factors(self):
        signals = generate_minute_signals({})
        assert signals == []

    def test_neutral_factors(self):
        # Middle-range factors — no signals
        signals = generate_minute_signals({
            "rsi_9m": 50.0,
            "macd_cross_m": 0.0,
            "bb_position_m": 0.5,
            "vol_spike_m": 1.0,
        })
        assert signals == []

    def test_signal_has_required_fields(self):
        signals = generate_minute_signals({"rsi_9m": 20.0})
        for s in signals:
            assert "name" in s
            assert "direction" in s
            assert "strength" in s
            assert s["direction"] in ("bullish", "bearish", "neutral")
            assert 0 <= s["strength"] <= 1

    def test_vwap_signals(self):
        signals = generate_minute_signals({"vwap_spread_m": 1.5})
        assert any("VWAP" in s["name"] for s in signals)

    def test_stochastic_oversold(self):
        signals = generate_minute_signals({"stoch_k_m": 10.0})
        assert any("스토캐스틱" in s["name"] for s in signals)


class TestComputeMinuteSummary:
    def test_bullish_summary(self):
        signals = [
            {"name": "s1", "direction": "bullish", "strength": 0.8},
            {"name": "s2", "direction": "bullish", "strength": 0.6},
        ]
        summary = compute_minute_summary({}, signals)
        assert summary["sentiment"] > 0
        assert summary["bullish_count"] == 2
        assert summary["bearish_count"] == 0

    def test_bearish_summary(self):
        signals = [
            {"name": "s1", "direction": "bearish", "strength": 0.8},
            {"name": "s2", "direction": "bearish", "strength": 0.6},
        ]
        summary = compute_minute_summary({}, signals)
        assert summary["sentiment"] < 0
        assert summary["bearish_count"] == 2

    def test_neutral_summary(self):
        signals = [
            {"name": "s1", "direction": "bullish", "strength": 0.5},
            {"name": "s2", "direction": "bearish", "strength": 0.5},
        ]
        summary = compute_minute_summary({}, signals)
        assert abs(summary["sentiment"]) < 0.1

    def test_empty_signals(self):
        summary = compute_minute_summary({}, [])
        assert summary["sentiment"] == 0.0
        assert summary["recommendation"] == "관망"

    def test_recommendation_buy(self):
        signals = [{"name": "s1", "direction": "bullish", "strength": 0.9}]
        summary = compute_minute_summary({}, signals)
        assert "매수" in summary["recommendation"]

    def test_recommendation_sell(self):
        signals = [{"name": "s1", "direction": "bearish", "strength": 0.9}]
        summary = compute_minute_summary({}, signals)
        assert "매도" in summary["recommendation"] or "관망" in summary["recommendation"]
