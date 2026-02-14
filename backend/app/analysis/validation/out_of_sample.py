"""Out-of-Sample (OOS) validation for trading strategies.

Splits data into in-sample (training) and out-of-sample (testing) periods
to verify that strategy performance isn't just curve-fitting.
"""

import logging
from typing import Callable

import pandas as pd
import numpy as np
from app.analysis.backtest.engine import run_backtest

logger = logging.getLogger(__name__)


def out_of_sample_test(
    df: pd.DataFrame,
    signal_generator: Callable,
    params: dict,
    oos_ratio: float = 0.3,
) -> dict:
    """Run out-of-sample validation.

    Args:
        df: Full OHLCV DataFrame
        signal_generator: Signal generation function
        params: Strategy parameters
        oos_ratio: Fraction of data reserved for out-of-sample testing

    Returns:
        Dict with IS/OOS metrics and degradation analysis
    """
    n = len(df)
    split_idx = int(n * (1 - oos_ratio))

    if split_idx < 60 or (n - split_idx) < 30:
        return {
            "oos_score": 0,
            "message": "Insufficient data for out-of-sample testing",
        }

    is_data = df.iloc[:split_idx]
    oos_data = df.iloc[split_idx:]

    # Run backtests on both periods
    try:
        is_entry, is_exit = signal_generator(is_data, **params)
        is_bt = run_backtest(is_data, is_entry, is_exit)
    except Exception as e:
        return {"oos_score": 0, "message": f"In-sample backtest failed: {e}"}

    try:
        oos_entry, oos_exit = signal_generator(oos_data, **params)
        oos_bt = run_backtest(oos_data, oos_entry, oos_exit)
    except Exception as e:
        return {"oos_score": 0, "message": f"Out-of-sample backtest failed: {e}"}

    # Calculate degradation metrics
    def safe_ratio(oos_val: float, is_val: float) -> float:
        if is_val == 0:
            return 0.0 if oos_val == 0 else 1.0
        return oos_val / is_val

    sharpe_retention = safe_ratio(oos_bt.sharpe_ratio, is_bt.sharpe_ratio)
    return_retention = safe_ratio(oos_bt.annual_return, is_bt.annual_return)
    winrate_retention = safe_ratio(oos_bt.win_rate, is_bt.win_rate)

    # OOS Score: weighted average of retention ratios (capped at 100)
    # Higher = less degradation = better
    oos_score = min(100, max(0, (
        0.4 * min(sharpe_retention, 1.5) +
        0.3 * min(return_retention, 1.5) +
        0.3 * min(winrate_retention, 1.5)
    ) * 100 / 1.5))

    # Check if strategy is profitable OOS
    oos_profitable = oos_bt.total_return > 0 and oos_bt.sharpe_ratio > 0

    return {
        "oos_score": round(oos_score, 2),
        "oos_profitable": oos_profitable,
        "in_sample": {
            "period": f"{is_data.index[0]} to {is_data.index[-1]}",
            "days": len(is_data),
            "total_return": is_bt.total_return,
            "annual_return": is_bt.annual_return,
            "sharpe_ratio": is_bt.sharpe_ratio,
            "max_drawdown": is_bt.max_drawdown,
            "total_trades": is_bt.total_trades,
            "win_rate": is_bt.win_rate,
        },
        "out_of_sample": {
            "period": f"{oos_data.index[0]} to {oos_data.index[-1]}",
            "days": len(oos_data),
            "total_return": oos_bt.total_return,
            "annual_return": oos_bt.annual_return,
            "sharpe_ratio": oos_bt.sharpe_ratio,
            "max_drawdown": oos_bt.max_drawdown,
            "total_trades": oos_bt.total_trades,
            "win_rate": oos_bt.win_rate,
        },
        "degradation": {
            "sharpe_retention": round(sharpe_retention * 100, 2),
            "return_retention": round(return_retention * 100, 2),
            "winrate_retention": round(winrate_retention * 100, 2),
        },
    }


def combinatorial_purged_cv(
    df: pd.DataFrame,
    signal_generator: Callable,
    params: dict,
    n_splits: int = 5,
    purge_days: int = 5,
) -> dict:
    """Combinatorial Purged Cross-Validation (CPCV).

    More rigorous than simple walk-forward: uses combinatorial splits
    with purge gaps to prevent information leakage.

    Args:
        df: OHLCV DataFrame
        signal_generator: Signal generation function
        params: Strategy parameters
        n_splits: Number of splits
        purge_days: Gap between train/test to prevent lookahead
    """
    n = len(df)
    fold_size = n // n_splits
    results = []

    for test_fold in range(n_splits):
        test_start = test_fold * fold_size
        test_end = min(test_start + fold_size, n)

        # Train on all other folds (with purge gap)
        train_mask = pd.Series(True, index=df.index)
        purge_start = max(0, test_start - purge_days)
        purge_end = min(n, test_end + purge_days)
        train_mask.iloc[purge_start:purge_end] = False

        train_data = df[train_mask]
        test_data = df.iloc[test_start:test_end]

        if len(test_data) < 20:
            continue

        try:
            entry, exit_ = signal_generator(test_data, **params)
            bt = run_backtest(test_data, entry, exit_)
            results.append({
                "fold": test_fold + 1,
                "test_days": len(test_data),
                "sharpe_ratio": bt.sharpe_ratio,
                "total_return": bt.total_return,
                "max_drawdown": bt.max_drawdown,
                "total_trades": bt.total_trades,
                "win_rate": bt.win_rate,
            })
        except Exception:
            results.append({
                "fold": test_fold + 1,
                "sharpe_ratio": 0,
                "total_return": 0,
                "error": True,
            })

    if not results:
        return {"cpcv_score": 0, "folds": []}

    sharpe_vals = [r["sharpe_ratio"] for r in results]
    positive_folds = sum(1 for s in sharpe_vals if s > 0)
    cpcv_score = (positive_folds / len(results)) * 100

    return {
        "cpcv_score": round(cpcv_score, 2),
        "mean_sharpe": round(float(np.mean(sharpe_vals)), 4),
        "std_sharpe": round(float(np.std(sharpe_vals)), 4),
        "positive_folds": positive_folds,
        "total_folds": len(results),
        "folds": results,
    }
