import pandas as pd
from typing import Callable
import optuna
from app.analysis.backtest.engine import run_backtest


optuna.logging.set_verbosity(optuna.logging.WARNING)


def bayesian_optimize(
    df: pd.DataFrame,
    signal_generator: Callable,
    param_space: dict[str, dict],
    scoring: str = "sharpe_ratio",
    n_trials: int = 100,
    top_n: int = 10,
) -> list[dict]:
    """Bayesian optimization using Optuna.

    Args:
        df: OHLCV DataFrame
        signal_generator: Function(df, **params) -> (entry_signals, exit_signals)
        param_space: Dict of param_name -> {"type": "int"|"float", "low": x, "high": y}
        scoring: Metric to maximize
        n_trials: Number of optimization trials
        top_n: Number of top results to return
    """
    all_results = []

    def objective(trial):
        params = {}
        for name, spec in param_space.items():
            if spec["type"] == "int":
                params[name] = trial.suggest_int(name, spec["low"], spec["high"])
            elif spec["type"] == "float":
                params[name] = trial.suggest_float(name, spec["low"], spec["high"])
            elif spec["type"] == "categorical":
                params[name] = trial.suggest_categorical(name, spec["choices"])

        try:
            entry_signals, exit_signals = signal_generator(df, **params)
            bt = run_backtest(df, entry_signals, exit_signals)

            if bt.total_trades < 5:
                return float("-inf")

            all_results.append({
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

            return getattr(bt, scoring, bt.sharpe_ratio)
        except Exception:
            return float("-inf")

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials)

    all_results.sort(key=lambda x: x["metrics"].get(scoring, 0), reverse=True)
    return all_results[:top_n]
