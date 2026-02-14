"""Trading endpoints - connected to KIS API for order execution."""

import io
import uuid
import logging
from datetime import datetime, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.order import Order
from app.models.position import Position
from app.models.trade import Trade
from app.models.strategy import Strategy
from app.schemas.trading import OrderCreate, OrderResponse, PositionResponse
from app.api.v1.deps import get_current_user
from app.services.kis_service import get_kis_client
from app.api.v1.websocket import manager as ws_manager
from app.analysis.portfolio.aggregator import PortfolioAggregator, StrategyExposure
from app.analysis.portfolio.correlation import StrategyCorrelation
from app.analysis.portfolio.attribution import PerformanceAttribution
from app.analysis.risk.var import full_risk_report, STRESS_SCENARIOS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/orders", response_model=OrderResponse, status_code=201,
              summary="Place a trading order",
              description="Submit an order to KIS API. Supports market/limit orders. Updates positions and trades on fill.")
async def place_order(
    req: OrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Place an order and submit to KIS API."""
    order = Order(
        user_id=user.id,
        stock_code=req.stock_code,
        stock_name=req.stock_name,
        side=req.side,
        order_type=req.order_type,
        quantity=req.quantity,
        limit_price=req.limit_price,
        strategy_id=uuid.UUID(req.strategy_id) if req.strategy_id else None,
        status="pending",
    )
    db.add(order)
    await db.flush()

    # Submit to KIS API
    try:
        kis = await get_kis_client(user.id, db)
        kis_result = await kis.place_order(
            stock_code=req.stock_code,
            side=req.side,
            quantity=req.quantity,
            price=int(req.limit_price) if req.limit_price else 0,
            order_type=req.order_type,
        )

        if kis_result.get("success"):
            order.status = "submitted"
            order.kis_order_id = kis_result.get("kis_order_id")
            order.submitted_at = datetime.now(timezone.utc)
            logger.info(f"Order submitted to KIS: {kis_result['kis_order_id']}")
        else:
            order.status = "rejected"
            logger.warning(f"KIS rejected order: {kis_result.get('message')}")

    except ValueError as e:
        order.status = "failed"
        logger.error(f"KIS credentials error: {e}")
    except Exception as e:
        order.status = "failed"
        logger.error(f"KIS order submission failed: {e}")

    await db.flush()

    # Notify via WebSocket
    await ws_manager.send_to_user(str(user.id), {
        "type": "order_update",
        "order_id": str(order.id),
        "stock_code": order.stock_code,
        "side": order.side,
        "status": order.status,
    })

    # Send notification
    try:
        from app.services.notification_service import notify_order_filled, notify_order_rejected
        if order.status == "submitted":
            await notify_order_filled(
                str(user.id), order.stock_code, order.side, order.quantity,
                float(order.limit_price or 0), db,
            )
        elif order.status in ("rejected", "failed"):
            await notify_order_rejected(
                str(user.id), order.stock_code, order.side, f"Status: {order.status}", db,
            )
    except Exception as e:
        logger.warning(f"Notification dispatch failed: {e}")

    return OrderResponse(
        id=str(order.id),
        stock_code=order.stock_code,
        stock_name=order.stock_name,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        limit_price=float(order.limit_price) if order.limit_price else None,
        filled_quantity=order.filled_quantity,
        avg_fill_price=float(order.avg_fill_price) if order.avg_fill_price else None,
        status=order.status,
        submitted_at=order.submitted_at,
        filled_at=order.filled_at,
        created_at=order.created_at,
    )


@router.get("/orders", response_model=list[OrderResponse], summary="List orders")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    status: str | None = None,
    limit: int = 50,
):
    query = select(Order).where(Order.user_id == user.id)
    if status:
        query = query.where(Order.status == status)
    query = query.order_by(Order.created_at.desc()).limit(limit)

    result = await db.execute(query)
    orders = result.scalars().all()
    return [OrderResponse(
        id=str(o.id),
        stock_code=o.stock_code,
        stock_name=o.stock_name,
        side=o.side,
        order_type=o.order_type,
        quantity=o.quantity,
        limit_price=float(o.limit_price) if o.limit_price else None,
        filled_quantity=o.filled_quantity,
        avg_fill_price=float(o.avg_fill_price) if o.avg_fill_price else None,
        status=o.status,
        submitted_at=o.submitted_at,
        filled_at=o.filled_at,
        created_at=o.created_at,
    ) for o in orders]


@router.delete("/orders/{order_id}", status_code=204, summary="Cancel a pending order")
async def cancel_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Order).where(Order.id == uuid.UUID(order_id), Order.user_id == user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("pending", "submitted"):
        raise HTTPException(status_code=400, detail="Cannot cancel order in current status")

    # Cancel via KIS API if submitted
    if order.kis_order_id:
        try:
            kis = await get_kis_client(user.id, db)
            cancel_result = await kis.cancel_order(
                order_id=order.kis_order_id,
                stock_code=order.stock_code,
                quantity=order.quantity,
            )
            if not cancel_result.get("success"):
                logger.warning(f"KIS cancel failed: {cancel_result.get('message')}")
        except Exception as e:
            logger.error(f"KIS cancel error: {e}")

    order.status = "cancelled"

    await ws_manager.send_to_user(str(user.id), {
        "type": "order_update",
        "order_id": str(order.id),
        "stock_code": order.stock_code,
        "status": "cancelled",
    })


@router.get("/positions", response_model=list[PositionResponse], summary="List open positions")
async def list_positions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.quantity > 0)
    )
    positions = result.scalars().all()
    return [PositionResponse(
        id=str(p.id),
        stock_code=p.stock_code,
        stock_name=p.stock_name,
        quantity=p.quantity,
        avg_cost_price=float(p.avg_cost_price),
        current_price=float(p.current_price) if p.current_price else None,
        unrealized_pnl=float(p.unrealized_pnl) if p.unrealized_pnl else None,
        realized_pnl=float(p.realized_pnl),
    ) for p in positions]


@router.get("/balance", summary="Get account balance from KIS")
async def get_trading_balance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch account balance directly from KIS API."""
    try:
        kis = await get_kis_client(user.id, db)
        return await kis.get_balance()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch balance: {str(e)}")


@router.get("/trades", summary="List completed trades with P&L")
async def list_trades(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=100, le=500),
):
    """List completed trades with P&L."""
    result = await db.execute(
        select(Trade)
        .where(Trade.user_id == user.id)
        .order_by(Trade.entry_at.desc())
        .limit(limit)
    )
    trades = result.scalars().all()
    return [{
        "id": str(t.id),
        "stock_code": t.stock_code,
        "side": t.side,
        "quantity": t.quantity,
        "entry_price": float(t.entry_price),
        "exit_price": float(t.exit_price) if t.exit_price else None,
        "pnl": float(t.pnl) if t.pnl else None,
        "pnl_percent": t.pnl_percent,
        "entry_at": t.entry_at.isoformat() if t.entry_at else None,
        "exit_at": t.exit_at.isoformat() if t.exit_at else None,
    } for t in trades]


