"""Value-at-Risk (VaR) and stress testing for portfolio risk analysis."""

import math
import numpy as np
from dataclasses import dataclass


@dataclass
class VaRResult:
    """Value-at-Risk calculation result."""
    confidence: float  # e.g. 0.95
    horizon_days: int
    var_absolute: float  # KRW amount at risk
    var_pct: float  # Percentage of portfolio
    method: str
    cvar_absolute: float | None = None  # Conditional VaR (Expected Shortfall)
    cvar_pct: float | None = None


@dataclass
class StressScenario:
    """A stress test scenario definition."""
    name: str
    description: str
    shocks: dict[str, float]  # stock_code -> price change pct (e.g. -0.10 = -10%)


@dataclass
class StressResult:
    """Result of a stress test scenario."""
    scenario: str
    portfolio_impact: float  # KRW change
    portfolio_impact_pct: float
    position_impacts: list[dict]  # per-position breakdown


# ── Standard scenarios for Korean market ──

STRESS_SCENARIOS = [
    StressScenario(
        name="market_crash",
        description="Broad market crash (-15% across all positions)",
        shocks={"__all__": -0.15},
    ),
    StressScenario(
        name="sector_rotation",
        description="Tech -20%, Financials +5%, Others -5%",
        shocks={"__tech__": -0.20, "__finance__": 0.05, "__all__": -0.05},
    ),
    StressScenario(
        name="flash_crash",
        description="Sudden 10% drop followed by partial recovery (net -7%)",
        shocks={"__all__": -0.07},
    ),
    StressScenario(
        name="rate_hike",
        description="Interest rate shock: growth stocks -12%, value +3%",
        shocks={"__growth__": -0.12, "__value__": 0.03, "__all__": -0.05},
    ),
    StressScenario(
        name="won_depreciation",
        description="KRW weakens 10%: exporters +8%, importers -8%",
        shocks={"__export__": 0.08, "__import__": -0.08, "__all__": -0.02},
    ),
    StressScenario(
        name="black_swan",
        description="Extreme tail event (-25% all positions)",
        shocks={"__all__": -0.25},
    ),
]


def historical_var(
    returns: np.ndarray,
    portfolio_value: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> VaRResult:
    """Calculate VaR using historical simulation method.

    Args:
        returns: Array of historical daily portfolio returns (e.g. [-0.01, 0.02, ...])
        portfolio_value: Current portfolio value in KRW
        confidence: Confidence level (e.g. 0.95 for 95%)
        horizon_days: Time horizon in days (sqrt-of-time scaled)

    Returns:
        VaRResult with historical VaR
    """
    if len(returns) < 5:
        return VaRResult(
            confidence=confidence,
            horizon_days=horizon_days,
            var_absolute=0.0,
            var_pct=0.0,
            method="historical",
        )

    sorted_returns = np.sort(returns)
    # VaR at the (1 - confidence) percentile
    idx = int(len(sorted_returns) * (1 - confidence))
    idx = max(0, min(idx, len(sorted_returns) - 1))
    var_daily = abs(sorted_returns[idx])

    # Scale to horizon
    var_pct = var_daily * math.sqrt(horizon_days)
    var_abs = portfolio_value * var_pct

    # CVaR (Expected Shortfall): average of losses beyond VaR
    tail_returns = sorted_returns[:idx + 1]
    cvar_pct = abs(np.mean(tail_returns)) * math.sqrt(horizon_days) if len(tail_returns) > 0 else var_pct
    cvar_abs = portfolio_value * cvar_pct

    return VaRResult(
        confidence=confidence,
        horizon_days=horizon_days,
        var_absolute=round(var_abs, 0),
        var_pct=round(var_pct * 100, 2),
        method="historical",
        cvar_absolute=round(cvar_abs, 0),
        cvar_pct=round(cvar_pct * 100, 2),
    )


def parametric_var(
    returns: np.ndarray,
    portfolio_value: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> VaRResult:
    """Calculate VaR using parametric (variance-covariance) method.

    Assumes normal distribution of returns.
    """
    if len(returns) < 5:
        return VaRResult(
            confidence=confidence,
            horizon_days=horizon_days,
            var_absolute=0.0,
            var_pct=0.0,
            method="parametric",
        )

    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)

    # Z-score for confidence level
    z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
    z = z_scores.get(confidence, 1.645)

    var_daily = abs(mu - z * sigma)
    var_pct = var_daily * math.sqrt(horizon_days)
    var_abs = portfolio_value * var_pct

    # CVaR for normal distribution: mu - sigma * phi(z) / (1 - confidence)
    # phi(z) = standard normal pdf at z
    phi_z = (1 / math.sqrt(2 * math.pi)) * math.exp(-z * z / 2)
    cvar_daily = abs(mu - sigma * phi_z / (1 - confidence))
    cvar_pct = cvar_daily * math.sqrt(horizon_days)
    cvar_abs = portfolio_value * cvar_pct

    return VaRResult(
        confidence=confidence,
        horizon_days=horizon_days,
        var_absolute=round(var_abs, 0),
        var_pct=round(var_pct * 100, 2),
        method="parametric",
        cvar_absolute=round(cvar_abs, 0),
        cvar_pct=round(cvar_pct * 100, 2),
    )


def monte_carlo_var(
    returns: np.ndarray,
    portfolio_value: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
    n_simulations: int = 10000,
) -> VaRResult:
    """Calculate VaR using Monte Carlo simulation.

    Simulates future portfolio paths from historical return distribution.
    """
    if len(returns) < 5:
        return VaRResult(
            confidence=confidence,
            horizon_days=horizon_days,
            var_absolute=0.0,
            var_pct=0.0,
            method="monte_carlo",
        )

    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)

    # Simulate horizon-day returns
    rng = np.random.default_rng(42)
    sim_daily = rng.normal(mu, sigma, size=(n_simulations, horizon_days))
    sim_cumulative = np.sum(sim_daily, axis=1)

    # Sort simulated returns
    sorted_sim = np.sort(sim_cumulative)
    idx = int(n_simulations * (1 - confidence))
    var_pct = abs(sorted_sim[idx])
    var_abs = portfolio_value * var_pct

    # CVaR
    tail = sorted_sim[:idx + 1]
    cvar_pct = abs(np.mean(tail)) if len(tail) > 0 else var_pct
    cvar_abs = portfolio_value * cvar_pct

    return VaRResult(
        confidence=confidence,
        horizon_days=horizon_days,
        var_absolute=round(var_abs, 0),
        var_pct=round(var_pct * 100, 2),
        method="monte_carlo",
        cvar_absolute=round(cvar_abs, 0),
        cvar_pct=round(cvar_pct * 100, 2),
    )


