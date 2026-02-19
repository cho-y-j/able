import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db, async_session_factory
from app.models.user import User
from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.schemas.strategy import (
    StrategyCreate, StrategyUpdate, StrategyResponse,
    StrategySearchRequest, StrategySearchResponse,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    stock_code: str | None = Query(None, description="Filter by stock code"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Strategy).where(Strategy.user_id == user.id)
    if stock_code:
        stmt = stmt.where(Strategy.stock_code == stock_code)
    stmt = stmt.order_by(Strategy.created_at.desc())
    result = await db.execute(stmt)
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
    await db.refresh(strategy)
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })


@router.post("/search", response_model=StrategySearchResponse)
async def search_strategies(
    req: StrategySearchRequest,
    user: User = Depends(get_current_user),
):
    """Start a strategy search. Returns a job_id for polling progress."""
    import asyncio
    from app.services.strategy_search import run_search

    job_id = str(uuid.uuid4())

    async def _run_in_background():
        async with async_session_factory() as db:
            await run_search(
                job_id=job_id,
                user_id=user.id,
                stock_code=req.stock_code,
                date_range_start=req.date_range_start,
                date_range_end=req.date_range_end,
                optimization_method=req.optimization_method,
                data_source=req.data_source,
                db=db,
                market=req.market,
            )

    asyncio.create_task(_run_in_background())

    return StrategySearchResponse(
        job_id=job_id,
        status="running",
        message=f"{req.stock_code} 전략 검색을 시작했습니다",
    )


@router.get("/search-jobs/{job_id}")
async def get_search_job_status(job_id: str):
    """Poll strategy search job progress."""
    from app.services.strategy_search import get_job_status

    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "step": job["step"],
        "result": job.get("result"),
        "error": job.get("error"),
    }


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


@router.get("/{strategy_id}/detail")
async def get_strategy_detail(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get strategy with its latest backtest and full validation data."""
    result = await db.execute(
        select(Strategy).where(Strategy.id == uuid.UUID(strategy_id), Strategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get latest backtest
    bt_result = await db.execute(
        select(Backtest)
        .where(Backtest.strategy_id == strategy.id, Backtest.status == "completed")
        .order_by(Backtest.created_at.desc())
        .limit(1)
    )
    bt = bt_result.scalar_one_or_none()

    backtest_data = None
    if bt:
        backtest_data = {
            "id": str(bt.id),
            "date_range_start": str(bt.date_range_start),
            "date_range_end": str(bt.date_range_end),
            "metrics": {
                "total_return": bt.total_return,
                "annual_return": bt.annual_return,
                "sharpe_ratio": bt.sharpe_ratio,
                "sortino_ratio": bt.sortino_ratio,
                "max_drawdown": bt.max_drawdown,
                "win_rate": bt.win_rate,
                "profit_factor": bt.profit_factor,
                "total_trades": bt.total_trades,
                "calmar_ratio": bt.calmar_ratio,
            },
            "validation": {
                "wfa_score": bt.wfa_score,
                "mc_score": bt.mc_score,
                "oos_score": bt.oos_score,
            },
            "equity_curve": bt.equity_curve,
            "trade_log": bt.trade_log,
        }

    return {
        "id": str(strategy.id),
        "name": strategy.name,
        "stock_code": strategy.stock_code,
        "stock_name": strategy.stock_name,
        "strategy_type": strategy.strategy_type,
        "indicators": strategy.indicators,
        "parameters": strategy.parameters,
        "entry_rules": strategy.entry_rules,
        "exit_rules": strategy.exit_rules,
        "risk_params": strategy.risk_params,
        "composite_score": strategy.composite_score,
        "validation_results": strategy.validation_results,
        "status": strategy.status,
        "is_auto_trading": strategy.is_auto_trading,
        "created_at": strategy.created_at.isoformat(),
        "backtest": backtest_data,
    }


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
    await db.refresh(strategy)
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
    await db.refresh(strategy)
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
    await db.refresh(strategy)
    return StrategyResponse(id=str(strategy.id), **{
        k: getattr(strategy, k) for k in StrategyResponse.model_fields if k != "id"
    })
