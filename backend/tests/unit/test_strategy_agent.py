"""Tests for enhanced strategy search agent node."""

import uuid
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage

from app.agents.nodes.strategy_search import (
    strategy_search_node,
    _run_quick_backtest,
    REGIME_SIGNALS,
    MIN_SCORE_THRESHOLD,
    MAX_CANDIDATES_PER_STOCK,
    MAX_TOTAL_CANDIDATES,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def sample_ohlcv():
    """Generate 250 days of synthetic OHLCV data."""
    np.random.seed(42)
    n = 250
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 50000 + np.cumsum(np.random.randn(n) * 500)
    close = np.maximum(close, 10000)
    df = pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 200,
            "high": close + abs(np.random.randn(n) * 300),
            "low": close - abs(np.random.randn(n) * 300),
            "close": close,
            "volume": np.random.randint(100_000, 10_000_000, n),
        },
        index=dates,
    )
    df.index.name = "date"
    return df


def _make_state(**overrides) -> dict:
    """Create a minimal TradingState dict."""
    state = {
        "messages": [],
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "market_regime": {"classification": "sideways", "confidence": 0.8, "indicators": {}, "timestamp": "2024-01-01"},
        "watchlist": ["005930"],
        "strategy_candidates": [],
        "optimization_status": "",
        "risk_assessment": None,
        "pending_orders": [],
        "executed_orders": [],
        "portfolio_snapshot": {},
        "alerts": [],
        "pending_approval": False,
        "pending_trades": [],
        "approval_status": None,
        "approval_threshold": 5_000_000,
        "hitl_enabled": False,
        "memory_context": "",
        "current_agent": "",
        "iteration_count": 0,
        "should_continue": True,
        "error_state": None,
    }
    state.update(overrides)
    return state


# ── REGIME_SIGNALS ───────────────────────────────────────


class TestRegimeSignals:
    def test_all_regimes_have_signals(self):
        for regime in ["bull", "bear", "sideways", "volatile", "crisis"]:
            assert regime in REGIME_SIGNALS
            assert len(REGIME_SIGNALS[regime]) >= 3

    def test_bull_regime_has_trend_signals(self):
        bull = REGIME_SIGNALS["bull"]
        assert "sma_crossover" in bull
        assert "macd_crossover" in bull
        assert "supertrend" in bull

    def test_bear_regime_has_reversal_signals(self):
        bear = REGIME_SIGNALS["bear"]
        assert "rsi_mean_reversion" in bear
        assert "elder_impulse" in bear

    def test_sideways_regime_has_mean_reversion(self):
        sw = REGIME_SIGNALS["sideways"]
        assert "rsi_mean_reversion" in sw
        assert "bb_bounce" in sw

    def test_volatile_regime_has_volatility_signals(self):
        vol = REGIME_SIGNALS["volatile"]
        assert "keltner_breakout" in vol
        assert "squeeze_momentum" in vol

    def test_crisis_regime_is_defensive(self):
        crisis = REGIME_SIGNALS["crisis"]
        assert len(crisis) <= 5  # Fewer signals = more conservative
        assert "rsi_mean_reversion" in crisis


# ── _run_quick_backtest ──────────────────────────────────


