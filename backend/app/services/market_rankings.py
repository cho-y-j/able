"""Market rankings service for real-time stock rankings and interest stock extraction.

Combines KIS API data with factor scores and theme classification
to produce rankings and interest stock recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.theme_classifier import classify_stock, get_theme_stocks

logger = logging.getLogger(__name__)


def compute_interest_score(
    ranking_position: int | None = None,
    total_ranked: int = 30,
    has_active_theme: bool = False,
    factor_signals: dict[str, float] | None = None,
    foreign_net_buy: float = 0,
    institutional_net_buy: float = 0,
) -> tuple[float, list[str]]:
    """Compute interest score for a stock (0~10 scale).

    Returns (score, reasons_list).
    """
    score = 0.0
    reasons: list[str] = []

    # Ranking score (0~3): higher position = higher score
    if ranking_position is not None and total_ranked > 0:
        rank_score = max(0, (total_ranked - ranking_position + 1) / total_ranked) * 3
        score += rank_score
        if ranking_position <= 5:
            reasons.append(f"상승률 {ranking_position}위")

    # Theme score (0~2)
    if has_active_theme:
        score += 2.0
        reasons.append("활성 테마 소속")

    # Factor score (0~3): RSI reversal + MACD golden cross + close vs low
    if factor_signals:
        rsi = factor_signals.get("rsi_14")
        macd_cross = factor_signals.get("macd_signal_cross")
        close_low = factor_signals.get("close_vs_low_20")

        factor_score = 0.0
        if rsi is not None and rsi < 40:
            factor_score += 1.0
            reasons.append("RSI 반등 구간")
        if macd_cross is not None and macd_cross > 0:
            factor_score += 1.0
            reasons.append("MACD 골든크로스")
        if close_low is not None and close_low > 1.05:
            factor_score += 1.0
            reasons.append("20일 저점 대비 반등")
        score += factor_score

    # Flow score (0~2): foreign + institutional net buying
    flow_score = 0.0
    if foreign_net_buy > 0:
        flow_score += 1.0
        reasons.append("외국인 순매수")
    if institutional_net_buy > 0:
        flow_score += 1.0
        reasons.append("기관 순매수")
    score += flow_score

    return min(score, 10.0), reasons


def build_interest_stocks(
    price_rankings: list[dict[str, Any]],
    volume_rankings: list[dict[str, Any]],
    stock_factors: dict[str, dict[str, float]] | None = None,
    stock_flows: dict[str, dict[str, float]] | None = None,
    stock_themes: dict[str, list[str]] | None = None,
    active_themes: set[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Build ranked interest stocks from multiple data sources.

    Args:
        price_rankings: KIS price ranking results
        volume_rankings: KIS volume ranking results
        stock_factors: {stock_code: {factor_name: value}}
        stock_flows: {stock_code: {foreign_net_buy_qty, institutional_net_buy_qty}}
        stock_themes: {stock_code: [theme_names]}
        active_themes: Set of currently active/hot theme names
        limit: Max results

    Returns:
        Sorted list of interest stocks with scores and reasons
    """
    stock_factors = stock_factors or {}
    stock_flows = stock_flows or {}
    stock_themes = stock_themes or {}
    active_themes = active_themes or set()

    # Collect all candidate stocks
    candidates: dict[str, dict[str, Any]] = {}

    for item in price_rankings:
        code = item["stock_code"]
        candidates[code] = {
            "stock_code": code,
            "stock_name": item.get("stock_name", ""),
            "price": item.get("price", 0),
            "change_pct": item.get("change_pct", 0),
            "volume": item.get("volume", 0),
            "ranking_position": item.get("rank"),
        }

    for item in volume_rankings:
        code = item["stock_code"]
        if code not in candidates:
            candidates[code] = {
                "stock_code": code,
                "stock_name": item.get("stock_name", ""),
                "price": item.get("price", 0),
                "change_pct": item.get("change_pct", 0),
                "volume": item.get("volume", 0),
                "ranking_position": None,
            }

    # Score each candidate
    results = []
    for code, info in candidates.items():
        themes = stock_themes.get(code, [])
        has_active = bool(active_themes & set(themes))
        factors = stock_factors.get(code, {})
        flows = stock_flows.get(code, {})

        score, reasons = compute_interest_score(
            ranking_position=info.get("ranking_position"),
            has_active_theme=has_active,
            factor_signals=factors,
            foreign_net_buy=flows.get("foreign_net_buy_qty", 0),
            institutional_net_buy=flows.get("institutional_net_buy_qty", 0),
        )

        results.append({
            **info,
            "score": round(score, 1),
            "reasons": reasons,
            "themes": themes,
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
