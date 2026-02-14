"""Order execution engine with configurable strategies."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.execution.smart_router import SmartOrderRouter, OrderRouting
from app.execution.slippage import SlippageTracker, SlippageResult
from app.execution.twap import execute_twap, TWAPResult
from app.execution.vwap import execute_vwap, VWAPResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    stock_code: str
    side: str
    total_quantity: int
    execution_strategy: str  # direct, twap, vwap
    kis_order_id: str | None
    success: bool
    fill_price: float
    expected_price: float
    slippage: SlippageResult | None
    child_orders: list[dict]
    error_message: str | None = None


class ExecutionEngine:
    """Coordinates order execution with smart routing and slippage tracking."""

    def __init__(self, kis_client):
        self.kis = kis_client
        self.router = SmartOrderRouter()
        self.slippage = SlippageTracker()

    async def execute(
        self,
        stock_code: str,
        side: str,
        quantity: int,
        strategy_override: str | None = None,
    ) -> ExecutionResult:
        """Execute an order with automatic strategy selection.

        Args:
            stock_code: KRX stock code
            side: "buy" or "sell"
            quantity: Number of shares
            strategy_override: Force "direct", "twap", or "vwap" (skip routing)
        """
        # Get market data for routing decision
        try:
            price_data = await self.kis.get_price(stock_code)
        except Exception as e:
            return ExecutionResult(
                stock_code=stock_code, side=side, total_quantity=quantity,
                execution_strategy="failed", kis_order_id=None, success=False,
                fill_price=0, expected_price=0, slippage=None, child_orders=[],
                error_message=f"Failed to get price: {e}",
            )

        current_price = price_data["current_price"]
        volume = price_data.get("volume", 0)

        # Get orderbook for spread data (best-effort)
        best_bid, best_ask = 0.0, 0.0
        try:
            orderbook = await self.kis.get_orderbook(stock_code)
            best_bid = orderbook.get("best_bid", 0)
            best_ask = orderbook.get("best_ask", 0)
        except Exception:
            pass

        # Route order
        if strategy_override:
            routing = OrderRouting(
                execution_strategy=strategy_override,
                order_type="limit" if strategy_override != "direct" else "market",
                limit_price=None,
                num_slices=5 if strategy_override == "twap" else 9 if strategy_override == "vwap" else 1,
                reasoning=f"Manual override: {strategy_override}",
            )
        else:
            routing = self.router.route(
                quantity=quantity,
                side=side,
                current_price=current_price,
                avg_daily_volume=volume,
                best_bid=best_bid,
                best_ask=best_ask,
            )

        logger.info(
            f"Execution routing for {side} {quantity} {stock_code}: "
            f"{routing.execution_strategy} ({routing.reasoning})"
        )

        # Execute based on routing
        if routing.execution_strategy == "twap":
            return await self._execute_twap(stock_code, side, quantity, current_price, routing)
        elif routing.execution_strategy == "vwap":
            return await self._execute_vwap(stock_code, side, quantity, current_price, routing)
        else:
            return await self._execute_direct(stock_code, side, quantity, current_price, routing)

    async def _execute_direct(
        self, stock_code: str, side: str, quantity: int,
        expected_price: float, routing: OrderRouting,
    ) -> ExecutionResult:
        """Submit a single order directly to KIS."""
        try:
            price = routing.limit_price or 0
            kis_result = await self.kis.place_order(
                stock_code=stock_code,
                side=side,
                quantity=quantity,
                price=price,
                order_type=routing.order_type,
            )

            success = kis_result.get("success", False)
            fill_price = float(price) if price > 0 else expected_price

            slippage = self.slippage.calculate(expected_price, fill_price, side) if success else None

            return ExecutionResult(
                stock_code=stock_code,
                side=side,
                total_quantity=quantity,
                execution_strategy="direct",
                kis_order_id=kis_result.get("kis_order_id"),
                success=success,
                fill_price=fill_price,
                expected_price=expected_price,
                slippage=slippage,
                child_orders=[],
                error_message=kis_result.get("message") if not success else None,
            )
        except Exception as e:
            logger.error(f"Direct execution failed: {e}")
            return ExecutionResult(
                stock_code=stock_code, side=side, total_quantity=quantity,
                execution_strategy="direct", kis_order_id=None, success=False,
                fill_price=0, expected_price=expected_price, slippage=None,
                child_orders=[], error_message=str(e),
            )

    async def _execute_twap(
        self, stock_code: str, side: str, quantity: int,
        expected_price: float, routing: OrderRouting,
    ) -> ExecutionResult:
        """Execute via TWAP strategy."""
        try:
            twap_result: TWAPResult = await execute_twap(
                kis_client=self.kis,
                stock_code=stock_code,
                side=side,
                total_quantity=quantity,
                num_slices=routing.num_slices,
            )

            success = twap_result.filled_quantity > 0
            fill_price = twap_result.avg_fill_price if success else 0
            slippage = self.slippage.calculate(expected_price, fill_price, side) if success else None

            child_orders = [
                {
                    "slice": s.slice_index,
                    "quantity": s.quantity,
                    "limit_price": s.limit_price,
                    "kis_order_id": s.kis_order_id,
                    "success": s.success,
                }
                for s in twap_result.slices
            ]

            return ExecutionResult(
                stock_code=stock_code, side=side, total_quantity=quantity,
                execution_strategy="twap",
                kis_order_id=twap_result.slices[0].kis_order_id if twap_result.slices else None,
                success=success, fill_price=fill_price, expected_price=expected_price,
                slippage=slippage, child_orders=child_orders,
            )
        except Exception as e:
            logger.error(f"TWAP execution failed: {e}")
            return ExecutionResult(
                stock_code=stock_code, side=side, total_quantity=quantity,
                execution_strategy="twap", kis_order_id=None, success=False,
                fill_price=0, expected_price=expected_price, slippage=None,
                child_orders=[], error_message=str(e),
            )

    async def _execute_vwap(
        self, stock_code: str, side: str, quantity: int,
        expected_price: float, routing: OrderRouting,
    ) -> ExecutionResult:
        """Execute via VWAP strategy."""
        try:
            vwap_result: VWAPResult = await execute_vwap(
                kis_client=self.kis,
                stock_code=stock_code,
                side=side,
                total_quantity=quantity,
            )

            success = vwap_result.filled_quantity > 0
            fill_price = vwap_result.avg_fill_price if success else 0
            slippage = self.slippage.calculate(expected_price, fill_price, side) if success else None

            child_orders = [
                {
                    "slice": s.slice_index,
                    "weight": s.weight,
                    "quantity": s.quantity,
                    "limit_price": s.limit_price,
                    "kis_order_id": s.kis_order_id,
                    "success": s.success,
                }
                for s in vwap_result.slices
            ]

            return ExecutionResult(
                stock_code=stock_code, side=side, total_quantity=quantity,
                execution_strategy="vwap",
                kis_order_id=vwap_result.slices[0].kis_order_id if vwap_result.slices else None,
                success=success, fill_price=fill_price, expected_price=expected_price,
                slippage=slippage, child_orders=child_orders,
            )
        except Exception as e:
            logger.error(f"VWAP execution failed: {e}")
            return ExecutionResult(
                stock_code=stock_code, side=side, total_quantity=quantity,
                execution_strategy="vwap", kis_order_id=None, success=False,
                fill_price=0, expected_price=expected_price, slippage=None,
                child_orders=[], error_message=str(e),
            )
