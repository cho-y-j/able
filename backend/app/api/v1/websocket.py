"""WebSocket endpoints for real-time updates."""

import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_token

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections per user."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id] = [
                ws for ws in self.active_connections[user_id] if ws != websocket
            ]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            data = json.dumps(message, default=str)
            dead: list[WebSocket] = []
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_text(data)
                except Exception as e:
                    logger.warning("WS send failed for user %s: %s", user_id, e)
                    dead.append(ws)
            # Clean up dead connections
            for ws in dead:
                self.disconnect(ws, user_id)

    async def broadcast(self, message: dict):
        data = json.dumps(message, default=str)
        for user_id, connections in list(self.active_connections.items()):
            for ws in connections:
                try:
                    await ws.send_text(data)
                except Exception as e:
                    logger.warning("WS broadcast failed for user %s: %s", user_id, e)
                    self.disconnect(ws, user_id)


manager = ConnectionManager()


def _authenticate_ws(token: str) -> str | None:
    """Validate token and return user_id."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    return payload.get("sub")


@router.websocket("/trading")
async def trading_websocket(websocket: WebSocket, token: str = Query(...)):
    user_id = _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # Handle ping/pong
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)


@router.websocket("/agents")
async def agents_websocket(websocket: WebSocket, token: str = Query(...)):
    user_id = _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)


@router.websocket("/market/{stock_code}")
async def market_websocket(websocket: WebSocket, stock_code: str, token: str = Query(...)):
    """Real-time price stream for a stock.

    Tries KIS WebSocket for true real-time data.
    Falls back to REST API polling if KIS WS unavailable.
    """
    user_id = _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_id)
    price_task: asyncio.Task | None = None
    using_realtime = False

    try:
        # Try KIS WebSocket first
        using_realtime = await _try_realtime_subscribe(user_id, stock_code)

        if not using_realtime:
            # Fallback to REST polling
            price_task = asyncio.create_task(
                _stream_price(websocket, user_id, stock_code)
            )

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg.get("type") == "subscribe":
                # Client can switch stocks dynamically
                new_code = msg.get("stock_code")
                if new_code and new_code != stock_code:
                    old_code = stock_code
                    stock_code = new_code

                    if using_realtime:
                        from app.services.realtime_manager import get_realtime_manager
                        mgr = get_realtime_manager()
                        await mgr.unsubscribe(user_id, old_code)
                        using_realtime = await _try_realtime_subscribe(user_id, stock_code)

                    if not using_realtime:
                        if price_task:
                            price_task.cancel()
                        price_task = asyncio.create_task(
                            _stream_price(websocket, user_id, stock_code)
                        )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if price_task:
            price_task.cancel()
        if using_realtime:
            from app.services.realtime_manager import get_realtime_manager
            mgr = get_realtime_manager()
            await mgr.unsubscribe(user_id, stock_code)
        manager.disconnect(websocket, user_id)


async def _try_realtime_subscribe(user_id: str, stock_code: str) -> bool:
    """Try to subscribe via KIS WebSocket. Returns True on success."""
    try:
        from app.services.realtime_manager import get_realtime_manager
        from app.db.session import async_session_factory
        from app.services.kis_service import get_kis_client

        mgr = get_realtime_manager()

        # Get KIS credentials from cached client
        async with async_session_factory() as db:
            kis = await get_kis_client(user_id, db)

        return await mgr.subscribe(
            user_id=user_id,
            stock_code=stock_code,
            is_paper=kis.is_paper,
            app_key=kis.token_manager.app_key,
            app_secret=kis.token_manager.app_secret,
        )
    except Exception:
        return False


async def _stream_price(websocket: WebSocket, user_id: str, stock_code: str):
    """Poll KIS price API every 5s and push to WebSocket client."""
    import logging
    from app.db.session import async_session_factory
    from app.services.kis_service import get_kis_client

    logger = logging.getLogger(__name__)

    try:
        async with async_session_factory() as db:
            kis = await get_kis_client(user_id, db)

        while True:
            try:
                async with async_session_factory() as db:
                    kis = await get_kis_client(user_id, db)
                    price = await kis.get_price(stock_code)

                await websocket.send_text(json.dumps({
                    "type": "price_update",
                    "stock_code": stock_code,
                    "current_price": price.get("current_price", 0),
                    "change": price.get("change", 0),
                    "change_percent": price.get("change_percent", 0),
                    "volume": price.get("volume", 0),
                    "high": price.get("high", 0),
                    "low": price.get("low", 0),
                    "timestamp": price.get("time", ""),
                }, default=str))
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Price stream error for {stock_code}: {e}")
                # Send error but don't break — keep trying
                try:
                    await websocket.send_text(json.dumps({
                        "type": "price_error",
                        "stock_code": stock_code,
                        "message": str(e),
                    }))
                except Exception:
                    return

            await asyncio.sleep(1)  # 1초 간격 실시간 시세
    except asyncio.CancelledError:
        return
