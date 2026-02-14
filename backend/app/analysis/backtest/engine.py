import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class BacktestResult:
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    calmar_ratio: float
    equity_curve: list[dict]
    trade_log: list[dict]


def run_backtest(
    df: pd.DataFrame,
    entry_signals: pd.Series,
    exit_signals: pd.Series,
    initial_capital: float = 10_000_000,
    commission: float = 0.00015,  # 0.015% (Korean stock commission)
    slippage: float = 0.001,
) -> BacktestResult:
    """Simple vectorized backtest engine.

    Args:
        df: OHLCV DataFrame with datetime index
        entry_signals: Boolean series (True = buy signal)
        exit_signals: Boolean series (True = sell signal)
        initial_capital: Starting capital in KRW
        commission: Commission rate per trade
        slippage: Slippage as fraction of price
    """
    close = df["close"].values
    n = len(close)

    # Generate positions: 1 = long, 0 = flat
    position = np.zeros(n)
    in_position = False

    trades = []
    entry_price = 0.0
    entry_idx = 0

    for i in range(n):
        if not in_position and entry_signals.iloc[i]:
            in_position = True
            position[i] = 1
            entry_price = close[i] * (1 + slippage)
            entry_idx = i
        elif in_position and exit_signals.iloc[i]:
            in_position = False
            position[i] = 0
            exit_price = close[i] * (1 - slippage)
            pnl_pct = (exit_price - entry_price) / entry_price - 2 * commission
            trades.append({
                "entry_date": str(df.index[entry_idx]),
                "exit_date": str(df.index[i]),
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl_percent": round(pnl_pct * 100, 4),
                "hold_days": i - entry_idx,
            })
        elif in_position:
            position[i] = 1

    # Calculate returns
    daily_returns = pd.Series(close).pct_change().fillna(0).values
    strategy_returns = position * daily_returns

    # Equity curve
    equity = initial_capital * (1 + pd.Series(strategy_returns)).cumprod()
    equity_list = [{"date": str(df.index[i]), "value": round(float(equity.iloc[i]), 2)}
                   for i in range(0, n, max(1, n // 500))]

    # Metrics
    total_ret = float(equity.iloc[-1] / initial_capital - 1) if n > 0 else 0
    trading_days = n
    annual_factor = 252 / max(trading_days, 1)
    annual_ret = (1 + total_ret) ** annual_factor - 1

    # Sharpe ratio (annualized)
    strat_ret_series = pd.Series(strategy_returns)
    mean_ret = strat_ret_series.mean()
    std_ret = strat_ret_series.std()
    sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0

    # Sortino ratio
    downside = strat_ret_series[strat_ret_series < 0].std()
    sortino = (mean_ret / downside * np.sqrt(252)) if downside > 0 else 0

    # Max drawdown
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd = float(drawdown.min())

    # Calmar ratio
    calmar = annual_ret / abs(max_dd) if max_dd != 0 else 0

    # Win rate & profit factor
    if trades:
        wins = [t for t in trades if t["pnl_percent"] > 0]
        losses = [t for t in trades if t["pnl_percent"] <= 0]
        win_rate = len(wins) / len(trades)
        total_profit = sum(t["pnl_percent"] for t in wins) or 0
        total_loss = abs(sum(t["pnl_percent"] for t in losses)) or 1
        profit_factor = total_profit / total_loss
    else:
        win_rate = 0
        profit_factor = 0

    return BacktestResult(
        total_return=round(total_ret * 100, 4),
        annual_return=round(annual_ret * 100, 4),
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
        max_drawdown=round(max_dd * 100, 4),
        win_rate=round(win_rate * 100, 2),
        profit_factor=round(profit_factor, 4),
        total_trades=len(trades),
        calmar_ratio=round(calmar, 4),
        equity_curve=equity_list,
        trade_log=trades,
    )
