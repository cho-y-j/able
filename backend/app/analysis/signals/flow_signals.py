"""Investor flow factor extractors.

These factors capture institutional, foreign and individual investor behavior
from KIS API investor trend data. They are registered as factors
(not signals) because they return numeric values rather than entry/exit booleans.

ADR-0006 requires a news-trap filter whose decision input is "individual net
buying dominance". That decision needs both sides of the book, so the individual
leg and the three-party opposition are first-class factors here, not scratch
variables.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_flow_factors(investor_data: dict[str, Any], total_volume: int = 0) -> dict[str, float]:
    """Extract investor flow factors from KIS investor trend data.

    Pure transform of an already-fetched ``investor_data`` dict. No IO.

    Args:
        investor_data: Result from KISClient.get_investor_trends()
        total_volume: Today's total trading volume for ratio calculation

    Returns:
        Dict of {factor_name: value}. Keys:
            ``{foreign,institutional,individual,smart_money}_net_buy_qty``
                raw net buy quantities (smart_money = foreign + institutional)
            ``{...}_net_buy_ratio``
                the same values divided by ``total_volume`` (0.0 when volume <= 0)
            ``flow_opposition_qty``
                smart money net buy minus individual net buy
            ``flow_opposition_ratio``
                ``flow_opposition_qty`` divided by ``total_volume``
            ``flow_opposition_score``
                scale-free alignment in [-1.0, +1.0]; +1.0 exactly when smart
                money buys while individuals sell (ADR-0006 "weight up" case),
                -1.0 exactly when individuals buy while smart money sells
                (ADR-0006 news-trap case)
    """
    factors: dict[str, float] = {}

    foreign_qty = float(investor_data.get("foreign_net_buy_qty", 0))
    inst_qty = float(investor_data.get("institutional_net_buy_qty", 0))
    individual_qty = float(investor_data.get("individual_net_buy_qty", 0))

    # Foreign + institutional act as one side of the ADR-0006 judgement.
    smart_money_qty = foreign_qty + inst_qty
    opposition_qty = smart_money_qty - individual_qty

    factors["foreign_net_buy_qty"] = foreign_qty
    factors["institutional_net_buy_qty"] = inst_qty
    factors["individual_net_buy_qty"] = individual_qty
    factors["smart_money_net_buy_qty"] = smart_money_qty
    factors["flow_opposition_qty"] = opposition_qty

    # Ratios (net buy as fraction of total volume)
    if total_volume > 0:
        factors["foreign_net_buy_ratio"] = foreign_qty / total_volume
        factors["institutional_net_buy_ratio"] = inst_qty / total_volume
        factors["individual_net_buy_ratio"] = individual_qty / total_volume
        factors["smart_money_net_buy_ratio"] = smart_money_qty / total_volume
        factors["flow_opposition_ratio"] = opposition_qty / total_volume
    else:
        factors["foreign_net_buy_ratio"] = 0.0
        factors["institutional_net_buy_ratio"] = 0.0
        factors["individual_net_buy_ratio"] = 0.0
        factors["smart_money_net_buy_ratio"] = 0.0
        factors["flow_opposition_ratio"] = 0.0

    # Scale-free opposition. Bounded [-1, +1] so it is comparable across stocks
    # without needing volume, market cap or float share normalisation.
    # Saturates at +-1.0 only when the two sides take opposite directions.
    magnitude = abs(smart_money_qty) + abs(individual_qty)
    factors["flow_opposition_score"] = opposition_qty / magnitude if magnitude > 0 else 0.0

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
