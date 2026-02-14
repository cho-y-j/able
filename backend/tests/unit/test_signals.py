"""Tests for the signal generator registry and all registered signal generators."""

import pytest
import pandas as pd
import numpy as np


class TestSignalRegistry:
    """Test the signal registry infrastructure."""

    def test_all_signals_registered(self):
        from app.analysis.signals.registry import list_signal_generators

        signals = list_signal_generators()
        assert len(signals) >= 15, f"Expected >=15 signals, got {len(signals)}: {signals}"

    def test_list_by_category(self):
        from app.analysis.signals.registry import list_signal_generators_by_category

        categories = list_signal_generators_by_category()
        assert "trend" in categories
        assert "momentum" in categories
        assert "volatility" in categories
        assert "composite" in categories

    def test_get_unknown_signal_raises(self):
        from app.analysis.signals.registry import get_signal_generator

        with pytest.raises(ValueError, match="Unknown signal"):
            get_signal_generator("nonexistent_strategy_xyz")

    def test_param_spaces_valid(self):
        from app.analysis.signals.registry import (
            list_signal_generators,
            get_signal_param_space,
        )

        for name in list_signal_generators():
            space = get_signal_param_space(name)
            assert isinstance(space, dict), f"{name}: param_space not a dict"
            assert len(space) > 0, f"{name}: param_space is empty"
            for param_name, spec in space.items():
                assert "type" in spec, f"{name}.{param_name}: missing 'type'"
                if spec["type"] in ("int", "float"):
                    assert "low" in spec, f"{name}.{param_name}: missing 'low'"
                    assert "high" in spec, f"{name}.{param_name}: missing 'high'"
                    assert spec["low"] < spec["high"], (
                        f"{name}.{param_name}: low >= high"
                    )


class TestSignalGeneratorOutputs:
    """Test that every signal generator returns correct output shape."""

    def test_all_generators_return_correct_shape(self, sample_ohlcv):
        from app.analysis.signals.registry import (
            list_signal_generators,
            get_signal_generator,
        )

        for name in list_signal_generators():
            gen = get_signal_generator(name)
            entry, exit_ = gen(sample_ohlcv.copy())
            assert isinstance(entry, pd.Series), f"{name}: entry not Series"
            assert isinstance(exit_, pd.Series), f"{name}: exit not Series"
            assert len(entry) == len(sample_ohlcv), f"{name}: entry length mismatch"
            assert len(exit_) == len(sample_ohlcv), f"{name}: exit length mismatch"
            assert entry.dtype == bool, f"{name}: entry dtype={entry.dtype}, expected bool"
            assert exit_.dtype == bool, f"{name}: exit dtype={exit_.dtype}, expected bool"

    def test_most_generators_produce_signals(self, sample_ohlcv):
        from app.analysis.signals.registry import (
            list_signal_generators,
            get_signal_generator,
        )

        no_signal = []
        for name in list_signal_generators():
            gen = get_signal_generator(name)
            entry, exit_ = gen(sample_ohlcv.copy())
            total_signals = entry.sum() + exit_.sum()
            if total_signals == 0:
                no_signal.append(name)

        # Allow at most 2 generators to produce no signals on synthetic data
        assert len(no_signal) <= 2, (
            f"Too many generators with zero signals: {no_signal}"
        )


class TestTrendSignals:
    """Test specific trend-following signal generators."""

    def test_sma_crossover(self, sample_ohlcv):
        from app.analysis.signals.trend_signals import sma_crossover

        entry, exit_ = sma_crossover(sample_ohlcv.copy(), fast_period=10, slow_period=50)
        assert entry.any()
        assert exit_.any()

    def test_macd_crossover(self, sample_ohlcv):
        from app.analysis.signals.trend_signals import macd_crossover

        entry, exit_ = macd_crossover(sample_ohlcv.copy())
        assert entry.any()

    def test_supertrend(self, sample_ohlcv):
        from app.analysis.signals.trend_signals import supertrend_signal

        # Use lower multiplier for synthetic data (less volatile than real markets)
        entry, exit_ = supertrend_signal(sample_ohlcv.copy(), multiplier=1.5)
        assert entry.any() or exit_.any()

    def test_donchian_breakout(self, sample_ohlcv):
        from app.analysis.signals.trend_signals import donchian_breakout_signal

        entry, exit_ = donchian_breakout_signal(sample_ohlcv.copy())
        assert entry.any()


class TestMomentumSignals:
    """Test momentum signal generators."""

    def test_stochastic_crossover(self, sample_ohlcv):
        from app.analysis.signals.momentum_signals import stochastic_crossover

        entry, exit_ = stochastic_crossover(sample_ohlcv.copy())
        assert entry.any()

    def test_roc_momentum(self, sample_ohlcv):
        from app.analysis.signals.momentum_signals import roc_momentum

        entry, exit_ = roc_momentum(sample_ohlcv.copy())
        assert entry.any()


class TestVolatilitySignals:
    """Test volatility signal generators."""

    def test_keltner_breakout(self, sample_ohlcv):
        from app.analysis.signals.volatility_signals import keltner_breakout

        entry, exit_ = keltner_breakout(sample_ohlcv.copy())
        assert entry.any()

    def test_atr_trailing_stop(self, sample_ohlcv):
        from app.analysis.signals.volatility_signals import atr_trailing_stop

        entry, exit_ = atr_trailing_stop(sample_ohlcv.copy())
        assert entry.any()


class TestCompositeSignals:
    """Test composite signal generators."""

    def test_elder_impulse(self, sample_ohlcv):
        from app.analysis.signals.composite_signals import elder_impulse_signal

        entry, exit_ = elder_impulse_signal(sample_ohlcv.copy())
        assert entry.any()

    def test_multi_ma_vote(self, sample_ohlcv):
        from app.analysis.signals.composite_signals import multi_ma_vote

        entry, exit_ = multi_ma_vote(sample_ohlcv.copy())
        assert entry.any()


class TestBackwardCompatibility:
    """Test that the legacy get_signal_generator still works."""

    def test_legacy_rsi_detection(self):
        from app.analysis.indicators.registry import get_signal_generator

        gen = get_signal_generator({"period": [14], "oversold": [30], "overbought": [70]})
        assert callable(gen)

    def test_legacy_sma_detection(self):
        from app.analysis.indicators.registry import get_signal_generator

        gen = get_signal_generator({"fast_period": [10], "slow_period": [50]})
        assert callable(gen)

    def test_legacy_bb_detection(self):
        from app.analysis.indicators.registry import get_signal_generator

        gen = get_signal_generator({"period": [20], "std_dev": [2.0]})
        assert callable(gen)

    def test_name_based_lookup(self):
        from app.analysis.indicators.registry import get_signal_generator

        gen = get_signal_generator(name="macd_crossover")
        assert callable(gen)

    def test_default_fallback(self):
        from app.analysis.indicators.registry import get_signal_generator

        gen = get_signal_generator(None)
        assert callable(gen)
