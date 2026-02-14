"""Tests for VaR, CVaR, and stress testing."""

import numpy as np
import pytest

from app.analysis.risk.var import (
    historical_var, parametric_var, monte_carlo_var,
    run_stress_test, full_risk_report,
    StressScenario, STRESS_SCENARIOS, VaRResult,
)


# ── Fixtures ──

@pytest.fixture
def normal_returns():
    """Simulated daily returns: ~0% mean, ~1% daily vol."""
    rng = np.random.default_rng(42)
    return rng.normal(0.0005, 0.015, size=252)


@pytest.fixture
def portfolio_value():
    return 100_000_000  # 100M KRW


@pytest.fixture
def sample_positions():
    return [
        {"stock_code": "005930", "current_value": 40_000_000},
        {"stock_code": "000660", "current_value": 30_000_000},
        {"stock_code": "035420", "current_value": 20_000_000},
        {"stock_code": "051910", "current_value": 10_000_000},
    ]


# ── Historical VaR Tests ──

class TestHistoricalVaR:
    def test_basic_calculation(self, normal_returns, portfolio_value):
        result = historical_var(normal_returns, portfolio_value, confidence=0.95)
        assert isinstance(result, VaRResult)
        assert result.method == "historical"
        assert result.var_absolute > 0
        assert result.var_pct > 0
        assert result.confidence == 0.95
        assert result.horizon_days == 1

    def test_higher_confidence_higher_var(self, normal_returns, portfolio_value):
        var95 = historical_var(normal_returns, portfolio_value, confidence=0.95)
        var99 = historical_var(normal_returns, portfolio_value, confidence=0.99)
        assert var99.var_absolute >= var95.var_absolute

    def test_longer_horizon_higher_var(self, normal_returns, portfolio_value):
        var1d = historical_var(normal_returns, portfolio_value, horizon_days=1)
        var10d = historical_var(normal_returns, portfolio_value, horizon_days=10)
        assert var10d.var_absolute > var1d.var_absolute

    def test_cvar_greater_than_var(self, normal_returns, portfolio_value):
        result = historical_var(normal_returns, portfolio_value)
        assert result.cvar_absolute >= result.var_absolute

    def test_insufficient_data(self, portfolio_value):
        result = historical_var(np.array([0.01, -0.01]), portfolio_value)
        assert result.var_absolute == 0.0

    def test_zero_portfolio(self, normal_returns):
        result = historical_var(normal_returns, 0)
        assert result.var_absolute == 0.0


# ── Parametric VaR Tests ──

class TestParametricVaR:
    def test_basic_calculation(self, normal_returns, portfolio_value):
        result = parametric_var(normal_returns, portfolio_value)
        assert result.method == "parametric"
        assert result.var_absolute > 0
        assert result.var_pct > 0

    def test_higher_confidence(self, normal_returns, portfolio_value):
        var95 = parametric_var(normal_returns, portfolio_value, confidence=0.95)
        var99 = parametric_var(normal_returns, portfolio_value, confidence=0.99)
        assert var99.var_absolute > var95.var_absolute

    def test_cvar_exists(self, normal_returns, portfolio_value):
        result = parametric_var(normal_returns, portfolio_value)
        assert result.cvar_absolute is not None
        assert result.cvar_pct is not None
        assert result.cvar_absolute > 0


# ── Monte Carlo VaR Tests ──

class TestMonteCarloVaR:
    def test_basic_calculation(self, normal_returns, portfolio_value):
        result = monte_carlo_var(normal_returns, portfolio_value, n_simulations=5000)
        assert result.method == "monte_carlo"
        assert result.var_absolute > 0

    def test_reproducible_with_seed(self, normal_returns, portfolio_value):
        r1 = monte_carlo_var(normal_returns, portfolio_value)
        r2 = monte_carlo_var(normal_returns, portfolio_value)
        assert r1.var_absolute == r2.var_absolute

    def test_scales_with_horizon(self, normal_returns, portfolio_value):
        var1 = monte_carlo_var(normal_returns, portfolio_value, horizon_days=1)
        var5 = monte_carlo_var(normal_returns, portfolio_value, horizon_days=5)
        assert var5.var_absolute > var1.var_absolute


# ── Stress Test Tests ──

class TestStressTests:
    def test_market_crash_all_positions_down(self, sample_positions):
        scenario = StressScenario(
            name="crash", description="Test", shocks={"__all__": -0.15}
        )
        result = run_stress_test(sample_positions, scenario)
        total_value = sum(p["current_value"] for p in sample_positions)
        expected = total_value * -0.15
        assert abs(result.portfolio_impact - expected) < 1
        assert result.portfolio_impact_pct == -15.0

    def test_specific_stock_shock(self, sample_positions):
        scenario = StressScenario(
            name="samsung_drop", description="Test",
            shocks={"005930": -0.30, "__all__": 0.0}
        )
        result = run_stress_test(sample_positions, scenario)
        # Only Samsung should be affected: 40M * -30% = -12M
        assert abs(result.portfolio_impact - (-12_000_000)) < 1

    def test_empty_positions(self):
        scenario = StressScenario(name="t", description="t", shocks={"__all__": -0.10})
        result = run_stress_test([], scenario)
        assert result.portfolio_impact == 0
        assert result.portfolio_impact_pct == 0

    def test_per_position_impact(self, sample_positions):
        scenario = StressScenario(name="t", description="t", shocks={"__all__": -0.10})
        result = run_stress_test(sample_positions, scenario)
        assert len(result.position_impacts) == 4
        for pi in result.position_impacts:
            assert pi["shock_pct"] == -10.0
            assert pi["impact"] < 0

    def test_standard_scenarios_exist(self):
        assert len(STRESS_SCENARIOS) >= 6
        names = [s.name for s in STRESS_SCENARIOS]
        assert "market_crash" in names
        assert "black_swan" in names


# ── Full Risk Report Tests ──

class TestFullRiskReport:
    def test_report_structure(self, normal_returns, portfolio_value, sample_positions):
        report = full_risk_report(normal_returns, portfolio_value, sample_positions)
        assert "var" in report
        assert "stress_tests" in report
        assert "historical" in report["var"]
        assert "parametric" in report["var"]
        assert "monte_carlo" in report["var"]
        assert len(report["stress_tests"]) == len(STRESS_SCENARIOS)

    def test_report_values_positive(self, normal_returns, portfolio_value, sample_positions):
        report = full_risk_report(normal_returns, portfolio_value, sample_positions)
        for method in ["historical", "parametric", "monte_carlo"]:
            assert report["var"][method]["var"] > 0
            assert report["var"][method]["cvar"] > 0

    def test_confidence_levels(self, normal_returns, portfolio_value, sample_positions):
        r90 = full_risk_report(normal_returns, portfolio_value, sample_positions, confidence=0.90)
        r99 = full_risk_report(normal_returns, portfolio_value, sample_positions, confidence=0.99)
        assert r99["var"]["historical"]["var"] >= r90["var"]["historical"]["var"]

    def test_stress_worst_case(self, normal_returns, portfolio_value, sample_positions):
        report = full_risk_report(normal_returns, portfolio_value, sample_positions)
        black_swan = next(s for s in report["stress_tests"] if s["scenario"] == "black_swan")
        assert black_swan["impact"] < 0
        assert black_swan["impact_pct"] == -25.0
