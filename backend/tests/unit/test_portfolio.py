"""Tests for multi-strategy portfolio analysis: aggregator, correlation, attribution."""

import pytest
import numpy as np

from app.analysis.portfolio.aggregator import (
    PortfolioAggregator,
    StrategyExposure,
    AggregationResult,
    _calculate_hhi,
)
from app.analysis.portfolio.correlation import StrategyCorrelation, CorrelationResult
from app.analysis.portfolio.attribution import PerformanceAttribution, AttributionResult


# ── Helpers ──────────────────────────────────────────────────


def _exp(sid, name, stock, qty, value, side="long"):
    return StrategyExposure(
        strategy_id=sid, strategy_name=name,
        stock_code=stock, quantity=qty, value=value, side=side,
    )


# ── PortfolioAggregator tests ───────────────────────────────


class TestPortfolioAggregator:
    def test_empty_positions(self):
        result = PortfolioAggregator.aggregate([])
        assert result.total_exposure == 0
        assert result.hhi == 0
        assert result.conflicts == []

    def test_single_position(self):
        positions = [_exp("s1", "SMA", "005930", 100, 5_000_000)]
        result = PortfolioAggregator.aggregate(positions)
        assert result.total_exposure == 5_000_000
        assert result.net_exposure == 5_000_000
        assert result.long_exposure == 5_000_000
        assert result.short_exposure == 0
        assert result.hhi == 10000  # Single stock = max concentration

    def test_multiple_stocks_diversified(self):
        positions = [
            _exp("s1", "SMA", "005930", 100, 2_500_000),
            _exp("s1", "SMA", "035420", 50, 2_500_000),
            _exp("s2", "RSI", "000660", 80, 2_500_000),
            _exp("s2", "RSI", "051910", 40, 2_500_000),
        ]
        result = PortfolioAggregator.aggregate(positions, total_capital=20_000_000)
        assert result.total_exposure == 10_000_000
        # 4 equal positions → HHI = 4 * (25)^2 = 2500
        assert result.hhi == pytest.approx(2500, abs=1)
        assert len(result.stock_exposures) == 4
        assert result.warnings == []  # HHI=2500 is exactly at threshold

    def test_conflict_detection(self):
        positions = [
            _exp("s1", "Trend", "005930", 100, 5_000_000, "long"),
            _exp("s2", "Reversal", "005930", 50, 2_500_000, "short"),
        ]
        result = PortfolioAggregator.aggregate(positions)
        assert len(result.conflicts) == 1
        assert result.conflicts[0]["stock_code"] == "005930"
        assert "s1" in result.conflicts[0]["long_strategies"]
        assert "s2" in result.conflicts[0]["short_strategies"]

    def test_high_concentration_warning(self):
        positions = [_exp("s1", "SMA", "005930", 100, 9_000_000)]
        result = PortfolioAggregator.aggregate(positions, total_capital=10_000_000)
        assert result.hhi == 10000
        assert any("concentration" in w.lower() for w in result.warnings)

    def test_exposure_exceeds_capital_warning(self):
        positions = [
            _exp("s1", "SMA", "005930", 100, 5_000_000),
            _exp("s2", "RSI", "035420", 100, 5_000_000),
        ]
        result = PortfolioAggregator.aggregate(positions, total_capital=10_000_000)
        assert any("80%" in w for w in result.warnings)

    def test_strategy_exposure_totals(self):
        positions = [
            _exp("s1", "SMA", "005930", 100, 3_000_000),
            _exp("s1", "SMA", "035420", 50, 2_000_000),
            _exp("s2", "RSI", "000660", 80, 4_000_000),
        ]
        result = PortfolioAggregator.aggregate(positions)
        assert result.strategy_exposures["s1"] == 5_000_000
        assert result.strategy_exposures["s2"] == 4_000_000


class TestHHI:
    def test_single_stock_max(self):
        assert _calculate_hhi({"A": 1000}, 1000) == 10000

    def test_equal_two_stocks(self):
        assert _calculate_hhi({"A": 500, "B": 500}, 1000) == pytest.approx(5000, abs=1)

    def test_zero_exposure(self):
        assert _calculate_hhi({}, 0) == 0


# ── StrategyCorrelation tests ────────────────────────────────


