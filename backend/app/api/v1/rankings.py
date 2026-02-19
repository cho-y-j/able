"""Rankings API endpoints for real-time market rankings and interest stocks."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.models.user import User
from app.api.v1.deps import get_current_user
from app.services.theme_classifier import list_all_themes, classify_stock
from app.services.market_rankings import compute_interest_score

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
    direction: str = Query(default="up", regex="^(up|down)$"),
    limit: int = Query(default=30, le=50),
    user: User = Depends(get_current_user),
):
    """Get price change rankings (gainers or losers).

    Uses KIS API when available, falls back to empty list.
    """
    try:
        from app.integrations.kis.client import KISClient
        from app.api.v1.deps import get_kis_client_for_user
        # This would need actual KIS client — for now return demo data structure
        # In production, inject KIS client dependency
    except Exception:
        pass

    # Return empty for now — populated when KIS client is available
    return []


@router.get("/volume", response_model=list[RankingEntry])
async def get_volume_rankings(
    limit: int = Query(default=30, le=50),
    user: User = Depends(get_current_user),
):
    """Get volume rankings."""
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
                stocks=stocks[:5],  # top 5 only
            )
            for theme, stocks in sorted(theme_stocks.items())
        ]
    except Exception:
        # Return all themes with 0 stocks if registry not available
        return [ThemeInfo(name=t, stock_count=0, stocks=[]) for t in list_all_themes()]


@router.get("/interest", response_model=list[InterestStock])
async def get_interest_stocks(
    limit: int = Query(default=20, le=50),
    user: User = Depends(get_current_user),
):
    """Get today's interest stocks based on composite scoring.

    Combines ranking position, active themes, factor signals, and investor flow.
    Returns stocks sorted by interest score.
    """
    # In production, this aggregates live data from multiple sources
    # For now, return empty list — populated by Celery collector
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
