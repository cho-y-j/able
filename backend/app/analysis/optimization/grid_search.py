import itertools
import pandas as pd
from typing import Callable
from app.analysis.backtest.engine import run_backtest, BacktestResult


def grid_search(
    df: pd.DataFrame,
    signal_generator: Callable,
    param_grid: dict[str, list],
    scoring: str = "sharpe_ratio",
    top_n: int = 10,
) -> list[dict]:
    """Exhaustive grid search over parameter combinations.

    Args:
        df: OHLCV DataFrame
        signal_generator: Function(df, **params) -> (entry_signals, exit_signals)
        param_grid: Dict of param_name -> list of values to try
        scoring: Metric to optimize ('sharpe_ratio', 'total_return', 'sortino_ratio', etc.)
        top_n: Number of top results to return
    """
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(itertools.product(*param_values))

    results = []
    for combo in combinations:
        params = dict(zip(param_names, combo))
        try:
            entry_signals, exit_signals = signal_generator(df, **params)
            bt = run_backtest(df, entry_signals, exit_signals)

            if bt.total_trades < 5:
                continue

            results.append({
                "params": params,
                "metrics": {
                    "total_return": bt.total_return,
                    "annual_return": bt.annual_return,
                    "sharpe_ratio": bt.sharpe_ratio,
                    "sortino_ratio": bt.sortino_ratio,
                    "max_drawdown": bt.max_drawdown,
                    "win_rate": bt.win_rate,
                    "profit_factor": bt.profit_factor,
                    "total_trades": bt.total_trades,
                    "calmar_ratio": bt.calmar_ratio,
                },
                "backtest": bt,
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["metrics"].get(scoring, 0), reverse=True)
    return results[:top_n]


class GridSearchOptimizer:
    """Class wrapper around grid_search for strategy optimization tasks."""

    def __init__(self, param_grid: dict[str, list], scoring_metric: str = "sharpe_ratio"):
        self.param_grid = param_grid
        self.scoring_metric = scoring_metric

    def run(self, df: pd.DataFrame, top_n: int = 10) -> list[dict]:
        """Run grid search using default signal generators for common strategies."""
        from app.analysis.indicators.registry import get_signal_generator
        signal_gen = get_signal_generator(self.param_grid)
        return grid_search(df, signal_gen, self.param_grid, self.scoring_metric, top_n)
