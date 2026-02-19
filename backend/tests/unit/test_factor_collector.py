"""Tests for factor collector service — extractors, registry, helpers."""

import math
import numpy as np
import pandas as pd
import pytest

from app.services.factor_collector import (
    _FACTOR_REGISTRY,
    _safe_float,
    extract_technical_factors,
    list_factors,
    list_factors_by_category,
    get_factor_extractor,
    register_factor,
)


def _make_ohlcv(n=60, trend="up"):
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    base = 50000
    if trend == "up":
        closes = base + np.cumsum(np.random.randn(n) * 200 + 50)
    elif trend == "down":
        closes = base + np.cumsum(np.random.randn(n) * 200 - 50)
    else:
        closes = base + np.cumsum(np.random.randn(n) * 200)

    highs = closes + np.abs(np.random.randn(n)) * 300
    lows = closes - np.abs(np.random.randn(n)) * 300
    opens = closes + np.random.randn(n) * 100
    volumes = (np.random.rand(n) * 1_000_000 + 500_000).astype(int)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


class TestSafeFloat:
    def test_normal_value(self):
        assert _safe_float(42.5) == 42.5

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe_float(float("inf")) is None

    def test_neg_inf_returns_none(self):
        assert _safe_float(float("-inf")) is None

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_string_returns_none(self):
        assert _safe_float("abc") is None

    def test_numpy_nan(self):
        assert _safe_float(np.nan) is None

    def test_int_conversion(self):
        assert _safe_float(42) == 42.0


class TestFactorRegistry:
    def test_registry_has_20_plus_factors(self):
        assert len(_FACTOR_REGISTRY) >= 20

    def test_list_factors_returns_catalog(self):
        catalog = list_factors()
        assert len(catalog) >= 20
        for entry in catalog:
            assert "name" in entry
            assert "category" in entry
            assert "description" in entry

    def test_list_factors_by_category(self):
        by_cat = list_factors_by_category()
        assert "momentum" in by_cat
        assert "trend" in by_cat
        assert "volatility" in by_cat
        assert "volume" in by_cat

    def test_get_factor_extractor(self):
        extractor = get_factor_extractor("rsi_14")
        assert callable(extractor)

    def test_get_unknown_factor_raises(self):
        with pytest.raises(ValueError, match="Unknown factor"):
            get_factor_extractor("nonexistent_factor_xyz")


class TestIndividualFactors:
    """Test each factor extractor produces valid float output."""

    @pytest.fixture
    def df(self):
        return _make_ohlcv(60, "up")

    def test_rsi_14(self, df):
        from app.services.factor_collector import rsi_14
        val = rsi_14(df)
        assert 0 <= val <= 100

    def test_macd_histogram(self, df):
        from app.services.factor_collector import macd_histogram
        val = macd_histogram(df)
        assert isinstance(val, float)
        assert not math.isnan(val)

    def test_macd_signal_cross(self, df):
        from app.services.factor_collector import macd_signal_cross
        val = macd_signal_cross(df)
        assert val in (-1.0, 0.0, 1.0)

    def test_bb_position(self, df):
        from app.services.factor_collector import bb_position
        val = bb_position(df)
        assert isinstance(val, float)
        assert not math.isnan(val)

    def test_sma_20_slope(self, df):
        from app.services.factor_collector import sma_20_slope
        val = sma_20_slope(df)
        assert isinstance(val, float)

    def test_sma_50_spread(self, df):
        from app.services.factor_collector import sma_50_spread
        val = sma_50_spread(df)
        assert isinstance(val, float)

    def test_ema_12_26_spread(self, df):
        from app.services.factor_collector import ema_12_26_spread
        val = ema_12_26_spread(df)
        assert isinstance(val, float)

    def test_adx_value(self, df):
        from app.services.factor_collector import adx_value
        val = adx_value(df)
        assert 0 <= val <= 100 or math.isnan(val) is False

    def test_stochastic_k(self, df):
        from app.services.factor_collector import stochastic_k
        val = stochastic_k(df)
        assert 0 <= val <= 100

    def test_cci_value(self, df):
        from app.services.factor_collector import cci_value
        val = cci_value(df)
        assert isinstance(val, float)

    def test_williams_r(self, df):
        from app.services.factor_collector import williams_r
        val = williams_r(df)
        assert -100 <= val <= 0

    def test_mfi_value(self, df):
        from app.services.factor_collector import mfi_value
        val = mfi_value(df)
        assert 0 <= val <= 100

    def test_atr_pct(self, df):
        from app.services.factor_collector import atr_pct
        val = atr_pct(df)
        assert val >= 0

    def test_bb_width(self, df):
        from app.services.factor_collector import bb_width
        val = bb_width(df)
        assert val >= 0

    def test_obv_slope(self, df):
        from app.services.factor_collector import obv_slope
        val = obv_slope(df)
        assert isinstance(val, float)

    def test_rvol_20(self, df):
        from app.services.factor_collector import rvol_20
        val = rvol_20(df)
        assert val >= 0

    def test_volume_ma_ratio(self, df):
        from app.services.factor_collector import volume_ma_ratio
        val = volume_ma_ratio(df)
        assert val >= 0

    def test_roc_10(self, df):
        from app.services.factor_collector import roc_10
        val = roc_10(df)
        assert isinstance(val, float)

    def test_close_vs_high_20(self, df):
        from app.services.factor_collector import close_vs_high_20
        val = close_vs_high_20(df)
        assert 0 < val <= 1.0

    def test_close_vs_low_20(self, df):
        from app.services.factor_collector import close_vs_low_20
        val = close_vs_low_20(df)
        assert val >= 1.0


class TestExtractTechnicalFactors:
    def test_returns_dict_of_floats(self):
        df = _make_ohlcv(60)
        factors = extract_technical_factors(df)
        assert isinstance(factors, dict)
        assert len(factors) >= 15  # Most should succeed
        for k, v in factors.items():
            assert isinstance(k, str)
            assert isinstance(v, float)
            assert not math.isnan(v)
            assert not math.isinf(v)

    def test_short_df_returns_partial(self):
        """Short DataFrame should still return some factors."""
        df = _make_ohlcv(5)
        factors = extract_technical_factors(df)
        # Some factors may fail with insufficient data, but should not crash
        assert isinstance(factors, dict)

    def test_empty_df_handles_gracefully(self):
        """Empty DataFrame should not crash, may return some default values."""
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        factors = extract_technical_factors(df)
        assert isinstance(factors, dict)
        # Should not produce NaN or Inf values
        for name, val in factors.items():
            assert not math.isnan(val), f"Factor {name} returned NaN for empty df"
            assert not math.isinf(val), f"Factor {name} returned Inf for empty df"

    def test_no_nan_values(self):
        df = _make_ohlcv(100)
        factors = extract_technical_factors(df)
        for name, val in factors.items():
            assert not math.isnan(val), f"Factor {name} returned NaN"
            assert not math.isinf(val), f"Factor {name} returned Inf"

    def test_downtrend_data(self):
        df = _make_ohlcv(60, "down")
        factors = extract_technical_factors(df)
        assert len(factors) >= 15
        # RSI should be lower in downtrend
        if "rsi_14" in factors:
            assert factors["rsi_14"] < 70  # should not be overbought in downtrend
