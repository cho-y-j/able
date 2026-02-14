import json
import asyncio
import websockets
from typing import Callable, Awaitable

from app.integrations.kis.constants import REAL_WS_URL, PAPER_WS_URL


class KISWebSocket:
    """KIS real-time price streaming via WebSocket."""

    def __init__(self, app_key: str, app_secret: str, is_paper: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.ws_url = PAPER_WS_URL if is_paper else REAL_WS_URL
        self._ws = None
        self._running = False
        self._approval_key: str | None = None

    async def _get_approval_key(self) -> str:
        """Get WebSocket approval key from KIS API."""
        import httpx
        from app.integrations.kis.constants import REAL_BASE_URL, PAPER_BASE_URL

        base = PAPER_BASE_URL if "31000" in self.ws_url else REAL_BASE_URL
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

    async def subscribe_price(
        self,
        stock_code: str,
        callback: Callable[[dict], Awaitable[None]],
    ):
        """Subscribe to real-time price for a stock."""
        if not self._approval_key:
            self._approval_key = await self._get_approval_key()

        self._running = True
        async with websockets.connect(self.ws_url, ping_interval=30) as ws:
            self._ws = ws

            # Subscribe message
            subscribe_msg = json.dumps({
                "header": {
                    "approval_key": self._approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",
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

    def _parse_price_message(self, raw: str) -> dict | None:
        """Parse KIS WebSocket price data."""
        try:
            if raw.startswith("{"):
                return None  # Control message

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

    async def disconnect(self):
        self._running = False
        if self._ws:
            await self._ws.close()
