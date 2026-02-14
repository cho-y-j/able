import pandas as pd
import numpy as np
from typing import Callable
from app.analysis.backtest.engine import run_backtest


def walk_forward_analysis(
    df: pd.DataFrame,
    signal_generator: Callable,
    params: dict,
    n_splits: int = 5,
    train_ratio: float = 0.7,
) -> dict:
    """Walk-Forward Analysis: rolling train/test splits.

    Returns:
        Dict with overall WFA score, per-window results, and stability metrics.
    """
    n = len(df)
    window_size = n // n_splits
    results = []

    for i in range(n_splits):
        start = i * window_size
        end = min(start + window_size, n)
        window = df.iloc[start:end]

        if len(window) < 50:
            continue

        split_point = int(len(window) * train_ratio)
        train = window.iloc[:split_point]
        test = window.iloc[split_point:]

        if len(test) < 10:
            continue

        try:
            # Run on test set (out-of-sample)
            entry_signals, exit_signals = signal_generator(test, **params)
            bt = run_backtest(test, entry_signals, exit_signals)

            results.append({
                "window": i + 1,
                "test_start": str(test.index[0]),
                "test_end": str(test.index[-1]),
                "sharpe_ratio": bt.sharpe_ratio,
                "total_return": bt.total_return,
                "max_drawdown": bt.max_drawdown,
                "total_trades": bt.total_trades,
                "win_rate": bt.win_rate,
            })
        except Exception:
            results.append({
                "window": i + 1,
                "error": True,
                "sharpe_ratio": 0,
                "total_return": 0,
            })

    if not results:
        return {"wfa_score": 0, "windows": [], "stability": 0}

    sharpe_values = [r["sharpe_ratio"] for r in results]
    return_values = [r["total_return"] for r in results]

    # WFA score: percentage of windows with positive Sharpe
    positive_windows = sum(1 for s in sharpe_values if s > 0)
    wfa_score = (positive_windows / len(results)) * 100

    # Stability: 1 - (std / mean) of Sharpe ratios
    mean_sharpe = np.mean(sharpe_values)
    std_sharpe = np.std(sharpe_values)
    stability = max(0, 1 - (std_sharpe / abs(mean_sharpe) if mean_sharpe != 0 else 1)) * 100

    return {
        "wfa_score": round(wfa_score, 2),
        "stability": round(stability, 2),
        "mean_sharpe": round(mean_sharpe, 4),
        "mean_return": round(np.mean(return_values), 4),
        "windows": results,
    }


class WalkForwardAnalysis:
    """Class wrapper for walk-forward analysis (used by optimization tasks)."""

    def __init__(self, n_splits: int = 5, train_ratio: float = 0.7):
        self.n_splits = n_splits
        self.train_ratio = train_ratio

    def run(self, df: pd.DataFrame, params: dict) -> dict:
        """Run WFA using auto-detected signal generator."""
        from app.analysis.indicators.registry import get_signal_generator
        signal_gen = get_signal_generator(params)
        return walk_forward_analysis(
            df, signal_gen, params,
            n_splits=self.n_splits,
            train_ratio=self.train_ratio,
        )
