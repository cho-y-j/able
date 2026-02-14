import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.strategy import Strategy
from app.schemas.strategy import (
    StrategyCreate, StrategyUpdate, StrategyResponse,
    StrategySearchRequest, StrategySearchResponse,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id).order_by(Strategy.created_at.desc())
    )
    strategies = result.scalars().all()
    return [StrategyResponse(id=str(s.id), **{
        k: getattr(s, k) for k in StrategyResponse.model_fields if k != "id"
    }) for s in strategies]


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    req: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    strategy = Strategy(user_id=user.id, **req.model_dump())
    db.add(strategy)
    await db.flush()
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy).where(Strategy.id == uuid.UUID(strategy_id), Strategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    req: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy).where(Strategy.id == uuid.UUID(strategy_id), Strategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(strategy, field, value)

    await db.flush()
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy).where(Strategy.id == uuid.UUID(strategy_id), Strategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await db.delete(strategy)


@router.post("/search", response_model=StrategySearchResponse)
async def search_strategies(
    req: StrategySearchRequest,
    user: User = Depends(get_current_user),
):
    from app.tasks.optimization_tasks import run_strategy_search

    task = run_strategy_search.delay(
        user_id=str(user.id),
        stock_code=req.stock_code,
        date_range_start=req.date_range_start,
        date_range_end=req.date_range_end,
        method=req.optimization_method,
    )
    return StrategySearchResponse(
        job_id=task.id,
        status="queued",
        message=f"Strategy search started for {req.stock_code}",
    )


@router.post("/{strategy_id}/activate", response_model=StrategyResponse)
async def activate_strategy(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy).where(Strategy.id == uuid.UUID(strategy_id), Strategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy.is_auto_trading = True
    strategy.status = "active"
    await db.flush()
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })


@router.post("/{strategy_id}/deactivate", response_model=StrategyResponse)
async def deactivate_strategy(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Strategy).where(Strategy.id == uuid.UUID(strategy_id), Strategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy.is_auto_trading = False
    strategy.status = "paused"
    await db.flush()
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })
