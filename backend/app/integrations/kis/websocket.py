"""KIS WebSocket client for real-time market data.

Supports multiple subscriptions (max 20 per session), auto-reconnect,
and both execution (H0STCNT0) and orderbook (H0STASP0) data types.
"""

import asyncio
import json
import logging
from typing import Callable, Awaitable

import websockets

from app.integrations.kis.constants import (
    REAL_WS_URL, PAPER_WS_URL, REAL_BASE_URL, PAPER_BASE_URL,
    WS_REALTIME_EXEC, WS_REALTIME_ORDERBOOK,
)

logger = logging.getLogger(__name__)


class KISWebSocket:
    """KIS real-time market data WebSocket client.

    Constraints:
    - 1 session per account
    - Max 20 subscriptions per session
    """

    MAX_SUBSCRIPTIONS = 20

    def __init__(self, app_key: str, app_secret: str, is_paper: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.is_paper = is_paper
        self.ws_url = PAPER_WS_URL if is_paper else REAL_WS_URL
        self._ws = None
        self._running = False
        self._approval_key: str | None = None
        self._subscriptions: set[str] = set()
        self._callbacks: list[Callable[[dict], Awaitable[None]]] = []

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    async def _get_approval_key(self) -> str:
        """Get WebSocket approval key from KIS API."""
        import httpx

        base = PAPER_BASE_URL if self.is_paper else REAL_BASE_URL
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base}/oauth2/Approval",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "secretkey": self.app_secret,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()["approval_key"]

    async def connect(self):
        """Establish WebSocket connection."""
        self._approval_key = await self._get_approval_key()
        self._ws = await websockets.connect(self.ws_url, ping_interval=30)
        self._running = True
        logger.info(f"Connected to KIS WebSocket: {self.ws_url}")

    async def disconnect(self):
        """Close WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._subscriptions.clear()
        logger.info("Disconnected from KIS WebSocket")

    def on_message(self, callback: Callable[[dict], Awaitable[None]]):
        """Register a callback for incoming real-time data."""
        self._callbacks.append(callback)

    async def subscribe(self, stock_code: str, data_type: str = WS_REALTIME_EXEC):
        """Subscribe to real-time data for a stock.

        Args:
            stock_code: Stock code (e.g., "005930")
            data_type: H0STCNT0 (execution) or H0STASP0 (orderbook)
        """
        sub_key = f"{data_type}:{stock_code}"
        if sub_key in self._subscriptions:
            return

        if self.subscription_count >= self.MAX_SUBSCRIPTIONS:
            raise RuntimeError(
                f"Maximum subscriptions ({self.MAX_SUBSCRIPTIONS}) reached. "
                "Unsubscribe from existing stocks first."
            )

        if not self._ws:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        msg = json.dumps({
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": "1",  # 1=subscribe
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": data_type,
                    "tr_key": stock_code,
                }
            }
        })
        await self._ws.send(msg)
        self._subscriptions.add(sub_key)
        logger.info(f"Subscribed to {sub_key} ({self.subscription_count}/{self.MAX_SUBSCRIPTIONS})")

    async def unsubscribe(self, stock_code: str, data_type: str = WS_REALTIME_EXEC):
        """Unsubscribe from real-time data."""
        sub_key = f"{data_type}:{stock_code}"
        if sub_key not in self._subscriptions:
            return

        if not self._ws:
            return

        msg = json.dumps({
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": "2",  # 2=unsubscribe
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": data_type,
                    "tr_key": stock_code,
                }
            }
        })
        await self._ws.send(msg)
        self._subscriptions.discard(sub_key)
        logger.info(f"Unsubscribed from {sub_key}")

    async def subscribe_price(
        self,
        stock_code: str,
        callback: Callable[[dict], Awaitable[None]],
    ):
        """Subscribe to real-time price for a stock (legacy single-stock API)."""
        if not self._approval_key:
            self._approval_key = await self._get_approval_key()

        self._running = True
        async with websockets.connect(self.ws_url, ping_interval=30) as ws:
            self._ws = ws

            subscribe_msg = json.dumps({
                "header": {
                    "approval_key": self._approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {
                        "tr_id": WS_REALTIME_EXEC,
                        "tr_key": stock_code,
                    }
                },
            })
            await ws.send(subscribe_msg)

            while self._running:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = self._parse_price_message(message)
                    if data:
                        await callback(data)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    break

    async def listen(self):
        """Main loop: receive and process messages with auto-reconnect."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        retry_count = 0
        max_retries = 5

        while self._running:
            try:
                async for message in self._ws:
                    await self._process_message(message)
                    retry_count = 0
            except Exception as e:
                if not self._running:
                    break
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Max retries exceeded: {e}")
                    break
                wait = min(2 ** retry_count, 30)
                logger.warning(f"WS disconnected: {e}. Reconnecting in {wait}s...")
                await asyncio.sleep(wait)
                try:
                    await self.connect()
                    # Re-subscribe to all previous subscriptions
                    subs = list(self._subscriptions)
                    self._subscriptions.clear()
                    for sub_key in subs:
                        data_type, stock_code = sub_key.split(":", 1)
                        await self.subscribe(stock_code, data_type)
                except Exception as re_err:
                    logger.error(f"Reconnect failed: {re_err}")

    async def _process_message(self, raw: str):
        """Parse and dispatch incoming WebSocket message."""
        if raw.startswith("{"):
            logger.debug(f"WS JSON: {raw[:200]}")
            return

        parts = raw.split("|")
        if len(parts) < 4:
            return

        tr_id = parts[1]
        body = parts[3]

        parsed = self._parse_realtime_data(tr_id, body)
        if parsed:
            for cb in self._callbacks:
                try:
                    await cb(parsed)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

    def _parse_realtime_data(self, tr_id: str, body: str) -> dict | None:
        """Parse real-time data body based on tr_id."""
        fields = body.split("^")

        if tr_id == WS_REALTIME_EXEC and len(fields) >= 15:
            return {
                "type": "execution",
                "stock_code": fields[0],
                "exec_time": fields[1],
                "current_price": float(fields[2]) if fields[2] else 0,
                "change": float(fields[4]) if fields[4] else 0,
                "change_percent": float(fields[5]) if fields[5] else 0,
                "volume": int(fields[9]) if fields[9] else 0,
                "cumulative_volume": int(fields[13]) if fields[13] else 0,
            }
        elif tr_id == WS_REALTIME_ORDERBOOK and len(fields) >= 25:
            return {
                "type": "orderbook",
                "stock_code": fields[0],
                "best_ask": float(fields[3]) if fields[3] else 0,
                "best_bid": float(fields[13]) if fields[13] else 0,
                "total_ask_volume": int(fields[23]) if fields[23] else 0,
                "total_bid_volume": int(fields[24]) if fields[24] else 0,
            }

        return None

    def _parse_price_message(self, raw: str) -> dict | None:
        """Parse KIS WebSocket price data (legacy format)."""
        try:
            if raw.startswith("{"):
                return None

            parts = raw.split("|")
            if len(parts) < 4:
                return None

            fields = parts[3].split("^")
            if len(fields) < 15:
                return None

            return {
                "stock_code": fields[0],
                "time": fields[1],
                "current_price": float(fields[2]),
                "change": float(fields[4]),
                "change_percent": float(fields[5]),
                "volume": int(fields[9]),
                "cumulative_volume": int(fields[13]),
            }
        except (IndexError, ValueError):
            return None
