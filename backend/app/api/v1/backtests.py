import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.backtest import Backtest
from app.models.strategy import Strategy
from app.api.v1.deps import get_current_user
from app.schemas.validation import (
    MonteCarloRequest, MonteCarloResponse,
    OOSRequest, OOSResponse,
    CPCVRequest, CPCVResponse,
    StrategyCompareResponse,
)

router = APIRouter()


@router.get("/compare", response_model=StrategyCompareResponse)
async def compare_strategies(
    strategy_ids: str = Query(..., description="Comma-separated strategy IDs"),
    include_curves: bool = Query(False, description="Include equity curve data"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare multiple strategies side by side using their latest backtests."""
    ids = [uuid.UUID(sid.strip()) for sid in strategy_ids.split(",") if sid.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 strategy IDs to compare")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Max 10 strategies for comparison")

    strategies = []
    for sid in ids:
        result = await db.execute(
            select(Strategy).where(Strategy.id == sid, Strategy.user_id == user.id)
        )
        s = result.scalar_one_or_none()
        if not s:
            continue

        bt_result = await db.execute(
            select(Backtest)
            .where(Backtest.strategy_id == sid, Backtest.status == "completed")
            .order_by(Backtest.created_at.desc())
            .limit(1)
        )
        bt = bt_result.scalar_one_or_none()

        entry = {
            "strategy_id": str(s.id),
            "name": s.name,
            "stock_code": s.stock_code,
            "strategy_type": s.strategy_type,
            "composite_score": s.composite_score,
            "status": s.status,
        }
        if bt:
            entry["backtest"] = {
                "id": str(bt.id),
                "total_return": bt.total_return,
                "annual_return": bt.annual_return,
                "sharpe_ratio": bt.sharpe_ratio,
                "sortino_ratio": bt.sortino_ratio,
                "max_drawdown": bt.max_drawdown,
                "win_rate": bt.win_rate,
                "profit_factor": bt.profit_factor,
                "calmar_ratio": bt.calmar_ratio,
                "wfa_score": bt.wfa_score,
                "mc_score": bt.mc_score,
                "oos_score": bt.oos_score,
            }
            if include_curves and bt.equity_curve:
                entry["backtest"]["equity_curve"] = bt.equity_curve
                entry["backtest"]["date_range_start"] = str(bt.date_range_start)
        strategies.append(entry)

    ranked = sorted(strategies, key=lambda x: x.get("composite_score") or 0, reverse=True)
    ranking = [
        {"rank": i + 1, "strategy_id": s["strategy_id"], "name": s["name"], "score": s.get("composite_score")}
        for i, s in enumerate(ranked)
    ]

    return StrategyCompareResponse(strategies=strategies, ranking=ranking)


@router.get("/{backtest_id}")
async def get_backtest(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Backtest).where(
            Backtest.id == uuid.UUID(backtest_id),
            Backtest.user_id == user.id,
        )
    )
    bt = result.scalar_one_or_none()
    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return {
        "id": str(bt.id),
        "strategy_id": str(bt.strategy_id),
        "status": bt.status,
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
            "oos_score": bt.oos_score,
            "mc_score": bt.mc_score,
        },
        "equity_curve": bt.equity_curve,
        "trade_log": bt.trade_log,
        "error_message": bt.error_message,
    }


@router.get("/{backtest_id}/equity-curve")
async def get_equity_curve(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Backtest.equity_curve).where(
            Backtest.id == uuid.UUID(backtest_id),
            Backtest.user_id == user.id,
        )
    )
    curve = result.scalar_one_or_none()
    if curve is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return {"equity_curve": curve}


@router.post("/{backtest_id}/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo(
    backtest_id: str,
    req: MonteCarloRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run Monte Carlo simulation on a completed backtest's trade log."""
    bt = await _get_backtest(db, user, backtest_id)

    if not bt.trade_log:
        raise HTTPException(status_code=400, detail="Backtest has no trade log")

    trade_returns = [t.get("pnl_percent", 0) for t in bt.trade_log]
    if len(trade_returns) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 trades for Monte Carlo")

    from app.analysis.validation.monte_carlo import monte_carlo_simulation
    result = monte_carlo_simulation(
        trade_returns,
        n_simulations=req.n_simulations,
        initial_capital=req.initial_capital,
    )

    # Update stored mc_score
    bt.mc_score = result.get("mc_score", 0)
    await db.flush()

    return MonteCarloResponse(**result)


@router.post("/{backtest_id}/oos-validate", response_model=OOSResponse)
async def run_oos_validation(
    backtest_id: str,
    req: OOSRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run Out-of-Sample validation on a backtest's strategy."""
    bt = await _get_backtest(db, user, backtest_id)
    strategy = await _get_strategy(db, user, str(bt.strategy_id))

    df = await _fetch_data(
        strategy.stock_code,
        str(bt.date_range_start).replace("-", ""),
        str(bt.date_range_end).replace("-", ""),
        req.data_source,
    )

    signal_gen = _get_signal_gen(strategy)
    from app.analysis.validation.out_of_sample import out_of_sample_test
    result = out_of_sample_test(df, signal_gen, strategy.parameters, oos_ratio=req.oos_ratio)

    bt.oos_score = result.get("oos_score", 0)
    await db.flush()

    return OOSResponse(**result)


@router.post("/{backtest_id}/cpcv", response_model=CPCVResponse)
async def run_cpcv(
    backtest_id: str,
    req: CPCVRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run Combinatorial Purged Cross-Validation on a backtest's strategy."""
    bt = await _get_backtest(db, user, backtest_id)
    strategy = await _get_strategy(db, user, str(bt.strategy_id))

    df = await _fetch_data(
        strategy.stock_code,
        str(bt.date_range_start).replace("-", ""),
        str(bt.date_range_end).replace("-", ""),
        req.data_source,
    )

    signal_gen = _get_signal_gen(strategy)
    from app.analysis.validation.out_of_sample import combinatorial_purged_cv
    result = combinatorial_purged_cv(
        df, signal_gen, strategy.parameters,
        n_splits=req.n_splits, purge_days=req.purge_days,
    )

    return CPCVResponse(**result)


# ── Helpers ──────────────────────────────────────────────

async def _get_backtest(db: AsyncSession, user: User, backtest_id: str) -> Backtest:
    result = await db.execute(
        select(Backtest).where(
            Backtest.id == uuid.UUID(backtest_id),
            Backtest.user_id == user.id,
            Backtest.status == "completed",
        )
    )
    bt = result.scalar_one_or_none()
    if not bt:
        raise HTTPException(status_code=404, detail="Completed backtest not found")
    return bt


async def _get_strategy(db: AsyncSession, user: User, strategy_id: str) -> Strategy:
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == uuid.UUID(strategy_id),
            Strategy.user_id == user.id,
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


async def _fetch_data(stock_code: str, start_date: str, end_date: str, data_source: str = "yahoo"):
    """Fetch OHLCV data in a thread (blocking I/O)."""
    import asyncio
    from app.integrations.data.factory import get_data_provider

    provider = get_data_provider(data_source)

    def _fetch():
        return provider.get_ohlcv(stock_code, start_date, end_date)

    df = await asyncio.to_thread(_fetch)
    if df.empty or len(df) < 60:
        raise HTTPException(status_code=400, detail=f"Insufficient data: {len(df)} rows")
    return df


def _get_signal_gen(strategy: Strategy):
    """Get signal generator for a strategy."""
    from app.analysis.indicators.registry import get_signal_generator
    return get_signal_generator(
        strategy.parameters,
        name=strategy.strategy_type if strategy.strategy_type else None,
    )
