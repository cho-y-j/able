"""Paper portfolio session management.

Manages the lifecycle of paper trading sessions with persistent state
stored in a JSON-serializable format for DB storage.
"""

import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from app.simulation.paper_broker import PaperBroker, FillModel, PaperOrder

logger = logging.getLogger(__name__)


@dataclass
class PaperSession:
    """A paper trading session with its broker state."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    name: str = "Paper Trading"
    status: str = "active"  # active, paused, completed
    initial_cash: float = 100_000_000
    fill_model: str = "realistic"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: str | None = None


class PaperPortfolio:
    """Manages paper trading sessions and their brokers."""

    # In-memory session store (per-process)
    _sessions: dict[str, PaperSession] = {}
    _brokers: dict[str, PaperBroker] = {}

    @classmethod
    def create_session(
        cls,
        user_id: str,
        name: str = "Paper Trading",
        initial_cash: float = 100_000_000,
        fill_model: str = "realistic",
    ) -> PaperSession:
        """Create a new paper trading session."""
        session = PaperSession(
            user_id=user_id,
            name=name,
            initial_cash=initial_cash,
            fill_model=fill_model,
        )

        fm = FillModel.REALISTIC if fill_model == "realistic" else FillModel.IMMEDIATE
        broker = PaperBroker(initial_cash=initial_cash, fill_model=fm)

        cls._sessions[session.id] = session
        cls._brokers[session.id] = broker

        logger.info(f"Paper session created: {session.id} for user {user_id}")
        return session

    @classmethod
    def get_session(cls, session_id: str) -> PaperSession | None:
        return cls._sessions.get(session_id)

    @classmethod
    def get_broker(cls, session_id: str) -> PaperBroker | None:
        return cls._brokers.get(session_id)

    @classmethod
    def list_sessions(cls, user_id: str) -> list[PaperSession]:
        return [s for s in cls._sessions.values() if s.user_id == user_id]

    @classmethod
    def stop_session(cls, session_id: str) -> PaperSession | None:
        session = cls._sessions.get(session_id)
        if session:
            session.status = "completed"
            session.ended_at = datetime.now(timezone.utc).isoformat()
        return session

    @classmethod
    def get_session_summary(cls, session_id: str) -> dict | None:
        """Get comprehensive session summary with broker stats."""
        session = cls._sessions.get(session_id)
        broker = cls._brokers.get(session_id)
        if not session or not broker:
            return None

        stats = broker.get_stats()
        positions = [
            {
                "stock_code": p.stock_code,
                "stock_name": p.stock_name,
                "quantity": p.quantity,
                "avg_cost_price": round(p.avg_cost_price, 0),
                "current_price": round(p.current_price, 0),
                "unrealized_pnl": round(p.unrealized_pnl, 0),
                "pnl_pct": round(
                    ((p.current_price - p.avg_cost_price) / p.avg_cost_price * 100), 2
                ) if p.avg_cost_price > 0 else 0,
            }
            for p in broker.positions.values()
            if p.quantity > 0
        ]

        orders = [
            {
                "id": o.id,
                "stock_code": o.stock_code,
                "stock_name": o.stock_name,
                "side": o.side,
                "order_type": o.order_type,
                "quantity": o.quantity,
                "limit_price": o.limit_price,
                "filled_quantity": o.filled_quantity,
                "avg_fill_price": round(o.avg_fill_price, 0),
                "status": o.status,
                "slippage_bps": round(o.slippage_bps, 2),
                "created_at": o.created_at,
                "filled_at": o.filled_at,
            }
            for o in broker.orders
        ]

        trades = [
            {
                "stock_code": t.stock_code,
                "side": t.side,
                "quantity": t.quantity,
                "entry_price": round(t.entry_price, 0),
                "exit_price": round(t.exit_price, 0),
                "pnl": round(t.pnl, 0),
                "pnl_percent": round(t.pnl_percent, 2),
                "entry_at": t.entry_at,
                "exit_at": t.exit_at,
            }
            for t in broker.trades
        ]

        # Equity curve from trade history
        equity_curve = [{"time": session.created_at, "value": session.initial_cash}]
        running = session.initial_cash
        for t in broker.trades:
            running += t.pnl
            equity_curve.append({"time": t.exit_at, "value": round(running, 0)})

        return {
            "session": {
                "id": session.id,
                "name": session.name,
                "status": session.status,
                "initial_cash": session.initial_cash,
                "fill_model": session.fill_model,
                "created_at": session.created_at,
                "ended_at": session.ended_at,
            },
            "stats": stats,
            "positions": positions,
            "orders": orders,
            "trades": trades,
            "equity_curve": equity_curve,
        }

    @classmethod
    def reset(cls):
        """Clear all sessions (for testing)."""
        cls._sessions.clear()
        cls._brokers.clear()
