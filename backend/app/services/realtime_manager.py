"""KIS real-time WebSocket bridge.

Manages KIS WebSocket sessions per user and routes real-time ticks to:
1. User WebSocket connections (price_update events)
2. TriggerService for recipe signal evaluation
3. NotificationService for recipe signal alerts

Gracefully falls back to REST polling when KIS WebSocket unavailable.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from app.integrations.kis.websocket import KISWebSocket
from app.services.trigger_service import TriggerService

logger = logging.getLogger(__name__)


class KISRealtimeManager:
    """Bridges KIS WebSocket ticks to user WebSockets + TriggerService."""

    def __init__(self):
        # Per-user KIS WebSocket session
        self._sessions: dict[str, KISWebSocket] = {}  # user_id → KISWebSocket
        # Background listen tasks per user
        self._listen_tasks: dict[str, asyncio.Task] = {}
        # stock_code → set of user_ids subscribed
        self._stock_subscribers: dict[str, set[str]] = defaultdict(set)
        # user_id → set of stock_codes subscribed
        self._user_stocks: dict[str, set[str]] = defaultdict(set)
        # Active recipes: stock_code → list of {recipe_id, user_id, signal_config, custom_filters, name}
        self._stock_recipes: dict[str, list[dict]] = defaultdict(list)
        # TriggerService for recipe evaluation
        self._trigger = TriggerService()
        # Track which users are in paper mode
        self._user_paper: dict[str, bool] = {}

    async def subscribe(
        self, user_id: str, stock_code: str, is_paper: bool = True,
        app_key: str | None = None, app_secret: str | None = None,
    ) -> bool:
        """Subscribe a user to real-time data for a stock.

        Args:
            user_id: User UUID string
            stock_code: Stock code (e.g., "005930")
            is_paper: Whether to use paper trading WebSocket
            app_key: KIS app key (needed to create new session)
            app_secret: KIS app secret (needed to create new session)

        Returns:
            True if subscribed via KIS WebSocket, False if caller should use REST fallback.
        """
        # Already subscribed
        if stock_code in self._user_stocks.get(user_id, set()):
            return True

        # Create KIS WebSocket session if needed
        if user_id not in self._sessions:
            if not app_key or not app_secret:
                logger.debug("No KIS credentials for user %s, falling back to REST", user_id)
                return False

            try:
                kis_ws = KISWebSocket(
                    app_key=app_key,
                    app_secret=app_secret,
                    is_paper=is_paper,
                )
                await kis_ws.connect()
                kis_ws.on_message(self._on_kis_tick)
                self._sessions[user_id] = kis_ws
                self._user_paper[user_id] = is_paper

                # Start listen task in background
                task = asyncio.create_task(self._listen_loop(user_id))
                self._listen_tasks[user_id] = task

                logger.info("Created KIS WS session for user %s (paper=%s)", user_id, is_paper)
            except Exception as e:
                logger.warning("KIS WS connect failed for user %s: %s", user_id, e)
                return False

        kis_ws = self._sessions[user_id]

        # Check max subscription limit
        if kis_ws.subscription_count >= KISWebSocket.MAX_SUBSCRIPTIONS:
            logger.warning(
                "Max subscriptions (%d) reached for user %s, rejecting %s",
                KISWebSocket.MAX_SUBSCRIPTIONS, user_id, stock_code,
            )
            return False

        # Subscribe to KIS WebSocket (only if not already subscribed by another user on same session)
        try:
            await kis_ws.subscribe(stock_code)
        except Exception as e:
            logger.warning("KIS WS subscribe failed for %s: %s", stock_code, e)
            return False

        # Track subscription
        self._stock_subscribers[stock_code].add(user_id)
        self._user_stocks[user_id].add(stock_code)

        logger.info(
            "User %s subscribed to %s (total subs: %d)",
            user_id, stock_code, kis_ws.subscription_count,
        )
        return True

    async def unsubscribe(self, user_id: str, stock_code: str):
        """Unsubscribe a user from real-time data for a stock."""
        if stock_code not in self._user_stocks.get(user_id, set()):
            return

        self._stock_subscribers[stock_code].discard(user_id)
        self._user_stocks[user_id].discard(stock_code)

        # If no more subscribers for this stock, unsubscribe from KIS WS
        if not self._stock_subscribers[stock_code]:
            del self._stock_subscribers[stock_code]
            kis_ws = self._sessions.get(user_id)
            if kis_ws:
                try:
                    await kis_ws.unsubscribe(stock_code)
                except Exception:
                    pass

        # If user has no more subscriptions, cleanup session
        if not self._user_stocks[user_id]:
            del self._user_stocks[user_id]
            await self._cleanup_session(user_id)

        logger.debug("User %s unsubscribed from %s", user_id, stock_code)

    async def unsubscribe_all(self, user_id: str):
        """Unsubscribe a user from all stocks and cleanup session."""
        stocks = list(self._user_stocks.get(user_id, set()))
        for stock_code in stocks:
            await self.unsubscribe(user_id, stock_code)

    def is_subscribed(self, stock_code: str) -> bool:
        """Check if any user is subscribed to real-time data for a stock."""
        return bool(self._stock_subscribers.get(stock_code))

    def get_subscriber_count(self, stock_code: str) -> int:
        """Get number of users subscribed to a stock."""
        return len(self._stock_subscribers.get(stock_code, set()))

    async def reload_active_recipes(self, db=None):
        """Refresh stock→recipe mapping from database.

        Called when recipes are activated/deactivated.
        """
        self._stock_recipes.clear()

        if not db:
            return

        try:
            from sqlalchemy import select
            from app.models.trading_recipe import TradingRecipe

            result = await db.execute(
                select(TradingRecipe).where(TradingRecipe.is_active == True)  # noqa: E712
            )
            recipes = result.scalars().all()

            for recipe in recipes:
                for stock_code in (recipe.stock_codes or []):
                    self._stock_recipes[stock_code].append({
                        "recipe_id": str(recipe.id),
                        "user_id": str(recipe.user_id),
                        "name": recipe.name,
                        "signal_config": recipe.signal_config,
                        "custom_filters": recipe.custom_filters,
                    })

            logger.info(
                "Loaded %d active recipes across %d stocks",
                len(recipes), len(self._stock_recipes),
            )
        except Exception as e:
            logger.warning("Failed to reload active recipes: %s", e)

    async def _on_kis_tick(self, tick_data: dict):
        """Handle incoming KIS WebSocket tick.

        Routes to:
        1. All subscribed user WebSocket connections (price_update)
        2. TriggerService for tick buffering
        3. Active recipe evaluation
        """
        stock_code = tick_data.get("stock_code", "")
        if not stock_code:
            return

        # 1. Route to subscribed users via ConnectionManager
        subscribers = self._stock_subscribers.get(stock_code, set())
        if subscribers:
            from app.api.v1.websocket import manager

            price_msg = {
                "type": "price_update",
                "stock_code": stock_code,
                "current_price": tick_data.get("current_price", 0),
                "change": tick_data.get("change", 0),
                "change_percent": tick_data.get("change_percent", 0),
                "volume": tick_data.get("volume", 0),
                "cumulative_volume": tick_data.get("cumulative_volume", 0),
                "timestamp": tick_data.get("exec_time", ""),
            }

            for user_id in subscribers:
                try:
                    await manager.send_to_user(user_id, price_msg)
                except Exception:
                    pass

        # 2. Feed to TriggerService
        self._trigger.add_tick(stock_code, tick_data)

        # 3. Evaluate active recipes for this stock
        recipe_entries = self._stock_recipes.get(stock_code, [])
        if recipe_entries:
            await self._evaluate_recipes(stock_code, recipe_entries)

    async def _evaluate_recipes(self, stock_code: str, recipe_entries: list[dict]):
        """Evaluate active recipes against latest tick data."""
        for entry in recipe_entries:
            result = self._trigger.evaluate_recipe(
                stock_code,
                entry["signal_config"],
                entry.get("custom_filters"),
            )

            if result["should_enter"] or result["should_exit"]:
                signal_type = "entry" if result["should_enter"] else "exit"
                await self._send_recipe_signal(
                    user_id=entry["user_id"],
                    recipe_id=entry["recipe_id"],
                    recipe_name=entry["name"],
                    stock_code=stock_code,
                    signal_type=signal_type,
                )

    async def _send_recipe_signal(
        self, user_id: str, recipe_id: str, recipe_name: str,
        stock_code: str, signal_type: str,
    ):
        """Push recipe signal event to user's WebSocket."""
        from app.api.v1.websocket import manager

        try:
            await manager.send_to_user(user_id, {
                "type": "recipe_signal",
                "recipe_id": recipe_id,
                "recipe_name": recipe_name,
                "stock_code": stock_code,
                "signal_type": signal_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(
                "Recipe signal: %s %s for recipe '%s' stock %s",
                signal_type, recipe_id[:8], recipe_name, stock_code,
            )
        except Exception as e:
            logger.warning("Failed to send recipe signal: %s", e)

    async def _listen_loop(self, user_id: str):
        """Background task: run KIS WebSocket listen loop with cleanup."""
        kis_ws = self._sessions.get(user_id)
        if not kis_ws:
            return

        try:
            await kis_ws.listen()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("KIS WS listen error for user %s: %s", user_id, e)
        finally:
            # Session ended — cleanup
            await self._cleanup_session(user_id)

    async def _cleanup_session(self, user_id: str):
        """Remove KIS WebSocket session and cancel listen task."""
        # Cancel listen task
        task = self._listen_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

        # Disconnect KIS WebSocket
        kis_ws = self._sessions.pop(user_id, None)
        if kis_ws:
            try:
                await kis_ws.disconnect()
            except Exception:
                pass

        self._user_paper.pop(user_id, None)
        logger.info("Cleaned up KIS WS session for user %s", user_id)

    async def shutdown(self):
        """Gracefully shutdown all sessions."""
        user_ids = list(self._sessions.keys())
        for user_id in user_ids:
            await self.unsubscribe_all(user_id)
        self._trigger.clear_buffer()
        logger.info("KISRealtimeManager shut down")


# Singleton instance
_instance: KISRealtimeManager | None = None


def get_realtime_manager() -> KISRealtimeManager:
    """Get the global KISRealtimeManager singleton."""
    global _instance
    if _instance is None:
        _instance = KISRealtimeManager()
    return _instance
