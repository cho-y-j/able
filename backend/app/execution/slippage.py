"""Slippage tracking and execution quality analysis."""

from dataclasses import dataclass


@dataclass
class SlippageResult:
    expected_price: float
    actual_price: float
    slippage_bps: float  # Positive = unfavorable
    slippage_amount: float
    side: str


class SlippageTracker:
    """Tracks and analyzes execution slippage."""

    @staticmethod
    def calculate(expected_price: float, actual_price: float, side: str) -> SlippageResult:
        """Calculate slippage in basis points.

        Positive slippage = unfavorable (paid more on buy, received less on sell).
        """
        if expected_price <= 0:
            return SlippageResult(
                expected_price=expected_price,
                actual_price=actual_price,
                slippage_bps=0.0,
                slippage_amount=0.0,
                side=side,
            )

        if side == "buy":
            slippage_bps = (actual_price - expected_price) / expected_price * 10_000
        else:
            slippage_bps = (expected_price - actual_price) / expected_price * 10_000

        return SlippageResult(
            expected_price=expected_price,
            actual_price=actual_price,
            slippage_bps=round(slippage_bps, 2),
            slippage_amount=round(abs(actual_price - expected_price), 0),
            side=side,
        )
