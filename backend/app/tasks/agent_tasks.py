"""Celery tasks for AI agent orchestration sessions."""

import uuid
import logging
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.tasks.celery_app import celery_app
from app.models.agent_session import AgentSession, AgentAction
from app.models.api_credential import ApiCredential
from app.core.encryption import get_vault

from app.services.notification_service import (
    notify_agent_completed, notify_agent_error,
)

logger = logging.getLogger(__name__)


def _send_notification_sync(coro):
    """Run an async notification coroutine from sync Celery context."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(coro)
        loop.close()
    except Exception as exc:
        logger.warning(f"Notification dispatch failed: {exc}")


def _get_sync_db():
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


def _log_action(db: Session, session_id: uuid.UUID, agent_name: str,
                action_type: str, details: dict | None = None):
    """Log an agent action to the database."""
    action = AgentAction(
        session_id=session_id,
        agent_name=agent_name,
        action_type=action_type,
        output_data=details or {},
    )
    db.add(action)
    db.flush()


@celery_app.task(bind=True, name="tasks.run_agent_session", max_retries=2)
def run_agent_session(self, user_id: str, session_id: str, session_type: str = "full_cycle"):
    """Run an agent orchestration session as a background task.

    Executes the LangGraph trading graph in a synchronous wrapper.
    """
    import asyncio
    from langgraph.graph import StateGraph

    db = _get_sync_db()
    sid = uuid.UUID(session_id)
    uid = uuid.UUID(user_id)

    try:
        self.update_state(state="PROGRESS", meta={"step": "initializing", "agent": "orchestrator"})

        session = db.query(AgentSession).filter(AgentSession.id == sid).first()
        if not session:
            return {"status": "error", "message": "Session not found"}

        _log_action(db, sid, "orchestrator", "session_started", {"type": session_type})

        # Check for required credentials
        kis_cred = db.query(ApiCredential).filter(
            ApiCredential.user_id == uid,
            ApiCredential.service_type == "kis",
            ApiCredential.is_active == True,
        ).first()

        llm_cred = db.query(ApiCredential).filter(
            ApiCredential.user_id == uid,
            ApiCredential.service_type == "llm",
            ApiCredential.is_active == True,
        ).first()

        if not kis_cred:
            session.status = "error"
            session.error_log = [{"error": "No KIS credentials configured"}]
            db.commit()
            return {"status": "error", "message": "No KIS credentials"}

        # Initialize KIS client from stored credentials
        kis_client = None
        try:
            from app.integrations.kis.client import KISClient
            vault = get_vault()
            kis_client = KISClient(
                app_key=vault.decrypt(kis_cred.api_key_enc),
                app_secret=vault.decrypt(kis_cred.api_secret_enc),
                account_number=vault.decrypt(kis_cred.extra_encrypted.get("account_number", "")),
                is_paper=kis_cred.extra_encrypted.get("is_paper", True),
            )
            _log_action(db, sid, "orchestrator", "kis_client_initialized",
                       {"is_paper": kis_client.is_paper})
        except Exception as e:
            logger.warning(f"Failed to init KIS client, running in dry-run: {e}")
            _log_action(db, sid, "orchestrator", "kis_client_failed",
                       {"error": str(e)})

        # Build and run the trading graph
        from app.agents.orchestrator import build_trading_graph

        graph = build_trading_graph()

        # Initial state
        initial_state = {
            "messages": [],
            "user_id": user_id,
            "session_id": session_id,
            "market_regime": None,
            "watchlist": [],  # Will be populated by user's active strategies
            "strategy_candidates": [],
            "optimization_status": "",
            "risk_assessment": None,
            "pending_orders": [],
            "executed_orders": [],
            "portfolio_snapshot": {},
            "alerts": [],
            "current_agent": "",
            "iteration_count": 0,
            "should_continue": True,
            "error_state": None,
            "execution_config": None,
            "slippage_report": [],
            "_kis_client": kis_client,
        }

        # Get user's active strategies' stock codes as watchlist
        from app.models.strategy import Strategy
        strategies = db.query(Strategy).filter(
            Strategy.user_id == uid,
            Strategy.is_auto_trading == True,
        ).all()
        initial_state["watchlist"] = list(set(s.stock_code for s in strategies))

        if not initial_state["watchlist"]:
            _log_action(db, sid, "orchestrator", "no_watchlist",
                       {"message": "No active auto-trading strategies"})
            session.status = "completed"
            db.commit()
            return {"status": "complete", "message": "No active strategies to trade"}

        _log_action(db, sid, "orchestrator", "watchlist_loaded",
                   {"stocks": initial_state["watchlist"]})

        self.update_state(state="PROGRESS", meta={
            "step": "running_graph", "agent": "orchestrator",
            "watchlist": initial_state["watchlist"],
        })

        # Run the graph (synchronous invocation)
        final_state = asyncio.get_event_loop().run_until_complete(
            _run_graph_async(graph, initial_state, db, sid)
        ) if not asyncio.get_event_loop().is_running() else _run_graph_sync(graph, initial_state, db, sid)

        # Update session with results
        session.status = "completed"
        session.iteration_count = final_state.get("iteration_count", 0)
        if final_state.get("market_regime"):
            session.market_regime = final_state["market_regime"].get("classification")
        session.ended_at = datetime.now(timezone.utc)

        _log_action(db, sid, "orchestrator", "session_completed", {
            "iterations": final_state.get("iteration_count", 0),
            "orders_executed": len(final_state.get("executed_orders", [])),
            "alerts": final_state.get("alerts", []),
        })

        db.commit()

        # Notify user of session completion
        _send_notification_sync(
            notify_agent_completed(user_id, session_id, final_state.get("iteration_count", 0))
        )

        return {
            "status": "complete",
            "session_id": session_id,
            "iterations": final_state.get("iteration_count", 0),
            "regime": final_state.get("market_regime", {}).get("classification"),
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"Agent session {session_id} hit soft time limit")
        try:
            session = db.query(AgentSession).filter(AgentSession.id == sid).first()
            if session:
                session.status = "timeout"
                session.ended_at = datetime.now(timezone.utc)
                _log_action(db, sid, "orchestrator", "timeout",
                           {"message": "Soft time limit exceeded"})
            db.commit()
        except Exception:
            db.rollback()
        _send_notification_sync(
            notify_agent_error(user_id, session_id, "Session timed out")
        )
        return {"status": "timeout", "message": "Session timed out"}

    except Exception as e:
        logger.error(f"Agent session failed: {e}", exc_info=True)
        try:
            session = db.query(AgentSession).filter(AgentSession.id == sid).first()
            if session:
                session.status = "error"
                _log_action(db, sid, "orchestrator", "error", {"error": str(e)})
            db.commit()
        except Exception:
            db.rollback()

        # Notify user of agent error (sends email via send_email=True)
        _send_notification_sync(
            notify_agent_error(user_id, session_id, str(e))
        )

        # Retry on transient errors (up to max_retries)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def _run_graph_sync(graph, initial_state, db, session_id):
    """Run the graph and log agent transitions."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _run_graph_async(graph, initial_state, db, session_id)
        )
    finally:
        loop.close()


