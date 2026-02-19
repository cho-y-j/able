"""Rankings API endpoints for real-time market rankings and interest stocks."""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.services.theme_classifier import list_all_themes
from app.services.market_rankings import compute_interest_score, build_interest_stocks
from app.services.kis_service import get_kis_client

logger = logging.getLogger(__name__)

router = APIRouter()


class RankingEntry(BaseModel):
    rank: int
    stock_code: str
    stock_name: str
    price: int
    change_pct: float
    volume: int


class ThemeInfo(BaseModel):
    name: str
    stock_count: int
    stocks: list[dict]


class InterestStock(BaseModel):
    stock_code: str
    stock_name: str
    price: int
    change_pct: float
    volume: int
    score: float
    reasons: list[str]
    themes: list[str]


@router.get("/price", response_model=list[RankingEntry])
async def get_price_rankings(
    direction: str = Query(default="up", pattern="^(up|down)$"),
    limit: int = Query(default=30, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get price change rankings (gainers or losers) via KIS API."""
    try:
        kis = await get_kis_client(user.id, db)
        data = await kis.get_price_ranking(direction=direction, limit=limit)
        return [RankingEntry(**item) for item in data]
    except Exception as e:
        logger.warning("Failed to fetch price rankings: %s", e)
        return []


@router.get("/volume", response_model=list[RankingEntry])
async def get_volume_rankings(
    limit: int = Query(default=30, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get volume rankings via KIS API."""
    try:
        kis = await get_kis_client(user.id, db)
        data = await kis.get_volume_ranking(limit=limit)
        return [RankingEntry(**item) for item in data]
    except Exception as e:
        logger.warning("Failed to fetch volume rankings: %s", e)
        return []


@router.get("/themes", response_model=list[ThemeInfo])
async def get_theme_list(
    user: User = Depends(get_current_user),
):
    """Get all available themes with stock counts."""
    from app.services.stock_registry import get_all_stocks

    try:
        all_stocks = get_all_stocks()
        from app.services.theme_classifier import get_theme_stocks
        theme_stocks = get_theme_stocks([s.to_dict() for s in all_stocks])
        return [
            ThemeInfo(
                name=theme,
                stock_count=len(stocks),
                stocks=stocks[:5],
            )
            for theme, stocks in sorted(theme_stocks.items())
        ]
    except Exception:
        return [ThemeInfo(name=t, stock_count=0, stocks=[]) for t in list_all_themes()]


@router.get("/interest", response_model=list[InterestStock])
async def get_interest_stocks(
    limit: int = Query(default=20, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get today's interest stocks based on composite scoring.

    Combines KIS rankings, theme classification, factor signals, and investor flow.
    """
    try:
        kis = await get_kis_client(user.id, db)

        # Fetch price + volume rankings in parallel
        price_data = await kis.get_price_ranking(direction="up", limit=30)
        volume_data = await kis.get_volume_ranking(limit=30)

        # Build theme info for ranked stocks
        stock_themes: dict[str, list[str]] = {}
        try:
            from app.services.stock_registry import get_stock_info
            from app.services.theme_classifier import classify_stock

            for item in price_data + volume_data:
                code = item["stock_code"]
                if code not in stock_themes:
                    info = get_stock_info(code)
                    if info:
                        stock_themes[code] = classify_stock(
                            getattr(info, "sector", ""),
                            item.get("stock_name", ""),
                        )
        except Exception:
            pass

        results = build_interest_stocks(
            price_rankings=price_data,
            volume_rankings=volume_data,
            stock_themes=stock_themes,
            limit=limit,
        )
        return [InterestStock(**item) for item in results]

    except Exception as e:
        logger.warning("Failed to build interest stocks: %s", e)
        return []


@router.get("/catalog")
async def get_rankings_catalog(
    user: User = Depends(get_current_user),
):
    """Return available ranking types and their descriptions."""
    return {
        "rankings": [
            {"type": "price", "label": "상승/하락률 순위", "description": "당일 등락률 기준"},
            {"type": "volume", "label": "거래량 순위", "description": "당일 누적 거래량 기준"},
            {"type": "themes", "label": "테마 분류", "description": "섹터 기반 테마 그룹핑"},
            {"type": "interest", "label": "관심종목", "description": "복합 점수 기반 추천"},
        ],
        "theme_count": len(list_all_themes()),
    }
