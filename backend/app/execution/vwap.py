"""Volume-Weighted Average Price (VWAP) order execution."""

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Typical Korean stock market intraday volume profile (9 half-hour buckets)
# 09:00-09:30, 09:30-10:00, 10:00-11:00, 11:00-12:00,
# 12:00-13:00, 13:00-14:00, 14:00-14:30, 14:30-15:00, 15:00-15:30
DEFAULT_KRX_VOLUME_PROFILE = [
    0.15,  # 09:00-09:30 (opening surge)
    0.10,  # 09:30-10:00
    0.15,  # 10:00-11:00
    0.10,  # 11:00-12:00
    0.08,  # 12:00-13:00 (lunch dip)
    0.12,  # 13:00-14:00
    0.12,  # 14:00-14:30
    0.10,  # 14:30-15:00
    0.08,  # 15:00-15:30 (closing)
]


@dataclass
class VWAPSlice:
    slice_index: int
    weight: float
    quantity: int
    limit_price: int
    expected_price: float
    kis_order_id: str | None = None
    success: bool = False


@dataclass
class VWAPResult:
    total_quantity: int
    num_slices: int
    slices: list[VWAPSlice] = field(default_factory=list)
    filled_quantity: int = 0
    avg_fill_price: float = 0.0

    @property
    def success_rate(self) -> float:
        if not self.slices:
            return 0.0
        return sum(1 for s in self.slices if s.success) / len(self.slices)


def calculate_vwap_slices(
    total_quantity: int,
    volume_profile: list[float] | None = None,
) -> list[tuple[float, int]]:
    """Calculate quantity per slice based on volume profile.

    Returns list of (weight, quantity) tuples.
    """
    if volume_profile is None:
        volume_profile = DEFAULT_KRX_VOLUME_PROFILE

    total_weight = sum(volume_profile)
    if total_weight <= 0:
        return [(1.0, total_quantity)]

    weights = [v / total_weight for v in volume_profile]

    # Calculate raw quantities
    raw_quantities = [max(1, round(total_quantity * w)) for w in weights]

    # Adjust for rounding errors to match total exactly
    diff = total_quantity - sum(raw_quantities)
    if diff > 0:
        for i in range(diff):
            raw_quantities[i % len(raw_quantities)] += 1
    elif diff < 0:
        for i in range(-diff):
            idx = len(raw_quantities) - 1 - (i % len(raw_quantities))
            if raw_quantities[idx] > 1:
                raw_quantities[idx] -= 1

    return [(w, q) for w, q in zip(weights, raw_quantities) if q > 0]


async def execute_vwap(
    kis_client,
    stock_code: str,
    side: str,
    total_quantity: int,
    volume_profile: list[float] | None = None,
    interval_seconds: int = 600,  # 10 minutes between slices
    limit_offset_pct: float = 0.001,
) -> VWAPResult:
    """Execute VWAP strategy: split order proportional to volume profile."""
    slices = calculate_vwap_slices(total_quantity, volume_profile)
    result = VWAPResult(total_quantity=total_quantity, num_slices=len(slices))

    for i, (weight, qty) in enumerate(slices):
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

            slice_result = VWAPSlice(
                slice_index=i,
                weight=weight,
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
                f"VWAP slice {i+1}/{len(slices)}: "
                f"{side} {qty} {stock_code} @ {limit_price} "
                f"(weight={weight:.1%}, {'OK' if slice_result.success else 'FAIL'})"
            )

        except Exception as e:
            logger.error(f"VWAP slice {i+1} failed: {e}")
            result.slices.append(VWAPSlice(
                slice_index=i, weight=weight, quantity=qty,
                limit_price=0, expected_price=0, success=False,
            ))

        if i < len(slices) - 1:
            await asyncio.sleep(interval_seconds)

    if result.filled_quantity > 0:
        total_cost = sum(s.limit_price * s.quantity for s in result.slices if s.success)
        result.avg_fill_price = total_cost / result.filled_quantity

    return result
