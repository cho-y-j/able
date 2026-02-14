"""Tests for validation schemas and Monte Carlo / OOS / CPCV functions."""

import pytest
import numpy as np
import pandas as pd

from app.schemas.validation import (
    MonteCarloRequest, MonteCarloResponse,
    OOSRequest, OOSResponse,
    CPCVRequest, CPCVResponse,
    StrategyCompareResponse,
)
from app.analysis.validation.monte_carlo import monte_carlo_simulation
from app.analysis.validation.out_of_sample import (
    out_of_sample_test,
    combinatorial_purged_cv,
)


class TestValidationSchemas:
    def test_monte_carlo_request_defaults(self):
        req = MonteCarloRequest()
        assert req.n_simulations == 1000
        assert req.initial_capital == 10_000_000

    def test_monte_carlo_response(self):
        resp = MonteCarloResponse(mc_score=85.5, simulations_run=1000, n_trades=50)
        assert resp.mc_score == 85.5

    def test_oos_request_defaults(self):
        req = OOSRequest()
        assert req.oos_ratio == 0.3
        assert req.data_source == "yahoo"

    def test_cpcv_request_defaults(self):
        req = CPCVRequest()
        assert req.n_splits == 5
        assert req.purge_days == 5

    def test_compare_response(self):
        resp = StrategyCompareResponse(
            strategies=[{"strategy_id": "abc", "name": "test"}],
            ranking=[{"rank": 1, "strategy_id": "abc", "name": "test", "score": 80}],
        )
        assert len(resp.strategies) == 1
        assert resp.ranking[0]["rank"] == 1


class TestMonteCarloSimulation:
    def test_basic_simulation(self):
        np.random.seed(42)
        returns = [2.5, -1.2, 3.1, -0.5, 1.8, -2.0, 0.9, 1.5, -0.8, 2.2]
        result = monte_carlo_simulation(returns, n_simulations=100)

        assert result["mc_score"] > 0
        assert result["simulations_run"] == 100
        assert result["n_trades"] == 10
        assert "statistics" in result
        assert "drawdown_stats" in result
        assert "confidence_bands" in result
        assert "percentiles" in result

    def test_insufficient_trades(self):
        result = monte_carlo_simulation([1.0, 2.0], n_simulations=100)
        assert result["mc_score"] == 0
        assert "Insufficient" in result.get("message", "")

    def test_empty_trades(self):
        result = monte_carlo_simulation([], n_simulations=100)
        assert result["mc_score"] == 0

    def test_profitable_strategy(self):
        np.random.seed(42)
        # Mostly positive returns
        returns = [3.0, 2.0, 1.5, -1.0, 2.5, -0.5, 3.0, 1.0, 2.0, -0.8]
        result = monte_carlo_simulation(returns, n_simulations=500)
        assert result["mc_score"] > 50  # Should be mostly profitable

    def test_losing_strategy(self):
        np.random.seed(42)
        # Mostly negative returns
        returns = [-3.0, -2.0, 0.5, -1.5, -2.5, 0.3, -3.0, -1.0, -2.0, 0.2]
        result = monte_carlo_simulation(returns, n_simulations=500)
        assert result["mc_score"] < 50  # Should be mostly unprofitable

    def test_statistics_keys(self):
        np.random.seed(42)
        returns = [1.0, -0.5, 2.0, -1.0, 1.5, 0.5, -0.3, 1.2, -0.8, 0.7]
        result = monte_carlo_simulation(returns, n_simulations=100)

        stats = result["statistics"]
        assert "mean_return" in stats
        assert "median_return" in stats
        assert "profitable_pct" in stats
        assert "risk_of_ruin_pct" in stats

        dd = result["drawdown_stats"]
        assert "mean_max_dd" in dd
        assert "worst_max_dd" in dd


class TestOutOfSample:
    def test_basic_oos(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = out_of_sample_test(sample_ohlcv, signal_gen, params)
        assert "oos_score" in result
        assert result["oos_score"] >= 0

    def test_oos_has_is_and_oos_sections(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = out_of_sample_test(sample_ohlcv, signal_gen, params)
        if "message" not in result:
            assert "in_sample" in result
            assert "out_of_sample" in result
            assert "degradation" in result

    def test_oos_insufficient_data(self):
        short_df = pd.DataFrame({
            "open": [100] * 20,
            "high": [105] * 20,
            "low": [95] * 20,
            "close": [100] * 20,
            "volume": [1000] * 20,
        }, index=pd.date_range("2024-01-01", periods=20, freq="B"))

        def dummy_sig(df, **kwargs):
            return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

        result = out_of_sample_test(short_df, dummy_sig, {})
        assert result["oos_score"] == 0


class TestCPCV:
    def test_basic_cpcv(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = combinatorial_purged_cv(sample_ohlcv, signal_gen, params, n_splits=3)
        assert "cpcv_score" in result
        assert "folds" in result
        assert result["total_folds"] > 0

    def test_cpcv_fold_details(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("rsi_mean_reversion")
        params = {"period": 14, "oversold": 30, "overbought": 70}

        result = combinatorial_purged_cv(sample_ohlcv, signal_gen, params, n_splits=4)
        for fold in result["folds"]:
            assert "fold" in fold
            assert "sharpe_ratio" in fold
