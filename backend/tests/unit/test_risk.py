"""Tests for risk management: Kelly Criterion, position sizing, and risk limits."""

import pytest
from app.analysis.risk.position_sizing import (
    kelly_criterion,
    calculate_position_size,
    adaptive_position_size,
)
from app.analysis.risk.limits import RiskLimits


class TestKellyCriterion:
    def test_basic_positive_expectancy(self):
        # 60% win rate, avg win 5%, avg loss 3%
        kelly = kelly_criterion(0.6, 0.05, 0.03)
        assert kelly > 0
        assert kelly <= 0.25

    def test_coin_flip_with_edge(self):
        # 50% win rate, 2:1 payoff
        kelly = kelly_criterion(0.5, 0.06, 0.03)
        assert kelly > 0

    def test_losing_strategy_returns_zero(self):
        # 30% win rate, 1:1 payoff = negative expectancy
        kelly = kelly_criterion(0.3, 0.03, 0.03)
        assert kelly == 0

    def test_zero_loss_returns_zero(self):
        kelly = kelly_criterion(0.5, 0.05, 0)
        assert kelly == 0

    def test_zero_win_rate_returns_zero(self):
        kelly = kelly_criterion(0, 0.05, 0.03)
        assert kelly == 0

    def test_half_kelly_cap(self):
        # Very strong strategy should still be capped at 25%
        kelly = kelly_criterion(0.9, 0.10, 0.01)
        assert kelly <= 0.25

    def test_realistic_strategy(self):
        # 55% win rate, 1.5:1 reward/risk
        kelly = kelly_criterion(0.55, 0.045, 0.03)
        assert 0 < kelly < 0.15


class TestCalculatePositionSize:
    def test_basic_calculation(self):
        shares = calculate_position_size(
            total_capital=10_000_000,
            current_price=50000,
            kelly_fraction=0.05,
        )
        # 10M * 5% = 500K / 50K = 10 shares
        assert shares == 10

    def test_respects_max_position(self):
        shares = calculate_position_size(
            total_capital=10_000_000,
            current_price=50000,
            kelly_fraction=0.20,
            max_position_pct=0.10,
        )
        # Should be capped at 10% = 1M / 50K = 20 shares
        assert shares == 20

    def test_zero_price_returns_zero(self):
        shares = calculate_position_size(10_000_000, 0, 0.05)
        assert shares == 0

    def test_zero_capital_returns_zero(self):
        shares = calculate_position_size(0, 50000, 0.05)
        assert shares == 0

    def test_daily_loss_budget_constraint(self):
        shares = calculate_position_size(
            total_capital=10_000_000,
            current_price=50000,
            kelly_fraction=0.10,
            daily_loss_remaining=100_000,  # 100K remaining budget
        )
        # Min of (10M*10% = 1M) and (100K/0.03 = 3.33M) -> 1M / 50K = 20
        assert shares == 20

    def test_tight_daily_loss_budget(self):
        shares = calculate_position_size(
            total_capital=10_000_000,
            current_price=50000,
            kelly_fraction=0.10,
            daily_loss_remaining=10_000,  # Only 10K remaining
        )
        # 10K/0.03 = 333K / 50K = 6 shares
        assert shares == 6