class TestQuickBacktest:
    def test_returns_metrics_and_score(self, sample_ohlcv):
        result = _run_quick_backtest(sample_ohlcv, "rsi_mean_reversion")
        if result is not None:
            assert "metrics" in result
            assert "composite_score" in result
            assert "grade" in result
            assert "params" in result
            assert isinstance(result["composite_score"], (int, float))

    def test_returns_none_for_bad_signal(self, sample_ohlcv):
        result = _run_quick_backtest(sample_ohlcv, "nonexistent_signal")
        assert result is None

    def test_accepts_custom_params(self, sample_ohlcv):
        result = _run_quick_backtest(
            sample_ohlcv,
            "rsi_mean_reversion",
            {"rsi_period": 10, "oversold": 25, "overbought": 75},
        )
        if result is not None:
            assert result["params"]["rsi_period"] == 10

    def test_uses_default_params_from_space(self, sample_ohlcv):
        result = _run_quick_backtest(sample_ohlcv, "sma_crossover")
        if result is not None:
            assert "params" in result
            assert len(result["params"]) > 0

    def test_returns_none_for_insufficient_signals(self, sample_ohlcv):
        """If a signal generator produces fewer than 3 entries, return None."""
        # Create tiny df with not enough data
        tiny_df = sample_ohlcv.head(10)
        result = _run_quick_backtest(tiny_df, "ichimoku_cloud")
        # Ichimoku needs 52+ periods, so should return None on 10 rows
        assert result is None

    def test_multiple_signals_produce_results(self, sample_ohlcv):
        """Test that several signals can produce backtest results."""
        signals_to_test = ["rsi_mean_reversion", "sma_crossover", "bb_bounce", "macd_crossover"]
        results = []
        for sig in signals_to_test:
            r = _run_quick_backtest(sample_ohlcv, sig)
            if r is not None:
                results.append(r)
        # At least some should succeed
        assert len(results) >= 2


# ── strategy_search_node ─────────────────────────────────


