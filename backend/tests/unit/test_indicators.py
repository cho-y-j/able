import pytest
import pandas as pd
import numpy as np

# Import all indicator modules to trigger registration
from app.analysis.indicators import trend, momentum, volatility, volume
from app.analysis.indicators.registry import calculate_indicator, list_indicators, calculate_multiple


class TestIndicatorRegistry:
    def test_indicators_registered(self):
        indicators = list_indicators()
        assert len(indicators) >= 20
        assert "RSI" in indicators
        assert "SMA" in indicators
        assert "MACD" in indicators
        assert "BB" in indicators

    def test_calculate_multiple(self, sample_ohlcv):
        result = calculate_multiple(sample_ohlcv, [
            {"name": "RSI", "params": {"period": 14}},
            {"name": "SMA", "params": {"period": 20}},
        ])
        assert "RSI_14" in result.columns
        assert "SMA_20" in result.columns


class TestTrendIndicators:
    def test_sma(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "SMA", period=20)
        assert "SMA_20" in result.columns
        assert result["SMA_20"].iloc[19:].notna().all()

    def test_ema(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "EMA", period=20)
        assert "EMA_20" in result.columns

    def test_macd(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "MACD")
        assert "MACD_12_26_9" in result.columns
        assert "MACD_signal_12_26_9" in result.columns

    def test_adx(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "ADX")
        assert "ADX_14" in result.columns
        assert "+DI_14" in result.columns

    def test_supertrend(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "SUPERTREND")
        assert "SUPERTREND_10" in result.columns

    def test_ichimoku(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "ICHIMOKU")
        assert "ICHI_tenkan" in result.columns
        assert "ICHI_kijun" in result.columns


class TestMomentumIndicators:
    def test_rsi(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "RSI", period=14)
        assert "RSI_14" in result.columns
        valid = result["RSI_14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_stochastic(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "STOCH")
        assert "STOCH_K_14" in result.columns

    def test_cci(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "CCI")
        assert "CCI_20" in result.columns

    def test_mfi(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "MFI")
        assert "MFI_14" in result.columns


class TestVolatilityIndicators:
    def test_bollinger_bands(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "BB")
        assert "BB_upper_20" in result.columns
        assert "BB_lower_20" in result.columns

    def test_atr(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "ATR")
        assert "ATR_14" in result.columns

    def test_keltner(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "KC")
        assert "KC_upper_20" in result.columns


class TestVolumeIndicators:
    def test_obv(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "OBV")
        assert "OBV" in result.columns

    def test_vwap(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "VWAP")
        assert "VWAP" in result.columns

    def test_cmf(self, sample_ohlcv):
        result = calculate_indicator(sample_ohlcv, "CMF")
        assert "CMF_20" in result.columns
