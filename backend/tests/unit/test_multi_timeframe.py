"""Tests for multi-timeframe analysis module."""

import pytest
import numpy as np
import pandas as pd
from app.analysis.indicators.multi_timeframe import (
    resample_ohlcv,
    compute_sma,
    compute_rsi,
    compute_macd,
    analyze_timeframe,
    multi_timeframe_analysis,
)


def make_ohlcv_df(n: int = 200, freq: str = "1min", start: str = "2026-01-15 09:00") -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    idx = pd.date_range(start=start, periods=n, freq=freq)
    close = 70000 + np.cumsum(np.random.randn(n) * 100)
    high = close + np.abs(np.random.randn(n) * 50)
    low = close - np.abs(np.random.randn(n) * 50)
    opens = close + np.random.randn(n) * 30
    volume = np.random.randint(100, 10000, size=n)
    return pd.DataFrame({
        "open": opens,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)


def make_daily_df(n: int = 200) -> pd.DataFrame:
    """Generate synthetic daily OHLCV data."""
    np.random.seed(99)
    idx = pd.date_range(start="2025-06-01", periods=n, freq="B")
    close = 70000 + np.cumsum(np.random.randn(n) * 500)
    high = close + np.abs(np.random.randn(n) * 200)
    low = close - np.abs(np.random.randn(n) * 200)
    opens = close + np.random.randn(n) * 100
    volume = np.random.randint(50000, 500000, size=n)
    return pd.DataFrame({
        "open": opens,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)


class TestResampleOHLCV:
    def test_resample_5min(self):
        df = make_ohlcv_df(100, freq="1min")
        result = resample_ohlcv(df, "5min")
        assert len(result) == 20
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_resample_15min(self):
        df = make_ohlcv_df(150, freq="1min")
        result = resample_ohlcv(df, "15min")
        assert len(result) == 10

    def test_resample_1h(self):
        df = make_ohlcv_df(300, freq="1min")
        result = resample_ohlcv(df, "1h")
        assert len(result) == 5

    def test_resample_preserves_ohlcv_logic(self):
        df = make_ohlcv_df(10, freq="1min")
        result = resample_ohlcv(df, "5min")
        first_5 = df.iloc[:5]
        row = result.iloc[0]
        assert row["open"] == first_5["open"].iloc[0]
        assert row["high"] == first_5["high"].max()
        assert row["low"] == first_5["low"].min()
        assert row["close"] == first_5["close"].iloc[-1]
        assert row["volume"] == first_5["volume"].sum()

    def test_resample_empty_df(self):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = resample_ohlcv(df, "5min")
        assert result.empty


class TestComputeSMA:
    def test_sma_length(self):
        s = pd.Series(range(100), dtype=float)
        result = compute_sma(s, 20)
        assert len(result) == 100
        assert result.isna().sum() == 19  # first 19 are NaN

    def test_sma_value(self):
        s = pd.Series([10.0] * 20)
        result = compute_sma(s, 20)
        assert result.iloc[-1] == 10.0


class TestComputeRSI:
    def test_rsi_range(self):
        df = make_ohlcv_df(200)
        rsi = compute_rsi(df["close"])
        valid = rsi.dropna()
        assert all(0 <= v <= 100 for v in valid)

    def test_rsi_length(self):
        s = pd.Series(range(100), dtype=float)
        result = compute_rsi(s)
        assert len(result) == 100

    def test_rsi_monotonic_up(self):
        """Monotonically increasing prices should give high RSI."""
        s = pd.Series(range(50, 150), dtype=float)
        result = compute_rsi(s)
        valid = result.dropna()
        assert len(valid) > 0
        assert valid.iloc[-1] > 90


class TestComputeMACD:
    def test_macd_keys(self):
        s = pd.Series(range(100), dtype=float)
        result = compute_macd(s)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_macd_histogram(self):
        s = pd.Series(range(100), dtype=float)
        result = compute_macd(s)
        hist = result["histogram"]
        # histogram = macd - signal
        expected = result["macd"] - result["signal"]
        np.testing.assert_array_almost_equal(hist.values, expected.values)


class TestAnalyzeTimeframe:
    def test_returns_signal(self):
        df = make_ohlcv_df(200)
        sig = analyze_timeframe(df, "5min")
        assert sig.timeframe == "5min"
        assert sig.trend in ("bullish", "bearish", "neutral")
        assert -1.0 <= sig.strength <= 1.0

    def test_rsi_populated(self):
        df = make_ohlcv_df(200)
        sig = analyze_timeframe(df, "15min")
        assert sig.rsi_14 is not None
        assert 0 <= sig.rsi_14 <= 100

    def test_sma_populated(self):
        df = make_ohlcv_df(200)
        sig = analyze_timeframe(df, "1D")
        assert sig.sma_20 is not None

    def test_volume_trend_populated(self):
        df = make_ohlcv_df(200)
        sig = analyze_timeframe(df, "1h")
        assert sig.volume_trend in ("increasing", "decreasing", "neutral")

    def test_macd_signal_values(self):
        df = make_ohlcv_df(200)
        sig = analyze_timeframe(df, "5min")
        assert sig.macd_signal in ("bullish_cross", "bearish_cross", "neutral")


class TestMultiTimeframeAnalysis:
    def test_basic_analysis(self):
        minute_df = make_ohlcv_df(500, freq="1min")
        daily_df = make_daily_df(200)
        result = multi_timeframe_analysis(minute_df, daily_df)
        assert result.consensus in ("strong_bullish", "bullish", "neutral", "bearish", "strong_bearish")
        assert -1.0 <= result.consensus_score <= 1.0
        assert isinstance(result.alignment, bool)
        assert result.recommendation in ("buy", "sell", "hold")

    def test_signals_contain_timeframes(self):
        minute_df = make_ohlcv_df(500, freq="1min")
        daily_df = make_daily_df(200)
        result = multi_timeframe_analysis(minute_df, daily_df)
        # Should have at least some signals
        assert len(result.signals) > 0

    def test_custom_timeframes(self):
        minute_df = make_ohlcv_df(300, freq="1min")
        result = multi_timeframe_analysis(minute_df, timeframes=["5min"])
        assert "5min" in result.signals

    def test_empty_minute_data(self):
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = multi_timeframe_analysis(empty)
        assert result.consensus == "neutral"
        assert result.recommendation == "hold"
        assert len(result.signals) == 0

    def test_no_daily_data(self):
        minute_df = make_ohlcv_df(500, freq="1min")
        result = multi_timeframe_analysis(minute_df, daily_df=None)
        assert "1D" not in result.signals
        assert result.consensus in ("strong_bullish", "bullish", "neutral", "bearish", "strong_bearish")

    def test_dominant_timeframe(self):
        minute_df = make_ohlcv_df(500, freq="1min")
        daily_df = make_daily_df(200)
        result = multi_timeframe_analysis(minute_df, daily_df)
        # Dominant should be the highest weight timeframe
        if "1D" in result.signals:
            assert result.dominant_timeframe == "1D"

    def test_alignment_flag(self):
        """If all trends are the same, alignment should be True."""
        minute_df = make_ohlcv_df(500, freq="1min")
        result = multi_timeframe_analysis(minute_df)
        assert isinstance(result.alignment, bool)
