import uuid
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.trading_recipe import TradingRecipe
from app.models.order import Order
from app.models.trade import Trade
from app.models.api_credential import ApiCredential
from app.schemas.recipe import (
    RecipeCreate, RecipeUpdate, RecipeResponse,
    RecipeBacktestRequest, RecipeBacktestResponse,
    RecipeExecutionRequest, RecipeExecutionResponse, RecipeOrderResponse,
    DailyPnlPoint, PerformanceTrade, RecipePerformanceResponse,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


def _recipe_to_response(r: TradingRecipe) -> RecipeResponse:
    return RecipeResponse(
        id=str(r.id),
        name=r.name,
        description=r.description,
        signal_config=r.signal_config,
        custom_filters=r.custom_filters,
        stock_codes=r.stock_codes or [],
        risk_config=r.risk_config,
        is_active=r.is_active,
        is_template=r.is_template,
        auto_execute=r.auto_execute,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get("", response_model=list[RecipeResponse])
async def list_recipes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(TradingRecipe)
        .where(TradingRecipe.user_id == user.id)
        .order_by(TradingRecipe.created_at.desc())
    )
    result = await db.execute(stmt)
    return [_recipe_to_response(r) for r in result.scalars().all()]


@router.post("", response_model=RecipeResponse, status_code=201)
async def create_recipe(
    req: RecipeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = TradingRecipe(
        user_id=user.id,
        name=req.name,
        description=req.description,
        signal_config=req.signal_config,
        custom_filters=req.custom_filters,
        stock_codes=req.stock_codes,
        risk_config=req.risk_config,
        auto_execute=req.auto_execute,
    )
    db.add(recipe)
    await db.flush()
    await db.refresh(recipe)
    return _recipe_to_response(recipe)


@router.get("/templates", response_model=list[RecipeResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    stmt = (
        select(TradingRecipe)
        .where(TradingRecipe.is_template == True)  # noqa: E712
        .order_by(TradingRecipe.created_at.desc())
    )
    result = await db.execute(stmt)
    return [_recipe_to_response(r) for r in result.scalars().all()]


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _recipe_to_response(recipe)


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: str,
    req: RecipeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(recipe, field, value)

    await db.flush()
    await db.refresh(recipe)
    return _recipe_to_response(recipe)


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    await db.delete(recipe)


@router.post("/{recipe_id}/backtest", response_model=RecipeBacktestResponse)
async def backtest_recipe(
    recipe_id: str,
    req: RecipeBacktestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    from app.analysis.composer import SignalComposer
    from app.analysis.backtest.engine import run_backtest
    from app.services.strategy_search import fetch_ohlcv_data

    # Fetch data
    stock_code = req.stock_code
    df = await fetch_ohlcv_data(
        stock_code=stock_code,
        date_range_start=req.date_range_start,
        date_range_end=req.date_range_end,
    )

    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="No data available for the given stock/date range")

    # Compose signals
    composer = SignalComposer()
    entry, exit_ = composer.compose(df, recipe.signal_config)

    # Run backtest
    bt = run_backtest(df, entry, exit_)

    # Calculate score
    from app.analysis.validation.scoring import calculate_composite_score
    metrics_dict = {
        "total_return": bt.total_return,
        "annual_return": bt.annual_return,
        "sharpe_ratio": bt.sharpe_ratio,
        "max_drawdown": bt.max_drawdown,
        "win_rate": bt.win_rate,
        "profit_factor": bt.profit_factor,
        "calmar_ratio": bt.calmar_ratio,
    }
    score_result = calculate_composite_score(metrics_dict)

    return RecipeBacktestResponse(
        composite_score=score_result["composite_score"],
        grade=score_result["grade"],
        metrics={
            "total_return": bt.total_return,
            "annual_return": bt.annual_return,
            "sharpe_ratio": bt.sharpe_ratio,
            "max_drawdown": bt.max_drawdown,
            "win_rate": bt.win_rate,
            "total_trades": bt.total_trades,
            "sortino_ratio": bt.sortino_ratio,
            "profit_factor": bt.profit_factor,
            "calmar_ratio": bt.calmar_ratio,
        },
        equity_curve=bt.equity_curve,
        trade_log=bt.trade_log,
    )


@router.post("/{recipe_id}/activate", response_model=RecipeResponse)
async def activate_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Validate KIS credentials exist
    cred_result = await db.execute(
        select(ApiCredential).where(
            ApiCredential.user_id == user.id,
            ApiCredential.service_type == "kis",
            ApiCredential.is_active == True,  # noqa: E712
        )
    )
    if not cred_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="KIS credentials required to activate auto-trading",
        )

    recipe.is_active = True
    recipe.auto_execute = True
    await db.flush()
    await db.refresh(recipe)

    # Reload active recipes in realtime manager
    try:
        from app.services.realtime_manager import get_realtime_manager
        mgr = get_realtime_manager()
        await mgr.reload_active_recipes(db)
    except Exception:
        pass

    return _recipe_to_response(recipe)


@router.post("/{recipe_id}/deactivate", response_model=RecipeResponse)
async def deactivate_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe.is_active = False
    recipe.auto_execute = False
    await db.flush()
    await db.refresh(recipe)

    # Reload active recipes in realtime manager
    try:
        from app.services.realtime_manager import get_realtime_manager
        mgr = get_realtime_manager()
        await mgr.reload_active_recipes(db)
    except Exception:
        pass

    return _recipe_to_response(recipe)


@router.post("/{recipe_id}/clone", response_model=RecipeResponse, status_code=201)
async def clone_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Clone a recipe (typically a template) into user's own recipes."""
    result = await db.execute(
        select(TradingRecipe).where(TradingRecipe.id == uuid.UUID(recipe_id))
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Recipe not found")

    clone = TradingRecipe(
        user_id=user.id,
        name=f"{source.name} (복제)",
        description=source.description,
        signal_config=source.signal_config,
        custom_filters=source.custom_filters,
        stock_codes=source.stock_codes,
        risk_config=source.risk_config,
    )
    db.add(clone)
    await db.flush()
    await db.refresh(clone)
    return _recipe_to_response(clone)


@router.post("/{recipe_id}/execute", response_model=RecipeExecutionResponse)
async def execute_recipe(
    recipe_id: str,
    req: RecipeExecutionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger recipe execution for signal evaluation and order placement."""
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    from app.services.recipe_executor import RecipeExecutor

    executor = RecipeExecutor()
    try:
        order_results = await executor.execute(
            user_id=str(user.id),
            recipe=recipe,
            db=db,
            stock_code=req.stock_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    submitted = sum(1 for o in order_results if o.get("status") == "submitted")
    failed = sum(1 for o in order_results if o.get("status") in ("failed", "error"))

    # Build response with actual order records
    order_responses = []
    for o in order_results:
        oid = o.get("order_id")
        if oid:
            order_row = await db.execute(select(Order).where(Order.id == uuid.UUID(oid)))
            order_obj = order_row.scalar_one_or_none()
            if order_obj:
                order_responses.append(RecipeOrderResponse(
                    id=str(order_obj.id),
                    stock_code=order_obj.stock_code,
                    side=order_obj.side,
                    order_type=order_obj.order_type,
                    quantity=order_obj.quantity,
                    avg_fill_price=float(order_obj.avg_fill_price) if order_obj.avg_fill_price else None,
                    kis_order_id=order_obj.kis_order_id,
                    status=order_obj.status,
                    execution_strategy=order_obj.execution_strategy,
                    slippage_bps=order_obj.slippage_bps,
                    error_message=order_obj.error_message,
                    created_at=order_obj.created_at,
                ))

    return RecipeExecutionResponse(
        recipe_id=recipe_id,
        orders=order_responses,
        total_submitted=submitted,
        total_failed=failed,
    )


@router.get("/{recipe_id}/orders", response_model=list[RecipeOrderResponse])
async def list_recipe_orders(
    recipe_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List execution history (orders) for a recipe."""
    # Verify recipe ownership
    recipe_result = await db.execute(
        select(TradingRecipe.id).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    if not recipe_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Recipe not found")

    stmt = (
        select(Order)
        .where(Order.recipe_id == uuid.UUID(recipe_id))
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    return [
        RecipeOrderResponse(
            id=str(o.id),
            stock_code=o.stock_code,
            side=o.side,
            order_type=o.order_type,
            quantity=o.quantity,
            avg_fill_price=float(o.avg_fill_price) if o.avg_fill_price else None,
            kis_order_id=o.kis_order_id,
            status=o.status,
            execution_strategy=o.execution_strategy,
            slippage_bps=o.slippage_bps,
            error_message=o.error_message,
            created_at=o.created_at,
        )
        for o in orders
    ]


@router.get("/{recipe_id}/performance", response_model=RecipePerformanceResponse)
async def get_recipe_performance(
    recipe_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Performance analytics for a recipe: PnL stats, equity curve, trade history."""
    # Verify ownership
    result = await db.execute(
        select(TradingRecipe).where(
            TradingRecipe.id == uuid.UUID(recipe_id),
            TradingRecipe.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Fetch all trades for this recipe
    trade_result = await db.execute(
        select(Trade)
        .where(Trade.recipe_id == uuid.UUID(recipe_id))
        .order_by(Trade.entry_at.desc())
    )
    all_trades = trade_result.scalars().all()

    # Compute stats from closed trades
    closed = [t for t in all_trades if t.exit_at is not None and t.pnl is not None]
    open_count = len(all_trades) - len(closed)
    wins = [t for t in closed if float(t.pnl) > 0]
    losses = [t for t in closed if float(t.pnl) <= 0]

    total_pnl = float(sum(float(t.pnl) for t in closed)) if closed else 0.0
    win_rate = (len(wins) / len(closed) * 100) if closed else None
    avg_win = (sum(t.pnl_percent or 0 for t in wins) / len(wins)) if wins else None
    avg_loss = (sum(t.pnl_percent or 0 for t in losses) / len(losses)) if losses else None
    gross_wins = sum(float(t.pnl) for t in wins)
    gross_losses = abs(sum(float(t.pnl) for t in losses))
    profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else None
    total_pnl_pct = sum(t.pnl_percent or 0 for t in closed) if closed else None

    # Avg slippage from orders
    slip_result = await db.execute(
        select(func.avg(Order.slippage_bps)).where(
            Order.recipe_id == uuid.UUID(recipe_id),
            Order.slippage_bps.isnot(None),
        )
    )
    avg_slippage = slip_result.scalar_one_or_none()

    # Build daily equity curve from closed trades
    daily_pnl: dict[str, float] = defaultdict(float)
    for t in closed:
        day = t.exit_at.strftime("%Y-%m-%d")
        daily_pnl[day] += float(t.pnl)

    cumulative = 0.0
    equity_curve = []
    for day in sorted(daily_pnl.keys()):
        cumulative += daily_pnl[day]
        equity_curve.append(DailyPnlPoint(date=day, value=round(cumulative, 2)))

    # Paginate trades
    paginated = all_trades[offset: offset + limit]

    return RecipePerformanceResponse(
        total_trades=len(all_trades),
        closed_trades=len(closed),
        open_trades=open_count,
        win_rate=round(win_rate, 1) if win_rate is not None else None,
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round(total_pnl_pct, 2) if total_pnl_pct is not None else None,
        avg_win=round(avg_win, 2) if avg_win is not None else None,
        avg_loss=round(avg_loss, 2) if avg_loss is not None else None,
        profit_factor=round(profit_factor, 2) if profit_factor is not None else None,
        avg_slippage_bps=round(float(avg_slippage), 1) if avg_slippage else None,
        equity_curve=equity_curve,
        trades=[
            PerformanceTrade(
                id=str(t.id),
                stock_code=t.stock_code,
                side=t.side,
                entry_price=float(t.entry_price),
                exit_price=float(t.exit_price) if t.exit_price else None,
                quantity=t.quantity,
                pnl=float(t.pnl) if t.pnl else None,
                pnl_percent=t.pnl_percent,
                entry_at=t.entry_at.isoformat(),
                exit_at=t.exit_at.isoformat() if t.exit_at else None,
            )
            for t in paginated
        ],
        trades_total=len(all_trades),
    )
