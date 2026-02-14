"""Tools available to AI agents for analysis operations."""

from langchain_core.tools import tool
import pandas as pd

from app.analysis.indicators.registry import calculate_multiple, list_indicators
from app.analysis.backtest.engine import run_backtest
from app.analysis.validation.scoring import calculate_composite_score


@tool
def get_available_indicators() -> list[str]:
    """Get list of all available technical indicators."""
    return list_indicators()


@tool
def calculate_indicators_tool(ohlcv_data: list[dict], indicators: list[dict]) -> dict:
    """Calculate technical indicators on OHLCV data.

    Args:
        ohlcv_data: List of {date, open, high, low, close, volume} dicts
        indicators: List of {name, params} dicts, e.g. [{"name": "RSI", "params": {"period": 14}}]
    """
    df = pd.DataFrame(ohlcv_data)
    df = calculate_multiple(df, indicators)
    # Return last 5 rows for each indicator column
    result_cols = [c for c in df.columns if c not in ("date", "open", "high", "low", "close", "volume")]
    return {col: df[col].tail(5).tolist() for col in result_cols}


@tool
def run_backtest_tool(
    ohlcv_data: list[dict],
    entry_indicator: str,
    entry_threshold: float,
    entry_comparator: str,
    exit_indicator: str,
    exit_threshold: float,
    exit_comparator: str,
) -> dict:
    """Run a backtest with simple indicator-based entry/exit rules.

    Args:
        ohlcv_data: OHLCV data
        entry_indicator: Column name for entry signal (e.g., 'RSI_14')
        entry_threshold: Threshold value for entry
        entry_comparator: '<' or '>' for entry condition
        exit_indicator: Column name for exit signal
        exit_threshold: Threshold for exit
        exit_comparator: '<' or '>' for exit condition
    """
    df = pd.DataFrame(ohlcv_data)

    if entry_comparator == "<":
        entry_signals = df[entry_indicator] < entry_threshold
    else:
        entry_signals = df[entry_indicator] > entry_threshold

    if exit_comparator == "<":
        exit_signals = df[exit_indicator] < exit_threshold
    else:
        exit_signals = df[exit_indicator] > exit_threshold

    result = run_backtest(df, entry_signals, exit_signals)
    return {
        "total_return": result.total_return,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
    }


@tool
def score_strategy_tool(metrics: dict) -> dict:
    """Calculate composite score for a strategy based on its backtest metrics.

    Args:
        metrics: Dict with keys like sharpe_ratio, sortino_ratio, max_drawdown, etc.
    """
    return calculate_composite_score(metrics)
