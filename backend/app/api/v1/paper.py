"""Paper trading simulation endpoints.

Provides a simulated trading environment using in-memory state.
No real orders are placed — all fills are simulated locally.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.user import User
from app.api.v1.deps import get_current_user
from app.simulation.paper_portfolio import PaperPortfolio

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request/Response schemas ---

class CreateSessionRequest(BaseModel):
    name: str = "Paper Trading"
    initial_cash: float = 100_000_000
    fill_model: str = "realistic"  # "realistic" or "immediate"


class PaperOrderRequest(BaseModel):
    stock_code: str
    stock_name: str = ""
    side: str  # "buy" or "sell"
    quantity: int
    current_price: float
    order_type: str = "market"
    limit_price: float | None = None


class PriceUpdateRequest(BaseModel):
    prices: dict[str, float]  # stock_code -> current_price


# --- Endpoints ---

@router.post("/sessions", status_code=201)
async def create_session(
    req: CreateSessionRequest,
    user: User = Depends(get_current_user),
):
    """Start a new paper trading session."""
    if req.fill_model not in ("realistic", "immediate"):
        raise HTTPException(status_code=400, detail="fill_model must be 'realistic' or 'immediate'")

    session = PaperPortfolio.create_session(
        user_id=str(user.id),
        name=req.name,
        initial_cash=req.initial_cash,
        fill_model=req.fill_model,
    )
    return {
        "id": session.id,
        "name": session.name,
        "status": session.status,
        "initial_cash": session.initial_cash,
        "fill_model": session.fill_model,
        "created_at": session.created_at,
    }


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user)):
    """List all paper trading sessions for the current user."""
    sessions = PaperPortfolio.list_sessions(str(user.id))
    return [
        {
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "initial_cash": s.initial_cash,
            "fill_model": s.fill_model,
            "created_at": s.created_at,
            "ended_at": s.ended_at,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session_summary(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """Get comprehensive session summary with stats, positions, orders, trades."""
    session = PaperPortfolio.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your session")

    summary = PaperPortfolio.get_session_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session data not found")
    return summary


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """Stop a paper trading session."""
    session = PaperPortfolio.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your session")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    stopped = PaperPortfolio.stop_session(session_id)
    return {
        "id": stopped.id,
        "status": stopped.status,
        "ended_at": stopped.ended_at,
    }


@router.post("/sessions/{session_id}/order")
async def place_paper_order(
    session_id: str,
    req: PaperOrderRequest,
    user: User = Depends(get_current_user),
):
    """Place a simulated order in a paper trading session."""
    session = PaperPortfolio.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your session")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    if req.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    if req.current_price <= 0:
        raise HTTPException(status_code=400, detail="current_price must be positive")

    broker = PaperPortfolio.get_broker(session_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    order = broker.place_order(
        stock_code=req.stock_code,
        stock_name=req.stock_name,
        side=req.side,
        quantity=req.quantity,
        current_price=req.current_price,
        order_type=req.order_type,
        limit_price=req.limit_price,
    )

    return {
        "id": order.id,
        "stock_code": order.stock_code,
        "side": order.side,
        "order_type": order.order_type,
        "quantity": order.quantity,
        "filled_quantity": order.filled_quantity,
        "avg_fill_price": round(order.avg_fill_price, 0),
        "status": order.status,
        "slippage_bps": round(order.slippage_bps, 2),
    }


@router.post("/sessions/{session_id}/prices")
async def update_prices(
    session_id: str,
    req: PriceUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update current prices for positions and try to fill pending orders."""
    session = PaperPortfolio.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your session")

    broker = PaperPortfolio.get_broker(session_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    broker.update_prices(req.prices)
    filled = broker.try_fill_pending(req.prices)

    return {
        "prices_updated": len(req.prices),
        "pending_filled": len(filled),
        "filled_orders": [
            {"id": o.id, "stock_code": o.stock_code, "status": o.status}
            for o in filled
        ],
    }
