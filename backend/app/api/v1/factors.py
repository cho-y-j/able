from datetime import date
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.api.v1.deps import get_current_user
from app.services.factor_collector import (
    get_latest_factors,
    get_factor_snapshots,
    list_factors,
)

router = APIRouter()


class FactorSnapshotResponse(BaseModel):
    factor_name: str
    value: float
    category: str | None = None
    snapshot_date: str
    stock_code: str
    timeframe: str

    model_config = {"from_attributes": True}


class FactorCatalogEntry(BaseModel):
    name: str
    category: str
    description: str


@router.get("/catalog", response_model=list[FactorCatalogEntry])
async def get_factor_catalog(
    user: User = Depends(get_current_user),
):
    """List all registered factor extractors including global/macro factors."""
    technical = [FactorCatalogEntry(**f) for f in list_factors()]
    try:
        from app.services.global_factor_collector import get_global_factor_catalog
        global_factors = [FactorCatalogEntry(**f) for f in get_global_factor_catalog()]
        return technical + global_factors
    except Exception:
        return technical


@router.get("/latest/{stock_code}", response_model=list[FactorSnapshotResponse])
async def get_latest_stock_factors(
    stock_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the latest factor values for a specific stock."""
    snapshots = await get_latest_factors(db, stock_code)
    return [
        FactorSnapshotResponse(
            factor_name=s.factor_name,
            value=s.value,
            category=(s.metadata_ or {}).get("category"),
            snapshot_date=str(s.snapshot_date),
            stock_code=s.stock_code,
            timeframe=s.timeframe,
        )
        for s in snapshots
    ]


@router.get("/snapshots", response_model=list[FactorSnapshotResponse])
async def query_factor_snapshots(
    stock_code: str | None = Query(default=None),
    factor_name: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Query factor snapshots with filters."""
    snapshots = await get_factor_snapshots(
        db,
        stock_code=stock_code,
        factor_name=factor_name,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [
        FactorSnapshotResponse(
            factor_name=s.factor_name,
            value=s.value,
            category=(s.metadata_ or {}).get("category"),
            snapshot_date=str(s.snapshot_date),
            stock_code=s.stock_code,
            timeframe=s.timeframe,
        )
        for s in snapshots
    ]