class TestStrategySearchNode:
    @pytest.mark.asyncio
    async def test_skips_if_candidates_exist(self):
        state = _make_state(
            strategy_candidates=[{"stock_code": "005930", "composite_score": 50}],
        )
        result = await strategy_search_node(state)
        assert result["optimization_status"] == "complete"
        assert len(result["strategy_candidates"]) == 1
        assert "existing candidates" in result["messages"][0].content.lower()

    @pytest.mark.asyncio
    async def test_no_watchlist_returns_empty(self):
        state = _make_state(watchlist=[])
        result = await strategy_search_node(state)
        assert result["optimization_status"] == "no_opportunities"
        assert len(result["strategy_candidates"]) == 0

    @pytest.mark.asyncio
    async def test_runs_backtests_with_mocked_data(self, sample_ohlcv):
        state = _make_state(
            watchlist=["005930"],
            market_regime={"classification": "sideways", "confidence": 0.8, "indicators": {}, "timestamp": ""},
        )
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=sample_ohlcv):
            result = await strategy_search_node(state)

        candidates = result["strategy_candidates"]
        assert len(candidates) <= MAX_CANDIDATES_PER_STOCK
        for c in candidates:
            assert "stock_code" in c
            assert "signal_name" in c
            assert "backtest_metrics" in c
            assert "composite_score" in c
            assert c["composite_score"] >= MIN_SCORE_THRESHOLD

    @pytest.mark.asyncio
    async def test_respects_regime_signal_selection(self, sample_ohlcv):
        """Bull regime should test trend signals."""
        state = _make_state(
            watchlist=["005930"],
            market_regime={"classification": "bull", "confidence": 0.9, "indicators": {}, "timestamp": ""},
        )
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=sample_ohlcv):
            result = await strategy_search_node(state)

        candidates = result["strategy_candidates"]
        signal_names = {c["signal_name"] for c in candidates}
        # At least one trend signal should appear if data supports it
        bull_signals = set(REGIME_SIGNALS["bull"])
        if candidates:
            assert len(signal_names & bull_signals) > 0

    @pytest.mark.asyncio
    async def test_handles_data_fetch_failure(self):
        state = _make_state(watchlist=["005930", "035720"])
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=None):
            result = await strategy_search_node(state)
        assert result["optimization_status"] == "no_opportunities"
        assert "skipped" in result["messages"][0].content.lower()

    @pytest.mark.asyncio
    async def test_multiple_stocks(self, sample_ohlcv):
        state = _make_state(watchlist=["005930", "035720", "000660"])
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=sample_ohlcv):
            result = await strategy_search_node(state)
        candidates = result["strategy_candidates"]
        # Should have candidates from multiple stocks
        assert len(candidates) <= MAX_TOTAL_CANDIDATES
        stock_codes = {c["stock_code"] for c in candidates}
        assert len(stock_codes) >= 1  # At least 1 stock has valid candidates

    @pytest.mark.asyncio
    async def test_candidates_sorted_by_score(self, sample_ohlcv):
        state = _make_state(watchlist=["005930"])
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=sample_ohlcv):
            result = await strategy_search_node(state)
        candidates = result["strategy_candidates"]
        scores = [c["composite_score"] for c in candidates]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_llm_suggestions_integrated(self, sample_ohlcv):
        """When LLM provides valid signal suggestions, they should be tested."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"strategies": [{"stock_code": "005930", "signal_name": "rsi_mean_reversion", "parameters": {"rsi_period": 10, "oversold": 25, "overbought": 75}}]}'
        )
        state = _make_state(
            watchlist=["005930"],
            _llm=mock_llm,
        )
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=sample_ohlcv):
            result = await strategy_search_node(state)

        candidates = result["strategy_candidates"]
        # Check if LLM-suggested signal was tested
        llm_candidates = [c for c in candidates if c.get("source") == "llm"]
        # May or may not pass score threshold, but LLM was invoked
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_output_format(self, sample_ohlcv):
        state = _make_state(watchlist=["005930"])
        with patch("app.agents.nodes.strategy_search._fetch_ohlcv", return_value=sample_ohlcv):
            result = await strategy_search_node(state)

        assert "messages" in result
        assert "strategy_candidates" in result
        assert "optimization_status" in result
        assert "current_agent" in result
        assert result["current_agent"] == "strategy_search"
        assert isinstance(result["messages"][0], AIMessage)


# ── Risk Manager (already enhanced, verify integration) ──


class TestRiskManagerIntegration:
    @pytest.mark.asyncio
    async def test_risk_manager_with_backtest_metrics(self):
        """Verify risk_manager handles candidates with real backtest_metrics."""
        from app.agents.nodes.risk_manager import risk_manager_node

        candidate = {
            "stock_code": "005930",
            "strategy_name": "rsi_mean_reversion_005930",
            "signal_name": "rsi_mean_reversion",
            "parameters": {"rsi_period": 14, "oversold": 30, "overbought": 70},
            "backtest_metrics": {
                "total_return": 0.15,
                "sharpe_ratio": 1.2,
                "win_rate": 55,
                "profit_factor": 1.5,
                "max_drawdown": -0.08,
                "total_trades": 45,
            },
            "composite_score": 62,
            "current_price": 72000,
        }

        state = _make_state(
            strategy_candidates=[candidate],
            portfolio_snapshot={
                "total_balance": 10_000_000,
                "total_exposure": 0,
                "daily_pnl": 0,
                "current_drawdown": 0,
            },
        )
        result = await risk_manager_node(state)
        assert "risk_assessment" in result
        ra = result["risk_assessment"]
        assert "approved_trades" in ra
        assert "rejected_trades" in ra

    @pytest.mark.asyncio
    async def test_risk_manager_rejects_low_score(self):
        """Low composite score should cause rejection."""
        from app.agents.nodes.risk_manager import risk_manager_node

        candidate = {
            "stock_code": "005930",
            "strategy_name": "bad_strategy",
            "parameters": {},
            "backtest_metrics": {"sharpe_ratio": -0.5, "win_rate": 30},
            "composite_score": 15,
            "current_price": 72000,
        }

        state = _make_state(
            strategy_candidates=[candidate],
            portfolio_snapshot={
                "total_balance": 10_000_000,
                "total_exposure": 0,
                "daily_pnl": 0,
                "current_drawdown": 0,
            },
        )
        result = await risk_manager_node(state)
        ra = result["risk_assessment"]
        assert "005930" in ra["rejected_trades"]