@router.get("/portfolio/analytics", summary="Portfolio summary and allocation")
async def portfolio_analytics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregated portfolio analytics: allocation, P&L summary, risk metrics."""
    # Positions
    pos_result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.quantity > 0)
    )
    positions = pos_result.scalars().all()

    total_invested = sum(float(p.avg_cost_price) * p.quantity for p in positions)
    total_current = sum(float(p.current_price or p.avg_cost_price) * p.quantity for p in positions)
    total_unrealized = sum(float(p.unrealized_pnl or 0) for p in positions)
    total_realized = sum(float(p.realized_pnl or 0) for p in positions)

    # Allocation breakdown
    allocation = []
    for p in positions:
        value = float(p.current_price or p.avg_cost_price) * p.quantity
        allocation.append({
            "stock_code": p.stock_code,
            "stock_name": p.stock_name,
            "quantity": p.quantity,
            "value": round(value, 0),
            "weight": round(value / total_current * 100, 2) if total_current > 0 else 0,
            "unrealized_pnl": float(p.unrealized_pnl or 0),
            "pnl_pct": round(
                (float(p.current_price or 0) - float(p.avg_cost_price)) / float(p.avg_cost_price) * 100, 2
            ) if float(p.avg_cost_price) > 0 else 0,
        })
    allocation.sort(key=lambda x: x["value"], reverse=True)

    # Trade statistics
    trade_result = await db.execute(
        select(Trade).where(Trade.user_id == user.id, Trade.exit_at != None)  # noqa: E711
    )
    trades = trade_result.scalars().all()

    total_trades = len(trades)
    winning = [t for t in trades if t.pnl and float(t.pnl) > 0]
    losing = [t for t in trades if t.pnl and float(t.pnl) <= 0]
    win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0

    avg_win = sum(float(t.pnl) for t in winning) / len(winning) if winning else 0
    avg_loss = sum(float(t.pnl) for t in losing) / len(losing) if losing else 0
    profit_factor = abs(avg_win * len(winning)) / abs(avg_loss * len(losing)) if losing and avg_loss != 0 else 0

    return {
        "portfolio_value": round(total_current, 0),
        "total_invested": round(total_invested, 0),
        "unrealized_pnl": round(total_unrealized, 0),
        "realized_pnl": round(total_realized, 0),
        "total_pnl": round(total_unrealized + total_realized, 0),
        "total_pnl_pct": round(
            (total_unrealized + total_realized) / total_invested * 100, 2
        ) if total_invested > 0 else 0,
        "position_count": len(positions),
        "allocation": allocation,
        "trade_stats": {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "avg_win": round(avg_win, 0),
            "avg_loss": round(avg_loss, 0),
            "profit_factor": round(profit_factor, 2),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
        },
    }


@router.get("/portfolio/strategies", summary="Cross-strategy exposure analysis")
async def portfolio_by_strategy(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cross-strategy exposure aggregation, HHI concentration, and conflict detection."""
    pos_result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.quantity > 0)
    )
    positions = pos_result.scalars().all()

    # Load strategy names
    strat_result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id)
    )
    strategies = {str(s.id): s.name for s in strat_result.scalars().all()}

    exposures = [
        StrategyExposure(
            strategy_id=str(p.strategy_id) if p.strategy_id else "manual",
            strategy_name=strategies.get(str(p.strategy_id), "Manual") if p.strategy_id else "Manual",
            stock_code=p.stock_code,
            quantity=p.quantity,
            value=float(p.current_price or p.avg_cost_price) * p.quantity,
            side="long" if p.quantity > 0 else "short",
        )
        for p in positions
    ]

    # Get total capital from balance if available
    total_capital = sum(e.value for e in exposures) * 1.25  # rough estimate

    agg = PortfolioAggregator.aggregate(exposures, total_capital)

    return {
        "total_exposure": round(agg.total_exposure, 0),
        "net_exposure": round(agg.net_exposure, 0),
        "long_exposure": round(agg.long_exposure, 0),
        "short_exposure": round(agg.short_exposure, 0),
        "hhi": round(agg.hhi, 0),
        "stock_exposures": {k: round(v, 0) for k, v in agg.stock_exposures.items()},
        "strategy_exposures": {
            k: {"value": round(v, 0), "name": strategies.get(k, "Manual")}
            for k, v in agg.strategy_exposures.items()
        },
        "conflicts": agg.conflicts,
        "warnings": agg.warnings,
    }


