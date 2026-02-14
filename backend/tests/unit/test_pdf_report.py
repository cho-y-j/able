"""Tests for PDF report generation."""

import pytest
from app.services.pdf_report import (
    generate_portfolio_report,
    generate_backtest_report,
    _format_won,
    _pnl_str,
)


class TestFormatWon:
    def test_billions(self):
        assert "억" in _format_won(150_000_000)

    def test_ten_thousands(self):
        assert "만" in _format_won(50_000)

    def test_small(self):
        result = _format_won(9999)
        assert "₩" in result

    def test_negative(self):
        result = _format_won(-200_000_000)
        assert "억" in result


class TestPnlStr:
    def test_positive(self):
        result = _pnl_str(100_000)
        assert "+" in result

    def test_negative(self):
        result = _pnl_str(-50_000)
        assert "-" in result or "₩" in result

    def test_zero(self):
        result = _pnl_str(0)
        assert "₩" in result


class TestGeneratePortfolioReport:
    def test_generates_valid_pdf(self):
        stats = {
            "portfolio_value": 10_000_000,
            "total_invested": 9_500_000,
            "unrealized_pnl": 500_000,
            "realized_pnl": 100_000,
            "total_pnl": 600_000,
            "total_pnl_pct": 6.32,
            "position_count": 3,
            "trade_stats": {
                "total_trades": 15,
                "win_rate": 0.6,
                "profit_factor": 1.8,
                "winning_trades": 9,
                "losing_trades": 6,
            },
        }
        positions = [
            {
                "stock_code": "005930",
                "stock_name": "Samsung",
                "quantity": 10,
                "avg_cost_price": 70000,
                "current_price": 75000,
                "unrealized_pnl": 50000,
            },
        ]
        pdf = generate_portfolio_report("Test User", stats, positions)

        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        assert pdf[:5] == b"%PDF-"

    def test_with_risk_data(self):
        stats = {
            "portfolio_value": 5_000_000,
            "total_invested": 5_000_000,
            "unrealized_pnl": 0,
            "realized_pnl": 0,
            "total_pnl": 0,
            "total_pnl_pct": 0,
            "position_count": 1,
        }
        risk_data = {
            "historical": {"var": 250000, "cvar": 350000},
            "parametric": {"var": 230000, "cvar": 320000},
            "monte_carlo": {"var": 260000, "cvar": 340000},
            "stress_tests": [
                {"scenario": "Market Crash", "portfolio_loss": -1000000, "loss_percent": -20.0},
                {"scenario": "Flash Crash", "portfolio_loss": -500000, "loss_percent": -10.0},
            ],
        }
        pdf = generate_portfolio_report("User", stats, [], risk_data=risk_data)
        assert pdf[:5] == b"%PDF-"

    def test_empty_positions(self):
        stats = {
            "portfolio_value": 0,
            "total_invested": 0,
            "unrealized_pnl": 0,
            "realized_pnl": 0,
            "total_pnl": 0,
            "total_pnl_pct": 0,
            "position_count": 0,
        }
        pdf = generate_portfolio_report("User", stats, [])
        assert pdf[:5] == b"%PDF-"

    def test_pdf_size_reasonable(self):
        stats = {
            "portfolio_value": 10_000_000,
            "total_invested": 9_000_000,
            "unrealized_pnl": 1_000_000,
            "realized_pnl": 500_000,
            "total_pnl": 1_500_000,
            "total_pnl_pct": 16.67,
            "position_count": 5,
            "trade_stats": {
                "total_trades": 50,
                "win_rate": 0.55,
                "profit_factor": 1.4,
                "winning_trades": 28,
                "losing_trades": 22,
            },
        }
        positions = [
            {"stock_code": f"0059{i}0", "stock_name": f"Stock {i}",
             "quantity": i * 10, "avg_cost_price": 50000 + i * 1000,
             "current_price": 52000 + i * 1000, "unrealized_pnl": 20000 * i}
            for i in range(5)
        ]
        pdf = generate_portfolio_report("Big Portfolio User", stats, positions)
        assert len(pdf) < 100_000  # should be well under 100KB


class TestGenerateBacktestReport:
    def test_generates_valid_pdf(self):
        params = {
            "strategy": "SMA Crossover",
            "fast_period": 10,
            "slow_period": 30,
            "stock": "005930",
        }
        results = {
            "total_return": 15.5,
            "annual_return": 12.3,
            "max_drawdown": -8.2,
            "sharpe_ratio": 1.45,
            "win_rate": 0.55,
            "total_trades": 42,
            "profit_factor": 1.6,
        }
        pdf = generate_backtest_report("SMA Crossover", params, results)

        assert isinstance(pdf, bytes)
        assert pdf[:5] == b"%PDF-"

    def test_with_trades(self):
        params = {"strategy": "RSI Mean Reversion"}
        results = {
            "total_return": 8.0,
            "annual_return": 6.0,
            "max_drawdown": -5.0,
            "sharpe_ratio": 1.1,
            "win_rate": 0.5,
            "total_trades": 10,
            "profit_factor": 1.2,
        }
        trades = [
            {"date": "2026-01-05", "side": "BUY", "stock_code": "005930",
             "quantity": 10, "price": 70000, "pnl": 50000},
            {"date": "2026-01-10", "side": "SELL", "stock_code": "005930",
             "quantity": 10, "price": 75000, "pnl": 50000},
        ]
        pdf = generate_backtest_report("RSI Strategy", params, results, trades=trades)
        assert pdf[:5] == b"%PDF-"

    def test_empty_params(self):
        pdf = generate_backtest_report("Empty", {}, {"total_return": 0, "annual_return": 0,
                                                       "max_drawdown": 0, "sharpe_ratio": 0,
                                                       "win_rate": 0, "total_trades": 0,
                                                       "profit_factor": 0})
        assert pdf[:5] == b"%PDF-"