def run_stress_test(
    positions: list[dict],
    scenario: StressScenario,
) -> StressResult:
    """Run a stress test scenario against current positions.

    Args:
        positions: List of dicts with stock_code, current_value, sector (optional)
        scenario: StressScenario with shocks

    Returns:
        StressResult with per-position and total impact
    """
    total_value = sum(p.get("current_value", 0) for p in positions)
    if total_value <= 0:
        return StressResult(
            scenario=scenario.name,
            portfolio_impact=0,
            portfolio_impact_pct=0,
            position_impacts=[],
        )

    position_impacts = []
    total_impact = 0.0

    for pos in positions:
        code = pos.get("stock_code", "")
        value = pos.get("current_value", 0)

        # Determine shock: specific stock > sector > __all__
        shock = scenario.shocks.get(code, None)
        if shock is None:
            shock = scenario.shocks.get("__all__", 0)

        impact = value * shock
        total_impact += impact

        position_impacts.append({
            "stock_code": code,
            "current_value": round(value, 0),
            "shock_pct": round(shock * 100, 2),
            "impact": round(impact, 0),
        })

    return StressResult(
        scenario=scenario.name,
        portfolio_impact=round(total_impact, 0),
        portfolio_impact_pct=round(total_impact / total_value * 100, 2) if total_value > 0 else 0,
        position_impacts=position_impacts,
    )


def full_risk_report(
    returns: np.ndarray,
    portfolio_value: float,
    positions: list[dict],
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> dict:
    """Generate comprehensive risk report.

    Returns dict with VaR (3 methods), CVaR, and all stress test results.
    """
    hist = historical_var(returns, portfolio_value, confidence, horizon_days)
    param = parametric_var(returns, portfolio_value, confidence, horizon_days)
    mc = monte_carlo_var(returns, portfolio_value, confidence, horizon_days)

    stress_results = []
    for scenario in STRESS_SCENARIOS:
        result = run_stress_test(positions, scenario)
        stress_results.append({
            "scenario": result.scenario,
            "description": scenario.description,
            "impact": result.portfolio_impact,
            "impact_pct": result.portfolio_impact_pct,
            "positions": result.position_impacts,
        })

    return {
        "portfolio_value": portfolio_value,
        "confidence": confidence,
        "horizon_days": horizon_days,
        "var": {
            "historical": {
                "var": hist.var_absolute,
                "var_pct": hist.var_pct,
                "cvar": hist.cvar_absolute,
                "cvar_pct": hist.cvar_pct,
            },
            "parametric": {
                "var": param.var_absolute,
                "var_pct": param.var_pct,
                "cvar": param.cvar_absolute,
                "cvar_pct": param.cvar_pct,
            },
            "monte_carlo": {
                "var": mc.var_absolute,
                "var_pct": mc.var_pct,
                "cvar": mc.cvar_absolute,
                "cvar_pct": mc.cvar_pct,
            },
        },
        "stress_tests": stress_results,
    }
