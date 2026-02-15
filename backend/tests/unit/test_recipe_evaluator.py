"""Tests for the recipe_evaluator_node (trading orchestrator node)."""

import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", "test" * 8 + "==")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

import uuid
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, AsyncMock, MagicMock

from app.agents.nodes.recipe_evaluator import recipe_evaluator_node


# ── Helpers ──────────────────────────────────────────────


def _make_state(**overrides) -> dict:
    """Create a minimal TradingState dict with all required fields."""
    state = {
        "messages": [],
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "market_regime": None,
        "watchlist": [],
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
        "execution_config": None,
        "slippage_report": [],
        "active_recipes": [],
        "recipe_signals": {},
        "memory_context": "",
        "current_agent": "",
        "iteration_count": 0,
        "should_continue": True,
        "error_state": None,
    }
    state.update(overrides)
    return state


def _make_sample_df(n=100, base_price=72000):
    """Generate synthetic OHLCV DataFrame for mocking fetch_ohlcv_data."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = base_price + np.cumsum(np.random.randn(n) * 500)
    close = np.maximum(close, 10000)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 200,
            "high": close + abs(np.random.randn(n) * 300),
            "low": close - abs(np.random.randn(n) * 300),
            "close": close,
            "volume": np.random.randint(100_000, 10_000_000, n),
        },
        index=dates,
    )


def _make_recipe(
    stock_codes=None,
    signal_config=None,
    recipe_id=None,
    name="Test Golden Cross",
):
    """Build a single active recipe dict."""
    return {
        "id": recipe_id or str(uuid.uuid4()),
        "name": name,
        "signal_config": signal_config or {"combinator": "AND", "signals": [{"type": "sma_crossover"}]},
        "custom_filters": None,
        "stock_codes": stock_codes or ["005930"],
        "risk_config": {"max_position_pct": 0.1},
    }


# ── Tests ────────────────────────────────────────────────


class TestRecipeEvaluatorNode:
    @pytest.mark.asyncio
    async def test_no_user_id_returns_message(self):
        """When user_id is missing the node should return an informational message."""
        state = _make_state(user_id="")

        result = await recipe_evaluator_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        msg_content = result["messages"][0].content
        assert "user_id" in msg_content.lower() or "No user_id" in msg_content

    @pytest.mark.asyncio
    async def test_no_active_recipes_no_db(self):
        """No active_recipes in state, DB returns nothing -> empty recipe_signals."""
        state = _make_state(active_recipes=[])

        # Mock the DB session to return no recipes.
        # The function does a lazy `from app.db.session import async_session_factory`,
        # so we patch the source module attribute before the function executes.
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.db.session.async_session_factory",
            return_value=mock_session,
        ):
            result = await recipe_evaluator_node(state)

        assert result.get("recipe_signals") == {} or result.get("active_recipes") == []
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_with_active_recipes_evaluates(self):
        """Provide active_recipes in state, mock OHLCV + SignalComposer."""
        recipe = _make_recipe(stock_codes=["005930", "000660"])
        state = _make_state(active_recipes=[recipe])

        sample_df = _make_sample_df(n=100)
        entry_series = pd.Series([False] * 99 + [False], index=sample_df.index)
        exit_series = pd.Series([False] * 100, index=sample_df.index)

        with patch(
            "app.services.strategy_search.fetch_ohlcv_data",
            new_callable=AsyncMock,
            return_value=sample_df,
        ), patch(
            "app.analysis.composer.SignalComposer"
        ) as MockComposer:
            MockComposer.return_value.compose.return_value = (entry_series, exit_series)

            result = await recipe_evaluator_node(state)

        assert "recipe_signals" in result
        rid = recipe["id"]
        assert rid in result["recipe_signals"]
        assert "005930" in result["recipe_signals"][rid]["results"]
        assert "000660" in result["recipe_signals"][rid]["results"]

        # Neither stock has entry signal (all False)
        for sc in ["005930", "000660"]:
            stock_result = result["recipe_signals"][rid]["results"][sc]
            assert stock_result["entry"] is False
            assert stock_result["exit"] is False

    @pytest.mark.asyncio
    async def test_entry_signal_detected(self):
        """When compose returns entry=True on last bar, the node should report it."""
        recipe = _make_recipe(stock_codes=["005930"])
        state = _make_state(active_recipes=[recipe])

        sample_df = _make_sample_df(n=50)
        # Last bar has entry=True
        entry_series = pd.Series([False] * 49 + [True], index=sample_df.index)
        exit_series = pd.Series([False] * 50, index=sample_df.index)

        with patch(
            "app.services.strategy_search.fetch_ohlcv_data",
            new_callable=AsyncMock,
            return_value=sample_df,
        ), patch(
            "app.analysis.composer.SignalComposer"
        ) as MockComposer:
            MockComposer.return_value.compose.return_value = (entry_series, exit_series)

            result = await recipe_evaluator_node(state)

        rid = recipe["id"]
        stock_result = result["recipe_signals"][rid]["results"]["005930"]
        assert stock_result["entry"] is True
        assert stock_result["exit"] is False

        # Summary message should mention entry signal
        msg_content = result["messages"][0].content
        assert "entry" in msg_content.lower()

    @pytest.mark.asyncio
    async def test_evaluation_error_handled(self):
        """If fetch_ohlcv_data raises for one stock, the error is captured per-stock."""
        recipe = _make_recipe(stock_codes=["005930", "BADCODE"])
        state = _make_state(active_recipes=[recipe])

        sample_df = _make_sample_df(n=50)
        entry_series = pd.Series([False] * 50, index=sample_df.index)
        exit_series = pd.Series([False] * 50, index=sample_df.index)

        async def _mock_fetch(stock_code, **kwargs):
            if stock_code == "BADCODE":
                raise ValueError("Unknown stock code")
            return sample_df

        with patch(
            "app.services.strategy_search.fetch_ohlcv_data",
            new_callable=AsyncMock,
            side_effect=_mock_fetch,
        ), patch(
            "app.analysis.composer.SignalComposer"
        ) as MockComposer:
            MockComposer.return_value.compose.return_value = (entry_series, exit_series)

            result = await recipe_evaluator_node(state)

        rid = recipe["id"]
        # Good stock should have a normal result
        assert result["recipe_signals"][rid]["results"]["005930"]["entry"] is False
        # Bad stock should have an error entry
        assert "error" in result["recipe_signals"][rid]["results"]["BADCODE"]
