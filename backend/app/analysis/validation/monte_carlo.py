"""Monte Carlo simulation for strategy robustness testing.

Generates thousands of synthetic equity curves by shuffling trade returns
to assess the probability of observed performance being due to luck.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def monte_carlo_simulation(
    trade_returns: list[float],
    n_simulations: int = 1000,
    initial_capital: float = 10_000_000,
    confidence_levels: tuple[float, ...] = (0.05, 0.25, 0.50, 0.75, 0.95),
) -> dict:
    """Run Monte Carlo simulation by reshuffling trade returns.

    Args:
        trade_returns: List of individual trade return percentages
        n_simulations: Number of simulation runs
        initial_capital: Starting capital
        confidence_levels: Percentile levels for confidence bands

    Returns:
        Dict with simulation statistics, confidence bands, and risk metrics
    """
    if not trade_returns or len(trade_returns) < 5:
        return {
            "mc_score": 0,
            "simulations_run": 0,
            "message": "Insufficient trades for Monte Carlo simulation",
        }

    returns = np.array(trade_returns) / 100  # Convert from percentage
    n_trades = len(returns)

    # Run simulations
    final_equities = np.zeros(n_simulations)
    max_drawdowns = np.zeros(n_simulations)
    equity_paths = np.zeros((n_simulations, n_trades + 1))
    equity_paths[:, 0] = initial_capital

    for sim in range(n_simulations):
        # Shuffle trade order
        shuffled = np.random.permutation(returns)

        # Build equity curve
        equity = initial_capital
        peak = equity
        max_dd = 0

        for i, ret in enumerate(shuffled):
            equity *= (1 + ret)
            equity_paths[sim, i + 1] = equity
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

        final_equities[sim] = equity
        max_drawdowns[sim] = max_dd

    # Calculate statistics
    final_returns = (final_equities / initial_capital - 1) * 100

    # Confidence bands for equity paths
    bands = {}
    for level in confidence_levels:
        bands[f"p{int(level*100)}"] = np.percentile(equity_paths, level * 100, axis=0).tolist()

    # MC Score: probability of being profitable
    profitable_pct = (final_returns > 0).mean() * 100

    # Risk of ruin: probability of losing > 50%
    ruin_pct = (final_returns < -50).mean() * 100

    # Sharpe distribution
    mean_final_return = float(np.mean(final_returns))
    std_final_return = float(np.std(final_returns))

    return {
        "mc_score": round(profitable_pct, 2),
        "simulations_run": n_simulations,
        "n_trades": n_trades,
        "statistics": {
            "mean_return": round(mean_final_return, 2),
            "median_return": round(float(np.median(final_returns)), 2),
            "std_return": round(std_final_return, 2),
            "best_case": round(float(np.max(final_returns)), 2),
            "worst_case": round(float(np.min(final_returns)), 2),
            "profitable_pct": round(profitable_pct, 2),
            "risk_of_ruin_pct": round(ruin_pct, 2),
        },
        "drawdown_stats": {
            "mean_max_dd": round(float(np.mean(max_drawdowns)) * 100, 2),
            "median_max_dd": round(float(np.median(max_drawdowns)) * 100, 2),
            "worst_max_dd": round(float(np.max(max_drawdowns)) * 100, 2),
            "p95_max_dd": round(float(np.percentile(max_drawdowns, 95)) * 100, 2),
        },
        "confidence_bands": bands,
        "percentiles": {
            "p5": round(float(np.percentile(final_returns, 5)), 2),
            "p25": round(float(np.percentile(final_returns, 25)), 2),
            "p50": round(float(np.percentile(final_returns, 50)), 2),
            "p75": round(float(np.percentile(final_returns, 75)), 2),
            "p95": round(float(np.percentile(final_returns, 95)), 2),
        },
    }


def monte_carlo_from_backtest(backtest_result, n_simulations: int = 1000) -> dict:
    """Run Monte Carlo simulation from a BacktestResult object."""
    if not backtest_result.trade_log:
        return {"mc_score": 0, "message": "No trades in backtest result"}

    trade_returns = [t["pnl_percent"] for t in backtest_result.trade_log]
    return monte_carlo_simulation(trade_returns, n_simulations)
