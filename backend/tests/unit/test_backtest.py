import pytest
import pandas as pd
import numpy as np

from app.analysis.backtest.engine import run_backtest


class TestBacktestEngine:
    def test_basic_backtest(self, sample_ohlcv):
        entry = sample_ohlcv["close"].pct_change() < -0.02  # Buy on 2% dip
        exit_sig = sample_ohlcv["close"].pct_change() > 0.02  # Sell on 2% gain

        result = run_backtest(sample_ohlcv, entry, exit_sig)

        assert result.total_trades > 0
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert result.max_drawdown <= 0
        assert len(result.equity_curve) > 0
        assert len(result.trade_log) == result.total_trades

    def test_no_trades(self, sample_ohlcv):
        entry = pd.Series(False, index=sample_ohlcv.index)
        exit_sig = pd.Series(False, index=sample_ohlcv.index)

        result = run_backtest(sample_ohlcv, entry, exit_sig)
        assert result.total_trades == 0
        assert result.win_rate == 0

    def test_always_in(self, sample_ohlcv):
        entry = pd.Series(True, index=sample_ohlcv.index)
        exit_sig = pd.Series(False, index=sample_ohlcv.index)

        result = run_backtest(sample_ohlcv, entry, exit_sig)
        assert result.total_trades <= 1  # Should enter once and never exit