class TestStrategyCorrelation:
    def test_single_strategy(self):
        result = StrategyCorrelation.compute({
            "s1": {"name": "SMA", "returns": [0.01, 0.02, -0.01]},
        })
        assert len(result.strategy_ids) == 1
        assert result.diversification_ratio == 1.0
        assert result.max_pair is None

    def test_perfectly_correlated(self):
        returns = [0.01, 0.02, -0.01, 0.03, -0.02]
        result = StrategyCorrelation.compute({
            "s1": {"name": "SMA", "returns": returns},
            "s2": {"name": "SMA_copy", "returns": returns},
        })
        assert result.correlation_matrix[0][1] == pytest.approx(1.0, abs=0.01)
        assert result.avg_correlation == pytest.approx(1.0, abs=0.01)

    def test_negatively_correlated(self):
        returns_a = [0.01, 0.02, -0.01, 0.03, -0.02]
        returns_b = [-0.01, -0.02, 0.01, -0.03, 0.02]
        result = StrategyCorrelation.compute({
            "s1": {"name": "Trend", "returns": returns_a},
            "s2": {"name": "MeanRev", "returns": returns_b},
        })
        assert result.correlation_matrix[0][1] == pytest.approx(-1.0, abs=0.01)
        # Perfectly negatively correlated equal-weight returns cancel to zero portfolio vol
        # so diversification_ratio → infinity, capped to 1.0 by our fallback
        assert result.diversification_ratio >= 1.0

    def test_uncorrelated(self):
        np.random.seed(42)
        n = 500
        result = StrategyCorrelation.compute({
            "s1": {"name": "A", "returns": np.random.randn(n).tolist()},
            "s2": {"name": "B", "returns": np.random.randn(n).tolist()},
        })
        assert abs(result.avg_correlation) < 0.15  # Nearly zero for large N

    def test_three_strategies(self):
        np.random.seed(123)
        result = StrategyCorrelation.compute({
            "s1": {"name": "A", "returns": np.random.randn(100).tolist()},
            "s2": {"name": "B", "returns": np.random.randn(100).tolist()},
            "s3": {"name": "C", "returns": np.random.randn(100).tolist()},
        })
        assert len(result.correlation_matrix) == 3
        assert len(result.correlation_matrix[0]) == 3
        assert result.max_pair is not None
        assert result.min_pair is not None

    def test_max_min_pair_identified(self):
        result = StrategyCorrelation.compute({
            "s1": {"name": "A", "returns": [1, 2, 3, 4, 5]},
            "s2": {"name": "B", "returns": [1, 2, 3, 4, 5]},
            "s3": {"name": "C", "returns": [5, 4, 3, 2, 1]},
        })
        # s1 and s2 perfectly correlated, s3 negatively with both
        assert result.max_pair[2] == pytest.approx(1.0, abs=0.01)
        assert result.min_pair[2] == pytest.approx(-1.0, abs=0.01)


# ── PerformanceAttribution tests ──────────────────────────────


class TestPerformanceAttribution:
    def test_empty_trades(self):
        result = PerformanceAttribution.compute([])
        assert result.total_pnl == 0
        assert result.by_strategy == []
        assert result.by_stock == []

    def test_single_strategy(self):
        trades = [
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "005930", "pnl": 100000},
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "035420", "pnl": -50000},
        ]
        result = PerformanceAttribution.compute(trades)
        assert result.total_pnl == 50000
        assert len(result.by_strategy) == 1
        assert result.by_strategy[0].pnl == 50000
        assert result.by_strategy[0].trade_count == 2
        assert result.by_strategy[0].win_count == 1
        assert result.by_strategy[0].loss_count == 1

    def test_multiple_strategies(self):
        trades = [
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "005930", "pnl": 200000},
            {"strategy_id": "s2", "strategy_name": "RSI", "stock_code": "005930", "pnl": -100000},
            {"strategy_id": "s2", "strategy_name": "RSI", "stock_code": "035420", "pnl": -50000},
        ]
        result = PerformanceAttribution.compute(trades)
        assert result.total_pnl == 50000
        assert result.best_strategy.key == "s1"
        assert result.worst_strategy.key == "s2"
        # s1 contributes 200k/50k = 400%, s2 contributes -150k/50k = -300%
        assert result.best_strategy.pnl_pct == pytest.approx(400.0, abs=0.1)

    def test_by_stock_attribution(self):
        trades = [
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "005930", "pnl": 100000},
            {"strategy_id": "s2", "strategy_name": "RSI", "stock_code": "005930", "pnl": 50000},
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "035420", "pnl": -30000},
        ]
        result = PerformanceAttribution.compute(trades)
        stock_005930 = next(s for s in result.by_stock if s.key == "005930")
        assert stock_005930.pnl == 150000
        assert stock_005930.trade_count == 2

    def test_avg_pnl_per_trade(self):
        trades = [
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "005930", "pnl": 100000},
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "035420", "pnl": 200000},
        ]
        result = PerformanceAttribution.compute(trades)
        assert result.by_strategy[0].avg_pnl_per_trade == 150000

    def test_best_worst_stock(self):
        trades = [
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "005930", "pnl": 300000},
            {"strategy_id": "s1", "strategy_name": "SMA", "stock_code": "035420", "pnl": -100000},
        ]
        result = PerformanceAttribution.compute(trades)
        assert result.best_stock.key == "005930"
        assert result.worst_stock.key == "035420"


