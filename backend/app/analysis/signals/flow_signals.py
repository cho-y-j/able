"""Investor flow factor extractors.

These factors capture institutional and foreign investor behavior
from KIS API investor trend data. They are registered as factors
(not signals) because they return numeric values rather than entry/exit booleans.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_flow_factors(investor_data: dict[str, Any], total_volume: int = 0) -> dict[str, float]:
    """Extract investor flow factors from KIS investor trend data.

    Args:
        investor_data: Result from KISClient.get_investor_trends()
        total_volume: Today's total trading volume for ratio calculation

    Returns:
        Dict of {factor_name: value}
    """
    factors: dict[str, float] = {}

    foreign_qty = investor_data.get("foreign_net_buy_qty", 0)
    inst_qty = investor_data.get("institutional_net_buy_qty", 0)
    individual_qty = investor_data.get("individual_net_buy_qty", 0)

    factors["foreign_net_buy_qty"] = float(foreign_qty)
    factors["institutional_net_buy_qty"] = float(inst_qty)

    # Ratios (foreign/institutional net buy as fraction of total volume)
    if total_volume > 0:
        factors["foreign_net_buy_ratio"] = float(foreign_qty) / total_volume
        factors["institutional_net_buy_ratio"] = float(inst_qty) / total_volume
    else:
        factors["foreign_net_buy_ratio"] = 0.0
        factors["institutional_net_buy_ratio"] = 0.0

    return factors


def compute_foreign_3day_trend(daily_foreign_qtys: list[int]) -> float:
    """Compute 3-day foreign buying trend direction.

    Args:
        daily_foreign_qtys: List of daily foreign net buy quantities,
            most recent first. Needs at least 3 values.

    Returns:
        +1.0 if 3 consecutive days of net buying
        -1.0 if 3 consecutive days of net selling
        0.0 otherwise
    """
    if len(daily_foreign_qtys) < 3:
        return 0.0

    recent_3 = daily_foreign_qtys[:3]

    if all(q > 0 for q in recent_3):
        return 1.0
    elif all(q < 0 for q in recent_3):
        return -1.0
    return 0.0
