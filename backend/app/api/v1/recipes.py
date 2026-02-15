import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.trading_recipe import TradingRecipe
from app.schemas.recipe import (
    RecipeCreate, RecipeUpdate, RecipeResponse,
    RecipeBacktestRequest, RecipeBacktestResponse,
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

    recipe.is_active = True
    await db.flush()
    await db.refresh(recipe)
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
    await db.flush()
    await db.refresh(recipe)
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
