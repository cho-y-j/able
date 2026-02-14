"""Tests for execution engine, smart router, TWAP, VWAP, slippage, and execution node."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.execution.slippage import SlippageTracker, SlippageResult
from app.execution.smart_router import SmartOrderRouter, OrderRouting
from app.execution.twap import calculate_twap_slices, execute_twap, TWAPResult
from app.execution.vwap import (
    calculate_vwap_slices,
    execute_vwap,
    VWAPResult,
    DEFAULT_KRX_VOLUME_PROFILE,
)
from app.execution.engine import ExecutionEngine, ExecutionResult
from app.agents.nodes.execution import execution_node, _dry_run_execution
from app.agents.nodes.monitor import monitor_node, _check_order_fill


# ── Helpers ──────────────────────────────────────────────────


def _make_kis_client(price=50000, volume=1_000_000, orderbook=None, order_success=True):
    """Create a mock KIS client."""
    client = AsyncMock()
    client.get_price = AsyncMock(return_value={
        "stock_code": "005930",
        "current_price": price,
        "volume": volume,
        "high": price * 1.02,
        "low": price * 0.98,
        "open": price * 0.99,
    })
    client.get_orderbook = AsyncMock(return_value=orderbook or {
        "stock_code": "005930",
        "best_ask": price * 1.001,
        "best_bid": price * 0.999,
        "ask_volume_1": 10000,
        "bid_volume_1": 10000,
        "total_ask_volume": 50000,
        "total_bid_volume": 50000,
    })
    client.place_order = AsyncMock(return_value={
        "kis_order_id": "ORD12345",
        "order_time": "120000",
        "success": order_success,
        "message": "OK" if order_success else "Insufficient balance",
    })
    client.get_balance = AsyncMock(return_value={
        "total_balance": 10_000_000,
        "available_cash": 5_000_000,
    })
    return client


def _make_state(**overrides) -> dict:
    state = {
        "messages": [],
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "market_regime": {"classification": "bull", "confidence": 0.8, "indicators": {}, "timestamp": ""},
        "watchlist": ["005930"],
        "strategy_candidates": [],
        "optimization_status": "",
        "risk_assessment": None,
        "pending_orders": [],
        "executed_orders": [],
        "portfolio_snapshot": {},
        "alerts": [],
        "current_agent": "",
        "iteration_count": 0,
        "should_continue": True,
        "error_state": None,
        "pending_approval": False,
        "pending_trades": [],
        "approval_status": None,
        "approval_threshold": 5_000_000,
        "hitl_enabled": False,
        "memory_context": "",
        "execution_config": None,
        "slippage_report": [],
        "_kis_client": None,
    }
    state.update(overrides)
    return state


# ── SlippageTracker tests ────────────────────────────────────


class TestSlippageTracker:
    def test_buy_unfavorable_slippage(self):
        result = SlippageTracker.calculate(50000, 50050, "buy")
        assert result.slippage_bps > 0  # Paid more than expected
        assert result.slippage_bps == pytest.approx(10.0, abs=0.1)

    def test_buy_favorable_slippage(self):
        result = SlippageTracker.calculate(50000, 49950, "buy")
        assert result.slippage_bps < 0  # Paid less

    def test_sell_unfavorable_slippage(self):
        result = SlippageTracker.calculate(50000, 49950, "sell")
        assert result.slippage_bps > 0  # Received less

    def test_sell_favorable_slippage(self):
        result = SlippageTracker.calculate(50000, 50050, "sell")
        assert result.slippage_bps < 0  # Received more

    def test_zero_expected_price(self):
        result = SlippageTracker.calculate(0, 50000, "buy")
        assert result.slippage_bps == 0.0


# ── SmartOrderRouter tests ───────────────────────────────────


class TestSmartOrderRouter:
    def test_market_order_tight_spread_small_depth(self):
        """Tight spread + low depth → market order."""
        result = SmartOrderRouter.route(
            quantity=100, side="buy", current_price=50000,
            avg_daily_volume=1_000_000,
            best_bid=49990, best_ask=50010,
        )
        assert result.execution_strategy == "direct"
        assert result.order_type == "market"

    def test_limit_order_moderate_spread(self):
        """Wider spread → limit order."""
        result = SmartOrderRouter.route(
            quantity=10000, side="buy", current_price=50000,
            avg_daily_volume=1_000_000,
            best_bid=49900, best_ask=50100,
        )
        assert result.execution_strategy == "direct"
        assert result.order_type == "limit"
        assert result.limit_price > 0

    def test_twap_for_large_order(self):
        """depth >= 5% → TWAP."""
        result = SmartOrderRouter.route(
            quantity=60000, side="buy", current_price=50000,
            avg_daily_volume=1_000_000,
            best_bid=49990, best_ask=50010,
        )
        assert result.execution_strategy == "twap"
        assert result.num_slices == 5

    def test_vwap_for_very_large_order(self):
        """depth >= 10% → VWAP."""
        result = SmartOrderRouter.route(
            quantity=150000, side="buy", current_price=50000,
            avg_daily_volume=1_000_000,
            best_bid=49990, best_ask=50010,
        )
        assert result.execution_strategy == "vwap"
        assert result.num_slices == 9

    def test_no_orderbook_fallback(self):
        """No bid/ask → uses current_price for limit."""
        result = SmartOrderRouter.route(
            quantity=10000, side="sell", current_price=50000,
            avg_daily_volume=1_000_000,
        )
        assert result.execution_strategy == "direct"


# ── TWAP tests ───────────────────────────────────────────────


class TestTWAP:
    def test_calculate_twap_slices_even(self):
        slices = calculate_twap_slices(100, 5)
        assert sum(slices) == 100
        assert len(slices) == 5
        assert slices == [20, 20, 20, 20, 20]

    def test_calculate_twap_slices_remainder(self):
        slices = calculate_twap_slices(103, 5)
        assert sum(slices) == 103
        assert len(slices) == 5
        assert slices[0] > slices[-1]  # remainder distributed to first slices

    def test_calculate_twap_single_slice(self):
        slices = calculate_twap_slices(50, 1)
        assert slices == [50]

    @pytest.mark.asyncio
    async def test_execute_twap_success(self):
        client = _make_kis_client()
        result = await execute_twap(
            client, "005930", "buy", 100, num_slices=3, interval_seconds=0,
        )
        assert isinstance(result, TWAPResult)
        assert result.filled_quantity == 100
        assert result.num_slices == 3
        assert len(result.slices) == 3
        assert result.success_rate == 1.0
        assert client.place_order.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_twap_partial_failure(self):
        client = _make_kis_client()
        # Second order fails
        client.place_order.side_effect = [
            {"kis_order_id": "O1", "success": True, "message": "OK"},
            {"kis_order_id": "O2", "success": False, "message": "Failed"},
            {"kis_order_id": "O3", "success": True, "message": "OK"},
        ]
        result = await execute_twap(
            client, "005930", "buy", 90, num_slices=3, interval_seconds=0,
        )
        assert result.filled_quantity == 60  # 30+30, middle failed
        assert result.success_rate == pytest.approx(2 / 3, abs=0.01)


# ── VWAP tests ───────────────────────────────────────────────


class TestVWAP:
    def test_calculate_vwap_slices_total(self):
        slices = calculate_vwap_slices(1000)
        total_qty = sum(q for _, q in slices)
        assert total_qty == 1000

    def test_calculate_vwap_slices_count(self):
        slices = calculate_vwap_slices(1000)
        assert len(slices) == len(DEFAULT_KRX_VOLUME_PROFILE)

    def test_calculate_vwap_weights_proportional(self):
        """Opening bucket (15%) should get more qty than lunch (8%)."""
        slices = calculate_vwap_slices(1000)
        opening_qty = slices[0][1]
        lunch_qty = slices[4][1]
        assert opening_qty > lunch_qty

    @pytest.mark.asyncio
    async def test_execute_vwap_success(self):
        client = _make_kis_client()
        result = await execute_vwap(
            client, "005930", "buy", 100,
            volume_profile=[0.5, 0.3, 0.2], interval_seconds=0,
        )
        assert isinstance(result, VWAPResult)
        assert result.filled_quantity == 100
        assert result.num_slices == 3
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_execute_vwap_exception_in_slice(self):
        client = _make_kis_client()
        client.get_price.side_effect = [
            {"current_price": 50000, "stock_code": "005930", "volume": 1000000},
            Exception("API timeout"),
            {"current_price": 50000, "stock_code": "005930", "volume": 1000000},
        ]
        result = await execute_vwap(
            client, "005930", "buy", 100,
            volume_profile=[0.5, 0.3, 0.2], interval_seconds=0,
        )
        # One slice failed due to exception
        failed = [s for s in result.slices if not s.success]
        assert len(failed) >= 1


# ── ExecutionEngine tests ────────────────────────────────────


class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_direct_execution(self):
        client = _make_kis_client()
        engine = ExecutionEngine(client)
        result = await engine.execute("005930", "buy", 100)
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.execution_strategy == "direct"

    @pytest.mark.asyncio
    async def test_price_fetch_failure(self):
        client = _make_kis_client()
        client.get_price.side_effect = Exception("Network error")
        engine = ExecutionEngine(client)
        result = await engine.execute("005930", "buy", 100)
        assert result.success is False
        assert "Failed to get price" in result.error_message

    @pytest.mark.asyncio
    @patch("app.execution.twap.asyncio.sleep", new_callable=AsyncMock)
    async def test_strategy_override_twap(self, mock_sleep):
        client = _make_kis_client()
        engine = ExecutionEngine(client)
        result = await engine.execute(
            "005930", "buy", 100, strategy_override="twap",
        )
        assert result.execution_strategy == "twap"


# ── Execution Node tests ─────────────────────────────────────


class TestExecutionNode:
    @pytest.mark.asyncio
    async def test_no_approved_trades_skips(self):
        state = _make_state(risk_assessment={"approved_trades": []})
        result = await execution_node(state)
        assert "No approved trades" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_dry_run_without_kis_client(self):
        state = _make_state(
            risk_assessment={"approved_trades": ["005930"]},
            strategy_candidates=[{
                "stock_code": "005930",
                "strategy_name": "sma_crossover",
                "position_sizing": {"shares": 10},
            }],
        )
        result = await execution_node(state)
        assert "DRY RUN" in result["messages"][0].content
        assert len(result["pending_orders"]) == 1
        assert result["pending_orders"][0]["execution_strategy"] == "dry_run"

    @pytest.mark.asyncio
    @patch("app.execution.twap.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.execution.vwap.asyncio.sleep", new_callable=AsyncMock)
    async def test_kis_execution_success(self, _mock_vwap_sleep, _mock_twap_sleep):
        client = _make_kis_client()
        state = _make_state(
            _kis_client=client,
            risk_assessment={"approved_trades": ["005930"]},
            strategy_candidates=[{
                "stock_code": "005930",
                "strategy_name": "sma_crossover",
                "position_sizing": {"shares": 10},
            }],
        )
        result = await execution_node(state)
        assert "Submitted 1 orders" in result["messages"][0].content
        assert len(result["pending_orders"]) == 1
        assert result["pending_orders"][0]["status"] == "submitted"

    @pytest.mark.asyncio
    @patch("app.execution.twap.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.execution.vwap.asyncio.sleep", new_callable=AsyncMock)
    async def test_kis_execution_failure(self, _mock_vwap_sleep, _mock_twap_sleep):
        client = _make_kis_client(order_success=False)
        state = _make_state(
            _kis_client=client,
            risk_assessment={"approved_trades": ["005930"]},
            strategy_candidates=[{
                "stock_code": "005930",
                "strategy_name": "sma_crossover",
                "position_sizing": {"shares": 10},
            }],
        )
        result = await execution_node(state)
        assert "1 failed" in result["messages"][0].content


# ── Monitor Node tests ────────────────────────────────────────


class TestMonitorNode:
    @pytest.mark.asyncio
    async def test_dry_run_orders_auto_filled(self):
        state = _make_state(
            pending_orders=[{"order_id": "DRY_005930", "status": "dry_run"}],
        )
        result = await monitor_node(state)
        assert len(result["pending_orders"]) == 0
        assert len(result["executed_orders"]) == 1
        assert result["executed_orders"][0]["status"] == "dry_run_filled"

    @pytest.mark.asyncio
    async def test_submitted_orders_filled_without_kis(self):
        state = _make_state(
            pending_orders=[{"order_id": "ORD1", "status": "submitted"}],
        )
        result = await monitor_node(state)
        assert len(result["executed_orders"]) == 1
        assert result["executed_orders"][0]["status"] == "filled"

    @pytest.mark.asyncio
    async def test_submitted_orders_filled_with_kis(self):
        client = _make_kis_client()
        state = _make_state(
            _kis_client=client,
            pending_orders=[{
                "order_id": "ORD1",
                "status": "submitted",
                "kis_order_id": "KIS123",
            }],
        )
        result = await monitor_node(state)
        assert len(result["executed_orders"]) == 1
        assert result["executed_orders"][0]["status"] == "filled"

    @pytest.mark.asyncio
    async def test_iteration_limit_stops(self):
        state = _make_state(iteration_count=48)
        result = await monitor_node(state)
        assert result["should_continue"] is False
        assert any("iteration limit" in a for a in result["alerts"])
