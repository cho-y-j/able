"""Tests for the KIS WebSocket client (real-time market data)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.kis.websocket import KISWebSocket
from app.integrations.kis.constants import (
    PAPER_WS_URL,
    REAL_WS_URL,
    WS_REALTIME_EXEC,
    WS_REALTIME_ORDERBOOK,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def paper_ws():
    """Create a KISWebSocket in paper mode."""
    return KISWebSocket(app_key="test_key", app_secret="test_secret", is_paper=True)


@pytest.fixture
def real_ws():
    """Create a KISWebSocket in real mode."""
    return KISWebSocket(app_key="test_key", app_secret="test_secret", is_paper=False)


@pytest.fixture
def connected_ws(paper_ws):
    """Paper-mode KISWebSocket with a mocked _ws connection."""
    paper_ws._ws = AsyncMock()
    paper_ws._approval_key = "fake-approval-key"
    paper_ws._running = True
    return paper_ws


def _build_exec_body(
    stock_code="005930",
    time="130500",
    price="72000",
    change="500",
    change_pct="0.70",
    volume="100000",
    cum_vol="5000000",
):
    """Build a pipe-delimited execution body with at least 15 ^-separated fields."""
    fields = [
        stock_code,   # 0: stock_code
        time,         # 1: exec_time
        price,        # 2: current_price
        "0",          # 3: placeholder
        change,       # 4: change
        change_pct,   # 5: change_percent
        "0",          # 6
        "0",          # 7
        "0",          # 8
        volume,       # 9: volume
        "0",          # 10
        "0",          # 11
        "0",          # 12
        cum_vol,      # 13: cumulative_volume
        "0",          # 14
    ]
    return "^".join(fields)


def _build_orderbook_body(
    stock_code="005930",
    best_ask="72100",
    best_bid="72000",
    total_ask_vol="300000",
    total_bid_vol="250000",
):
    """Build a ^-separated orderbook body with at least 25 fields."""
    fields = ["0"] * 25
    fields[0] = stock_code
    fields[3] = best_ask
    fields[13] = best_bid
    fields[23] = total_ask_vol
    fields[24] = total_bid_vol
    return "^".join(fields)


def _build_raw_message(tr_id, body):
    """Build the full pipe-delimited WebSocket message: enc|tr_id|count|body."""
    return f"0|{tr_id}|1|{body}"


# ── Initialization ───────────────────────────────────────


class TestKISWebSocketInit:
    def test_init_paper_mode(self, paper_ws):
        assert paper_ws.ws_url == PAPER_WS_URL
        assert paper_ws.is_paper is True
        assert paper_ws.app_key == "test_key"
        assert paper_ws._ws is None
        assert paper_ws._running is False

    def test_init_real_mode(self, real_ws):
        assert real_ws.ws_url == REAL_WS_URL
        assert real_ws.is_paper is False

    def test_subscription_count_starts_at_zero(self, paper_ws):
        assert paper_ws.subscription_count == 0
        assert len(paper_ws._subscriptions) == 0
        assert len(paper_ws._callbacks) == 0


# ── Subscribe / Unsubscribe ──────────────────────────────


class TestSubscription:
    @pytest.mark.asyncio
    async def test_subscribe_raises_without_connection(self, paper_ws):
        """subscribe() should raise when _ws is None."""
        with pytest.raises(RuntimeError, match="WebSocket not connected"):
            await paper_ws.subscribe("005930")

    @pytest.mark.asyncio
    async def test_max_subscriptions_limit(self, connected_ws):
        """After 20 subscriptions the 21st should raise."""
        ws = connected_ws
        for i in range(KISWebSocket.MAX_SUBSCRIPTIONS):
            stock_code = f"{i:06d}"
            await ws.subscribe(stock_code)

        assert ws.subscription_count == 20

        with pytest.raises(RuntimeError, match="Maximum subscriptions"):
            await ws.subscribe("999999")

    @pytest.mark.asyncio
    async def test_subscribe_sends_json_message(self, connected_ws):
        """subscribe() should send a correctly formatted JSON message."""
        await connected_ws.subscribe("005930", WS_REALTIME_EXEC)

        connected_ws._ws.send.assert_awaited_once()
        sent_raw = connected_ws._ws.send.call_args[0][0]
        sent = json.loads(sent_raw)

        assert sent["header"]["tr_type"] == "1"
        assert sent["body"]["input"]["tr_id"] == WS_REALTIME_EXEC
        assert sent["body"]["input"]["tr_key"] == "005930"

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_is_noop(self, connected_ws):
        """Subscribing to the same stock+type twice should not send twice."""
        await connected_ws.subscribe("005930")
        await connected_ws.subscribe("005930")

        assert connected_ws.subscription_count == 1
        assert connected_ws._ws.send.await_count == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self, connected_ws):
        """unsubscribe() should remove the sub_key and send tr_type=2."""
        await connected_ws.subscribe("005930")
        assert connected_ws.subscription_count == 1

        await connected_ws.unsubscribe("005930")
        assert connected_ws.subscription_count == 0

        # Second call to send should be the unsubscribe message
        unsub_raw = connected_ws._ws.send.call_args[0][0]
        unsub = json.loads(unsub_raw)
        assert unsub["header"]["tr_type"] == "2"


# ── Parsing ──────────────────────────────────────────────


class TestParsing:
    def test_parse_realtime_exec_data(self, paper_ws):
        body = _build_exec_body(
            stock_code="005930",
            time="130500",
            price="72000",
            change="500",
            change_pct="0.70",
            volume="100000",
            cum_vol="5000000",
        )
        result = paper_ws._parse_realtime_data(WS_REALTIME_EXEC, body)

        assert result is not None
        assert result["type"] == "execution"
        assert result["stock_code"] == "005930"
        assert result["exec_time"] == "130500"
        assert result["current_price"] == 72000.0
        assert result["change"] == 500.0
        assert result["change_percent"] == 0.70
        assert result["volume"] == 100000
        assert result["cumulative_volume"] == 5000000

    def test_parse_realtime_orderbook_data(self, paper_ws):
        body = _build_orderbook_body(
            stock_code="005930",
            best_ask="72100",
            best_bid="72000",
            total_ask_vol="300000",
            total_bid_vol="250000",
        )
        result = paper_ws._parse_realtime_data(WS_REALTIME_ORDERBOOK, body)

        assert result is not None
        assert result["type"] == "orderbook"
        assert result["stock_code"] == "005930"
        assert result["best_ask"] == 72100.0
        assert result["best_bid"] == 72000.0
        assert result["total_ask_volume"] == 300000
        assert result["total_bid_volume"] == 250000

    def test_parse_realtime_data_returns_none_for_short_body(self, paper_ws):
        """Body with fewer fields than required should return None."""
        short_body = "^".join(["0"] * 5)
        assert paper_ws._parse_realtime_data(WS_REALTIME_EXEC, short_body) is None
        assert paper_ws._parse_realtime_data(WS_REALTIME_ORDERBOOK, short_body) is None

    def test_parse_realtime_data_returns_none_for_unknown_tr_id(self, paper_ws):
        body = _build_exec_body()
        assert paper_ws._parse_realtime_data("UNKNOWN_TR", body) is None

    def test_parse_price_message_json_returns_none(self, paper_ws):
        """JSON messages (control frames) should return None."""
        json_msg = json.dumps({"header": {"tr_id": "PINGPONG"}})
        assert paper_ws._parse_price_message(json_msg) is None

    def test_parse_price_message_valid(self, paper_ws):
        body = _build_exec_body()
        raw = _build_raw_message(WS_REALTIME_EXEC, body)
        result = paper_ws._parse_price_message(raw)

        assert result is not None
        assert result["stock_code"] == "005930"
        assert result["current_price"] == 72000.0
        assert result["volume"] == 100000

    def test_parse_price_message_short_parts_returns_none(self, paper_ws):
        """Raw message with < 4 pipe-separated parts returns None."""
        assert paper_ws._parse_price_message("too|short") is None


# ── Callbacks ────────────────────────────────────────────


class TestCallbacks:
    def test_on_message_registers_callback(self, paper_ws):
        async def my_callback(data):
            pass

        paper_ws.on_message(my_callback)
        assert len(paper_ws._callbacks) == 1
        assert paper_ws._callbacks[0] is my_callback

    def test_on_message_multiple_callbacks(self, paper_ws):
        async def cb1(data):
            pass

        async def cb2(data):
            pass

        paper_ws.on_message(cb1)
        paper_ws.on_message(cb2)
        assert len(paper_ws._callbacks) == 2
