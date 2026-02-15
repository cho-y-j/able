"""Tests for KISRealtimeManager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.realtime_manager import KISRealtimeManager


@pytest.fixture
def manager():
    """Fresh KISRealtimeManager instance."""
    return KISRealtimeManager()


@pytest.fixture
def mock_kis_ws():
    ws = AsyncMock()
    ws.connect = AsyncMock()
    ws.subscribe = AsyncMock()
    ws.unsubscribe = AsyncMock()
    ws.disconnect = AsyncMock()
    ws.listen = AsyncMock()
    ws.on_message = MagicMock()
    ws.subscription_count = 0
    ws.MAX_SUBSCRIPTIONS = 20
    return ws


def _patch_kis_ws(mock_ws):
    """Patch KISWebSocket class, setting MAX_SUBSCRIPTIONS on the mock class."""
    mock_cls = MagicMock(return_value=mock_ws)
    mock_cls.MAX_SUBSCRIPTIONS = 20
    return patch("app.services.realtime_manager.KISWebSocket", mock_cls)


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_creates_session(self, manager, mock_kis_ws):
        with _patch_kis_ws(mock_kis_ws):
            result = await manager.subscribe(
                user_id="u1", stock_code="005930", is_paper=True,
                app_key="key", app_secret="secret",
            )

        assert result is True
        assert "u1" in manager._sessions
        assert "005930" in manager._user_stocks["u1"]
        assert "u1" in manager._stock_subscribers["005930"]
        mock_kis_ws.connect.assert_awaited_once()
        mock_kis_ws.subscribe.assert_awaited_once_with("005930")

    @pytest.mark.asyncio
    async def test_subscribe_returns_false_no_credentials(self, manager):
        result = await manager.subscribe(
            user_id="u1", stock_code="005930", is_paper=True,
        )
        assert result is False
        assert "u1" not in manager._sessions

    @pytest.mark.asyncio
    async def test_subscribe_deduplicates(self, manager, mock_kis_ws):
        with _patch_kis_ws(mock_kis_ws):
            await manager.subscribe("u1", "005930", True, "k", "s")
            # Already tracked from first subscribe
            result = await manager.subscribe("u1", "005930", True, "k", "s")

        assert result is True
        # subscribe should only be called once (first time)
        assert mock_kis_ws.subscribe.await_count == 1

    @pytest.mark.asyncio
    async def test_subscribe_fails_on_connect_error(self, manager):
        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock(side_effect=ConnectionError("refused"))
        mock_cls = MagicMock(return_value=mock_ws)
        mock_cls.MAX_SUBSCRIPTIONS = 20
        with patch("app.services.realtime_manager.KISWebSocket", mock_cls):
            result = await manager.subscribe("u1", "005930", True, "k", "s")

        assert result is False

    @pytest.mark.asyncio
    async def test_subscribe_max_limit(self, manager, mock_kis_ws):
        mock_kis_ws.subscription_count = 0
        with _patch_kis_ws(mock_kis_ws):
            await manager.subscribe("u1", "005930", True, "k", "s")
            # Set to max after first subscribe
            mock_kis_ws.subscription_count = 20
            result = await manager.subscribe("u1", "000660", True, "k", "s")

        assert result is False


class TestUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_removes_tracking(self, manager, mock_kis_ws):
        with _patch_kis_ws(mock_kis_ws):
            await manager.subscribe("u1", "005930", True, "k", "s")
            await manager.unsubscribe("u1", "005930")

        assert "005930" not in manager._stock_subscribers
        assert "u1" not in manager._user_stocks

    @pytest.mark.asyncio
    async def test_unsubscribe_noop_if_not_subscribed(self, manager):
        # Should not raise
        await manager.unsubscribe("u1", "005930")

    @pytest.mark.asyncio
    async def test_unsubscribe_all(self, manager, mock_kis_ws):
        with _patch_kis_ws(mock_kis_ws):
            await manager.subscribe("u1", "005930", True, "k", "s")
            mock_kis_ws.subscription_count = 1
            await manager.subscribe("u1", "000660", True, "k", "s")

            await manager.unsubscribe_all("u1")

        assert "u1" not in manager._user_stocks
        assert len(manager._stock_subscribers) == 0


class TestOnTick:
    @pytest.mark.asyncio
    async def test_tick_routes_to_subscribers(self, manager):
        """Tick data is forwarded to subscribed users via ConnectionManager."""
        manager._stock_subscribers["005930"] = {"u1"}

        mock_ws_manager = AsyncMock()
        with patch("app.services.realtime_manager.manager", mock_ws_manager, create=True), \
             patch("app.api.v1.websocket.manager", mock_ws_manager):
            await manager._on_kis_tick({
                "stock_code": "005930",
                "current_price": 72000,
                "change": 500,
                "change_percent": 0.7,
                "volume": 1000,
                "cumulative_volume": 50000,
                "exec_time": "093000",
            })

        mock_ws_manager.send_to_user.assert_awaited_once()
        call_args = mock_ws_manager.send_to_user.call_args
        assert call_args[0][0] == "u1"
        assert call_args[0][1]["type"] == "price_update"
        assert call_args[0][1]["current_price"] == 72000

    @pytest.mark.asyncio
    async def test_tick_feeds_trigger_service(self, manager):
        """Tick data is fed to TriggerService."""
        manager._trigger = MagicMock()

        await manager._on_kis_tick({
            "stock_code": "005930",
            "current_price": 72000,
        })

        manager._trigger.add_tick.assert_called_once_with("005930", {
            "stock_code": "005930",
            "current_price": 72000,
        })

    @pytest.mark.asyncio
    async def test_tick_ignores_empty_stock_code(self, manager):
        """Tick with empty stock_code is ignored."""
        manager._trigger = MagicMock()
        await manager._on_kis_tick({"stock_code": ""})
        manager._trigger.add_tick.assert_not_called()


class TestRecipeEvaluation:
    @pytest.mark.asyncio
    async def test_recipe_signal_triggers_on_tick(self, manager):
        """Active recipe with entry signal pushes recipe_signal event."""
        manager._stock_recipes["005930"] = [{
            "recipe_id": "r1",
            "user_id": "u1",
            "name": "Test Recipe",
            "signal_config": {"entry": {"indicators": []}},
            "custom_filters": None,
        }]
        manager._trigger = MagicMock()
        manager._trigger.evaluate_recipe.return_value = {
            "should_enter": True,
            "should_exit": False,
        }

        mock_ws_manager = AsyncMock()
        with patch("app.api.v1.websocket.manager", mock_ws_manager):
            await manager._evaluate_recipes("005930", manager._stock_recipes["005930"])

        mock_ws_manager.send_to_user.assert_awaited_once()
        call_args = mock_ws_manager.send_to_user.call_args
        assert call_args[0][0] == "u1"
        assert call_args[0][1]["type"] == "recipe_signal"
        assert call_args[0][1]["signal_type"] == "entry"


class TestReloadRecipes:
    @pytest.mark.asyncio
    async def test_reload_clears_and_repopulates(self, manager):
        """reload_active_recipes replaces the stock→recipe mapping."""
        manager._stock_recipes["old"] = [{"recipe_id": "stale"}]

        mock_db = AsyncMock()
        mock_recipe = MagicMock()
        mock_recipe.id = "r1"
        mock_recipe.user_id = "u1"
        mock_recipe.name = "My Recipe"
        mock_recipe.is_active = True
        mock_recipe.stock_codes = ["005930", "000660"]
        mock_recipe.signal_config = {"entry": {}}
        mock_recipe.custom_filters = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_recipe]
        mock_db.execute = AsyncMock(return_value=mock_result)

        await manager.reload_active_recipes(mock_db)

        assert "old" not in manager._stock_recipes
        assert len(manager._stock_recipes["005930"]) == 1
        assert len(manager._stock_recipes["000660"]) == 1
        assert manager._stock_recipes["005930"][0]["recipe_id"] == "r1"

    @pytest.mark.asyncio
    async def test_reload_no_db_clears_only(self, manager):
        manager._stock_recipes["005930"] = [{"recipe_id": "r1"}]
        await manager.reload_active_recipes(db=None)
        assert len(manager._stock_recipes) == 0


class TestHelpers:
    def test_is_subscribed(self, manager):
        assert manager.is_subscribed("005930") is False
        manager._stock_subscribers["005930"] = {"u1"}
        assert manager.is_subscribed("005930") is True

    def test_get_subscriber_count(self, manager):
        assert manager.get_subscriber_count("005930") == 0
        manager._stock_subscribers["005930"] = {"u1", "u2"}
        assert manager.get_subscriber_count("005930") == 2


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_cleans_all(self, manager, mock_kis_ws):
        manager._trigger = MagicMock()
        with _patch_kis_ws(mock_kis_ws):
            await manager.subscribe("u1", "005930", True, "k", "s")
            await manager.shutdown()

        assert len(manager._sessions) == 0
        assert len(manager._user_stocks) == 0
        manager._trigger.clear_buffer.assert_called_once()