# ── RiskManager integration with Aggregator ──────────────────


class TestRiskManagerAggregation:
    @pytest.mark.asyncio
    async def test_risk_manager_with_existing_positions(self):
        """Verify risk_manager_node picks up cross-strategy exposure warnings."""
        from app.agents.nodes.risk_manager import risk_manager_node
        import uuid

        state = {
            "messages": [],
            "user_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "market_regime": {"classification": "bull", "confidence": 0.8, "indicators": {}, "timestamp": ""},
            "watchlist": ["005930"],
            "strategy_candidates": [{
                "stock_code": "005930",
                "composite_score": 80,
                "current_price": 70000,
                "backtest_metrics": {
                    "total_return": 0.15, "sharpe_ratio": 1.2,
                    "max_drawdown": -0.08, "win_rate": 55,
                    "profit_factor": 1.5, "total_trades": 30,
                },
                "validation_scores": {},
                "parameters": {},
                "strategy_name": "sma_crossover",
            }],
            "optimization_status": "",
            "risk_assessment": None,
            "pending_orders": [],
            "executed_orders": [],
            "portfolio_snapshot": {"total_balance": 10_000_000},
            "alerts": [],
            "current_agent": "",
            "iteration_count": 0,
            "should_continue": True,
            "error_state": None,
            "pending_approval": False,
            "pending_trades": [],
            "approval_status": None,
            "approval_threshold": 5_000_000,
            "hitl_enabled": False,
            "memory_context": "",
            "execution_config": None,
            "slippage_report": [],
            # Existing positions with high concentration
            "existing_positions": [
                {
                    "strategy_id": "strat-1",
                    "strategy_name": "SMA",
                    "stock_code": "005930",
                    "quantity": 100,
                    "value": 9_000_000,
                },
            ],
        }
        result = await risk_manager_node(state)
        # Should have a concentration warning since HHI=10000
        assert any("concentration" in w.lower() or "HHI" in w for w in result["risk_assessment"]["warnings"])

    @pytest.mark.asyncio
    async def test_risk_manager_without_existing_positions(self):
        """Without existing positions, aggregation is skipped cleanly."""
        from app.agents.nodes.risk_manager import risk_manager_node
        import uuid

        state = {
            "messages": [],
            "user_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "market_regime": {"classification": "bull", "confidence": 0.8, "indicators": {}, "timestamp": ""},
            "watchlist": ["005930"],
            "strategy_candidates": [{
                "stock_code": "005930",
                "composite_score": 80,
                "current_price": 70000,
                "backtest_metrics": {
                    "total_return": 0.15, "sharpe_ratio": 1.2,
                    "max_drawdown": -0.08, "win_rate": 55,
                    "profit_factor": 1.5, "total_trades": 30,
                },
                "validation_scores": {},
                "parameters": {},
                "strategy_name": "sma_crossover",
            }],
            "optimization_status": "",
            "risk_assessment": None,
            "pending_orders": [],
            "executed_orders": [],
            "portfolio_snapshot": {"total_balance": 10_000_000},
            "alerts": [],
            "current_agent": "",
            "iteration_count": 0,
            "should_continue": True,
            "error_state": None,
            "pending_approval": False,
            "pending_trades": [],
            "approval_status": None,
            "approval_threshold": 5_000_000,
            "hitl_enabled": False,
            "memory_context": "",
            "execution_config": None,
            "slippage_report": [],
        }
        result = await risk_manager_node(state)
        assert "approved_trades" in result["risk_assessment"]
        assert "005930" in result["risk_assessment"]["approved_trades"]
