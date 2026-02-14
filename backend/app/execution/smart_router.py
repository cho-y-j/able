"""Smart order routing based on market conditions."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OrderRouting:
    execution_strategy: str  # "direct", "twap", "vwap"
    order_type: str  # "market", "limit"
    limit_price: int | None
    num_slices: int
    reasoning: str


class SmartOrderRouter:
    """Determines optimal order type based on spread and depth."""

    @staticmethod
    def route(
        quantity: int,
        side: str,
        current_price: float,
        avg_daily_volume: int,
        best_bid: float = 0,
        best_ask: float = 0,
    ) -> OrderRouting:
        """Decide execution strategy and order type.

        Rules:
        - spread < 0.1% & depth < 1% → market order (direct)
        - spread < 0.3% & depth < 5% → limit at best bid/ask (direct)
        - depth >= 5% → TWAP (5 slices)
        - depth >= 10% → VWAP
        """
        mid_price = (best_bid + best_ask) / 2 if (best_bid > 0 and best_ask > 0) else current_price
        spread_pct = (best_ask - best_bid) / mid_price if mid_price > 0 and best_ask > best_bid else 0
        depth_pct = quantity / avg_daily_volume if avg_daily_volume > 0 else 0

        # VWAP for very large orders
        if depth_pct >= 0.10:
            return OrderRouting(
                execution_strategy="vwap",
                order_type="limit",
                limit_price=None,
                num_slices=9,
                reasoning=f"Large order ({depth_pct:.1%} of daily volume), using VWAP",
            )

        # TWAP for large orders
        if depth_pct >= 0.05:
            return OrderRouting(
                execution_strategy="twap",
                order_type="limit",
                limit_price=None,
                num_slices=5,
                reasoning=f"Order is {depth_pct:.1%} of daily volume, using TWAP",
            )

        # Direct market order for small orders with tight spread
        if spread_pct < 0.001 and depth_pct < 0.01:
            return OrderRouting(
                execution_strategy="direct",
                order_type="market",
                limit_price=None,
                num_slices=1,
                reasoning=f"Tight spread ({spread_pct:.2%}), low depth ({depth_pct:.2%})",
            )

        # Direct limit order for moderate spread
        limit_price = int(best_ask if side == "buy" else best_bid) if best_bid > 0 else int(current_price)
        return OrderRouting(
            execution_strategy="direct",
            order_type="limit",
            limit_price=limit_price,
            num_slices=1,
            reasoning=f"Spread {spread_pct:.2%}, depth {depth_pct:.2%}, using limit order",
        )