async def _run_graph_async(graph, initial_state, db, session_id):
    """Async execution of the LangGraph trading graph."""
    final_state = initial_state

    async for event in graph.astream(initial_state):
        for node_name, node_state in event.items():
            if isinstance(node_state, dict):
                final_state.update(node_state)
                agent = node_state.get("current_agent", node_name)
                _log_action(db, session_id, agent, f"node_{node_name}_completed", {
                    "iteration": final_state.get("iteration_count", 0),
                })
                db.flush()

    return final_state


@celery_app.task(bind=True, name="tasks.resume_agent_session")
def resume_agent_session(self, user_id: str, session_id: str, approval_status: str = "approved"):
    """Resume an agent session after human approval/rejection.

    Continues the LangGraph execution from the human_approval checkpoint.
    """
    db = _get_sync_db()
    sid = uuid.UUID(session_id)

    try:
        session = db.query(AgentSession).filter(AgentSession.id == sid).first()
        if not session:
            return {"status": "error", "message": "Session not found"}

        _log_action(db, sid, "orchestrator", "session_resumed", {
            "approval_status": approval_status,
        })

        if approval_status == "rejected":
            session.status = "completed"
            session.ended_at = datetime.now(timezone.utc)
            _log_action(db, sid, "orchestrator", "trades_rejected", {
                "message": "User rejected proposed trades",
            })
            db.commit()
            return {"status": "complete", "message": "Trades rejected by user"}

        # For approved: mark session active and let the next beat cycle pick it up
        session.status = "active"
        db.commit()

        return {"status": "resumed", "session_id": session_id}

    except Exception as e:
        logger.error(f"Resume session failed: {e}", exc_info=True)
        try:
            session = db.query(AgentSession).filter(AgentSession.id == sid).first()
            if session:
                session.status = "error"
                _log_action(db, sid, "orchestrator", "resume_error", {"error": str(e)})
            db.commit()
        except Exception:
            db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