class TestAdaptivePositionSize:
    def test_bull_regime_full_size(self):
        result = adaptive_position_size(
            total_capital=10_000_000,
            current_price=50000,
            strategy_metrics={"win_rate": 60, "profit_factor": 2.0},
            market_regime="bull",
        )
        assert result["shares"] > 0
        assert result["adjustments"]["regime_multiplier"] == 1.0

    def test_crisis_regime_reduced(self):
        result_bull = adaptive_position_size(
            total_capital=10_000_000,
            current_price=50000,
            strategy_metrics={"win_rate": 60, "profit_factor": 2.0},
            market_regime="bull",
        )
        result_crisis = adaptive_position_size(
            total_capital=10_000_000,
            current_price=50000,
            strategy_metrics={"win_rate": 60, "profit_factor": 2.0},
            market_regime="crisis",
        )
        assert result_crisis["shares"] < result_bull["shares"]

    def test_drawdown_reduces_size(self):
        result_normal = adaptive_position_size(
            total_capital=10_000_000,
            current_price=50000,
            strategy_metrics={"win_rate": 60, "profit_factor": 2.0},
            market_regime="bull",
            current_drawdown=0.0,
        )
        result_dd = adaptive_position_size(
            total_capital=10_000_000,
            current_price=50000,
            strategy_metrics={"win_rate": 60, "profit_factor": 2.0},
            market_regime="bull",
            current_drawdown=0.12,
        )
        assert result_dd["shares"] <= result_normal["shares"]

    def test_returns_full_info(self):
        result = adaptive_position_size(
            total_capital=10_000_000,
            current_price=50000,
            strategy_metrics={"win_rate": 60, "profit_factor": 2.0},
            market_regime="sideways",
        )
        assert "shares" in result
        assert "position_value" in result
        assert "kelly_raw" in result
        assert "adjustments" in result


class TestRiskLimits:
    def test_order_passes_all_checks(self):
        limits = RiskLimits(total_capital=10_000_000)
        check = limits.check_order(
            order_value=500_000,
            current_exposure=2_000_000,
            daily_pnl=0,
        )
        assert check["approved"]

    def test_daily_loss_blocks_order(self):
        limits = RiskLimits(total_capital=10_000_000, max_daily_loss_pct=0.03)
        check = limits.check_order(
            order_value=500_000,
            current_exposure=0,
            daily_pnl=-300_000,  # Already lost 3%
        )
        assert not check["approved"]
        assert "Daily loss limit" in check["reason"]

    def test_exposure_limit(self):
        limits = RiskLimits(total_capital=10_000_000, max_total_exposure_pct=0.80)
        check = limits.check_order(
            order_value=2_000_000,
            current_exposure=7_000_000,  # 70% already
            daily_pnl=0,
        )
        # 7M + 2M = 9M > 8M limit, but 1M remaining allowed
        assert check["approved"]
        assert check["max_allowed_value"] <= 1_000_000

    def test_single_position_limit(self):
        limits = RiskLimits(total_capital=10_000_000, max_single_position_pct=0.10)
        check = limits.check_order(
            order_value=1_500_000,
            current_exposure=0,
            daily_pnl=0,
            existing_position_value=800_000,
        )
        # 800K + 1.5M = 2.3M > 1M limit
        assert check["approved"]
        assert check["max_allowed_value"] <= 200_000

    def test_daily_loss_check_normal(self):
        limits = RiskLimits(total_capital=10_000_000)
        check = limits.daily_loss_check(realized_pnl=-50_000, unrealized_pnl=20_000)
        assert not check["breached"]
        assert check["action"] == "NORMAL"

    def test_daily_loss_check_warning(self):
        limits = RiskLimits(total_capital=10_000_000, max_daily_loss_pct=0.03)
        check = limits.daily_loss_check(realized_pnl=-200_000, unrealized_pnl=-50_000)
        assert not check["breached"]
        assert check["action"] == "WARNING"

    def test_daily_loss_check_breached(self):
        limits = RiskLimits(total_capital=10_000_000, max_daily_loss_pct=0.03)
        check = limits.daily_loss_check(realized_pnl=-250_000, unrealized_pnl=-100_000)
        assert check["breached"]
        assert check["action"] == "HALT_TRADING"

    def test_drawdown_normal(self):
        limits = RiskLimits(total_capital=10_000_000)
        check = limits.drawdown_recovery_mode(current_drawdown=0.03)
        assert not check["recovery_mode"]
        assert check["position_scale"] == 1.0

    def test_drawdown_recovery_mode(self):
        limits = RiskLimits(total_capital=10_000_000)
        check = limits.drawdown_recovery_mode(current_drawdown=0.12)
        assert check["recovery_mode"]
        assert check["position_scale"] < 1.0

    def test_drawdown_halt(self):
        limits = RiskLimits(total_capital=10_000_000)
        check = limits.drawdown_recovery_mode(current_drawdown=0.16)
        assert check["action"] == "HALT_TRADING"
        assert check["position_scale"] == 0.0