@router.get("/portfolio/correlation", summary="Strategy correlation matrix")
async def portfolio_correlation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Strategy return correlation matrix and diversification ratio."""
    # Load completed trades grouped by strategy
    trade_result = await db.execute(
        select(Trade).where(
            Trade.user_id == user.id,
            Trade.exit_at != None,  # noqa: E711
            Trade.strategy_id != None,  # noqa: E711
        ).order_by(Trade.exit_at)
    )
    trades = trade_result.scalars().all()

    if not trades:
        return {
            "strategy_ids": [],
            "strategy_names": [],
            "correlation_matrix": [],
            "diversification_ratio": 1.0,
            "avg_correlation": 0.0,
            "max_pair": None,
            "min_pair": None,
        }

    # Load strategy names
    strat_result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id)
    )
    strategies = {str(s.id): s.name for s in strat_result.scalars().all()}

    # Group pnl_percent by strategy as daily returns proxy
    strategy_returns: dict[str, dict] = {}
    for t in trades:
        sid = str(t.strategy_id)
        if sid not in strategy_returns:
            strategy_returns[sid] = {
                "name": strategies.get(sid, sid[:8]),
                "returns": [],
            }
        strategy_returns[sid]["returns"].append(float(t.pnl_percent or 0))

    # Need at least 2 strategies with 2+ trades each
    strategy_returns = {
        k: v for k, v in strategy_returns.items() if len(v["returns"]) >= 2
    }

    if len(strategy_returns) < 2:
        ids = list(strategy_returns.keys())
        names = [strategy_returns[sid]["name"] for sid in ids]
        return {
            "strategy_ids": ids,
            "strategy_names": names,
            "correlation_matrix": [[1.0]] if ids else [],
            "diversification_ratio": 1.0,
            "avg_correlation": 0.0,
            "max_pair": None,
            "min_pair": None,
        }

    # Pad to same length (min length across strategies)
    min_len = min(len(v["returns"]) for v in strategy_returns.values())
    for v in strategy_returns.values():
        v["returns"] = v["returns"][:min_len]

    result = StrategyCorrelation.compute(strategy_returns)

    return {
        "strategy_ids": result.strategy_ids,
        "strategy_names": result.strategy_names,
        "correlation_matrix": result.correlation_matrix,
        "diversification_ratio": result.diversification_ratio,
        "avg_correlation": result.avg_correlation,
        "max_pair": result.max_pair,
        "min_pair": result.min_pair,
    }


@router.get("/portfolio/attribution", summary="P&L attribution by strategy and stock")
async def portfolio_attribution(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """P&L attribution by strategy and by stock."""
    trade_result = await db.execute(
        select(Trade).where(
            Trade.user_id == user.id,
            Trade.exit_at != None,  # noqa: E711
        )
    )
    trades = trade_result.scalars().all()

    # Load strategy names
    strat_result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id)
    )
    strategies = {str(s.id): s.name for s in strat_result.scalars().all()}

    trade_dicts = [
        {
            "strategy_id": str(t.strategy_id) if t.strategy_id else "manual",
            "strategy_name": strategies.get(str(t.strategy_id), "Manual") if t.strategy_id else "Manual",
            "stock_code": t.stock_code,
            "pnl": float(t.pnl or 0),
        }
        for t in trades
    ]

    result = PerformanceAttribution.compute(trade_dicts)

    def _entry_dict(e):
        return {
            "key": e.key,
            "name": e.name,
            "pnl": e.pnl,
            "pnl_pct": e.pnl_pct,
            "trade_count": e.trade_count,
            "win_count": e.win_count,
            "loss_count": e.loss_count,
            "avg_pnl_per_trade": e.avg_pnl_per_trade,
        }

    return {
        "total_pnl": result.total_pnl,
        "by_strategy": [_entry_dict(e) for e in result.by_strategy],
        "by_stock": [_entry_dict(e) for e in result.by_stock],
        "best_strategy": _entry_dict(result.best_strategy) if result.best_strategy else None,
        "worst_strategy": _entry_dict(result.worst_strategy) if result.worst_strategy else None,
        "best_stock": _entry_dict(result.best_stock) if result.best_stock else None,
        "worst_stock": _entry_dict(result.worst_stock) if result.worst_stock else None,
    }


@router.get("/portfolio/risk", summary="VaR, CVaR, and stress test analysis",
            description="Comprehensive risk report: Historical, Parametric, Monte Carlo VaR + 6 stress scenarios.")
async def portfolio_risk(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    confidence: float = Query(default=0.95, ge=0.80, le=0.99),
    horizon_days: int = Query(default=1, ge=1, le=30),
):
    """Generate portfolio risk analysis with VaR and stress tests."""
    import numpy as np

    # Get positions
    pos_result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.quantity > 0)
    )
    positions = pos_result.scalars().all()

    if not positions:
        return {
            "portfolio_value": 0,
            "confidence": confidence,
            "horizon_days": horizon_days,
            "var": {},
            "stress_tests": [],
            "message": "No open positions for risk analysis",
        }

    # Build positions list for stress tests
    portfolio_value = sum(
        (p.current_price or p.avg_cost_price) * p.quantity for p in positions
    )
    pos_list = [
        {
            "stock_code": p.stock_code,
            "current_value": (p.current_price or p.avg_cost_price) * p.quantity,
        }
        for p in positions
    ]

    # Get recent trades for return calculation
    trades_result = await db.execute(
        select(Trade).where(Trade.user_id == user.id)
        .order_by(Trade.closed_at.desc()).limit(252)
    )
    trades = trades_result.scalars().all()

    if len(trades) < 5:
        # Not enough trades — use synthetic returns from positions
        # Approximate daily returns from position cost vs current price
        returns_list = []
        for p in positions:
            if p.avg_cost_price > 0 and p.current_price:
                total_return = (p.current_price - p.avg_cost_price) / p.avg_cost_price
                # Assume held for 30 days, estimate daily return
                daily_ret = total_return / 30
                returns_list.extend([daily_ret + np.random.normal(0, 0.01) for _ in range(30)])
        if not returns_list:
            returns_list = [0.0] * 30
        returns = np.array(returns_list)
    else:
        # Calculate daily P&L returns from trade history
        daily_pnls: dict[str, float] = defaultdict(float)
        for t in trades:
            if t.closed_at:
                day_key = t.closed_at.strftime("%Y-%m-%d")
                daily_pnls[day_key] += float(t.pnl or 0)

        if portfolio_value > 0 and daily_pnls:
            returns = np.array([pnl / portfolio_value for pnl in daily_pnls.values()])
        else:
            returns = np.array([0.0] * 30)

    report = full_risk_report(returns, portfolio_value, pos_list, confidence, horizon_days)
    return report


@router.get("/portfolio/report/pdf", summary="Download portfolio PDF report")
async def portfolio_report_pdf(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate and download a PDF portfolio report."""
    from fastapi.responses import StreamingResponse
    from app.services.pdf_report import generate_portfolio_report

    # Gather data
    pos_result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.quantity > 0)
    )
    positions = pos_result.scalars().all()

    pos_list = [
        {
            "stock_code": p.stock_code,
            "stock_name": p.stock_name,
            "quantity": p.quantity,
            "avg_cost_price": float(p.avg_cost_price),
            "current_price": float(p.current_price) if p.current_price else None,
            "unrealized_pnl": float(p.unrealized_pnl) if p.unrealized_pnl is not None else None,
        }
        for p in positions
    ]

    total_invested = sum(float(p.avg_cost_price) * p.quantity for p in positions)
    total_current = sum(
        float(p.current_price or p.avg_cost_price) * p.quantity for p in positions
    )
    total_unrealized = sum(float(p.unrealized_pnl or 0) for p in positions)

    trade_result = await db.execute(
        select(Trade).where(Trade.user_id == user.id, Trade.exit_at != None)  # noqa: E711
    )
    trades = trade_result.scalars().all()
    total_realized = sum(float(t.pnl or 0) for t in trades)
    winning = [t for t in trades if t.pnl and float(t.pnl) > 0]
    losing = [t for t in trades if t.pnl and float(t.pnl) <= 0]

    stats = {
        "portfolio_value": total_current,
        "total_invested": total_invested,
        "unrealized_pnl": total_unrealized,
        "realized_pnl": total_realized,
        "total_pnl": total_unrealized + total_realized,
        "total_pnl_pct": (total_unrealized + total_realized) / total_invested * 100 if total_invested > 0 else 0,
        "position_count": len(positions),
        "trade_stats": {
            "total_trades": len(trades),
            "win_rate": len(winning) / len(trades) if trades else 0,
            "profit_factor": (
                abs(sum(float(t.pnl) for t in winning)) /
                abs(sum(float(t.pnl) for t in losing))
                if losing and sum(float(t.pnl) for t in losing) != 0 else 0
            ),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
        },
    }

    user_name = user.display_name or user.email
    pdf_bytes = generate_portfolio_report(user_name, stats, pos_list)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="able_portfolio_{datetime.now().strftime("%Y%m%d")}.pdf"'
        },
    )
