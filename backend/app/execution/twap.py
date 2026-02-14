"""Time-Weighted Average Price (TWAP) order execution."""

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TWAPSlice:
    slice_index: int
    quantity: int
    limit_price: int
    expected_price: float
    kis_order_id: str | None = None
    success: bool = False
    fill_price: float | None = None


@dataclass
class TWAPResult:
    total_quantity: int
    num_slices: int
    slices: list[TWAPSlice] = field(default_factory=list)
    filled_quantity: int = 0
    avg_fill_price: float = 0.0

    @property
    def success_rate(self) -> float:
        if not self.slices:
            return 0.0
        return sum(1 for s in self.slices if s.success) / len(self.slices)


def calculate_twap_slices(
    total_quantity: int,
    num_slices: int = 5,
) -> list[int]:
    """Split total quantity into equal time-weighted slices.

    Distributes remainder across first slices so the total is exact.
    """
    if num_slices <= 0:
        return [total_quantity] if total_quantity > 0 else []

    base_qty = total_quantity // num_slices
    remainder = total_quantity % num_slices
    slices = []
    for i in range(num_slices):
        qty = base_qty + (1 if i < remainder else 0)
        if qty > 0:
            slices.append(qty)
    return slices


async def execute_twap(
    kis_client,
    stock_code: str,
    side: str,
    total_quantity: int,
    num_slices: int = 5,
    interval_seconds: int = 600,  # 10 minutes between slices
    limit_offset_pct: float = 0.001,  # 0.1% offset
) -> TWAPResult:
    """Execute TWAP strategy: split order into time-weighted slices.

    For Korean market hours (09:00-15:30), default 5 slices x 10min = 50 min window.
    """
    slice_quantities = calculate_twap_slices(total_quantity, num_slices)
    result = TWAPResult(total_quantity=total_quantity, num_slices=len(slice_quantities))

    for i, qty in enumerate(slice_quantities):
        try:
            price_data = await kis_client.get_price(stock_code)
            current_price = price_data["current_price"]

            if side == "buy":
                limit_price = int(current_price * (1 + limit_offset_pct))
            else:
                limit_price = int(current_price * (1 - limit_offset_pct))

            order_result = await kis_client.place_order(
                stock_code=stock_code,
                side=side,
                quantity=qty,
                price=limit_price,
                order_type="limit",
            )

            slice_result = TWAPSlice(
                slice_index=i,
                quantity=qty,
                limit_price=limit_price,
                expected_price=current_price,
                kis_order_id=order_result.get("kis_order_id"),
                success=order_result.get("success", False),
            )

            if slice_result.success:
                result.filled_quantity += qty

            result.slices.append(slice_result)
            logger.info(
                f"TWAP slice {i+1}/{len(slice_quantities)}: "
                f"{side} {qty} {stock_code} @ {limit_price} "
                f"({'OK' if slice_result.success else 'FAIL'})"
            )

        except Exception as e:
            logger.error(f"TWAP slice {i+1} failed: {e}")
            result.slices.append(TWAPSlice(
                slice_index=i, quantity=qty, limit_price=0,
                expected_price=0, success=False,
            ))

        # Wait between slices (except last)
        if i < len(slice_quantities) - 1:
            await asyncio.sleep(interval_seconds)

    # Calculate average fill price
    if result.filled_quantity > 0:
        total_cost = sum(
            s.limit_price * s.quantity for s in result.slices if s.success
        )
        result.avg_fill_price = total_cost / result.filled_quantity

    return result
