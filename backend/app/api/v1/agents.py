import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.agent_session import AgentSession, AgentAction
from app.schemas.agent import (
    AgentStartRequest, AgentStopRequest,
    AgentStatusResponse, AgentSessionResponse,
    ApprovalRequest, ApprovalResponse,
)
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.post("/start", response_model=AgentStatusResponse,
              summary="Start an AI agent session",
              description="Launch a LangGraph trading agent. Types: full_cycle, analysis_only, execution_only. Runs asynchronously via Celery.")
async def start_agent_session(
    req: AgentStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Check for existing active session
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.user_id == user.id,
            AgentSession.status == "active",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An active session already exists")

    session = AgentSession(
        user_id=user.id,
        session_type=req.session_type,
        status="active",
    )
    db.add(session)
    await db.flush()

    # Start LangGraph orchestration via Celery task
    from app.tasks.agent_tasks import run_agent_session
    run_agent_session.delay(
        user_id=str(user.id),
        session_id=str(session.id),
        session_type=req.session_type,
    )

    # Notify user
    try:
        from app.services.notification_service import notify_agent_started
        await notify_agent_started(str(user.id), str(session.id), req.session_type, db)
    except Exception:
        pass  # Non-critical

    return AgentStatusResponse(
        session_id=str(session.id),
        status="active",
        session_type=session.session_type,
        market_regime=None,
        iteration_count=0,
        started_at=session.started_at,
    )


@router.post("/stop", summary="Stop an active agent session")
async def stop_agent_session(
    req: AgentStopRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == uuid.UUID(req.session_id),
            AgentSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "stopped"
    return {"status": "stopped", "session_id": str(session.id)}


@router.get("/status", response_model=AgentStatusResponse | None,
             summary="Get active agent status",
             description="Returns the currently active agent session with recent actions, or null if no active session.")
async def get_agent_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.user_id == user.id,
            AgentSession.status == "active",
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    # Get recent actions
    actions_result = await db.execute(
        select(AgentAction).where(AgentAction.session_id == session.id)
        .order_by(AgentAction.created_at.desc()).limit(10)
    )
    actions = actions_result.scalars().all()

    return AgentStatusResponse(
        session_id=str(session.id),
        status=session.status,
        session_type=session.session_type,
        market_regime=session.market_regime,
        iteration_count=session.iteration_count,
        started_at=session.started_at,
        recent_actions=[{
            "agent": a.agent_name,
            "action": a.action_type,
            "timestamp": str(a.created_at),
        } for a in actions],
    )


@router.get("/sessions", response_model=list[AgentSessionResponse], summary="List agent session history")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 20,
):
    result = await db.execute(
        select(AgentSession).where(AgentSession.user_id == user.id)
        .order_by(AgentSession.created_at.desc()).limit(limit)
    )
    sessions = result.scalars().all()
    return [AgentSessionResponse(
        id=str(s.id),
        session_type=s.session_type,
        status=s.status,
        market_regime=s.market_regime,
        iteration_count=s.iteration_count,
        started_at=s.started_at,
        ended_at=s.ended_at,
    ) for s in sessions]


@router.post("/sessions/{session_id}/approve", response_model=ApprovalResponse,
              summary="Approve pending trades (HITL)",
              description="Human-in-the-loop approval. Resumes agent execution for pending trades.")
async def approve_trades(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve pending trades in a HITL-enabled session."""
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == uuid.UUID(session_id),
            AgentSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Session is not pending approval (status: {session.status})")

    session.status = "active"

    # Log the approval action
    action = AgentAction(
        session_id=session.id,
        agent_name="human_approval",
        action_type="user_approved",
        output_data={"decision": "approved"},
    )
    db.add(action)

    # Resume agent via Celery with approval state
    from app.tasks.agent_tasks import resume_agent_session
    resume_agent_session.delay(
        user_id=str(user.id),
        session_id=session_id,
        approval_status="approved",
    )

    return ApprovalResponse(
        session_id=session_id,
        status="approved",
        message="Trades approved. Resuming execution.",
    )


@router.post("/sessions/{session_id}/reject", response_model=ApprovalResponse,
              summary="Reject pending trades (HITL)",
              description="Reject pending trades. Agent skips execution and continues monitoring.")
async def reject_trades(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reject pending trades in a HITL-enabled session."""
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == uuid.UUID(session_id),
            AgentSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Session is not pending approval (status: {session.status})")

    session.status = "active"

    action = AgentAction(
        session_id=session.id,
        agent_name="human_approval",
        action_type="user_rejected",
        output_data={"decision": "rejected"},
    )
    db.add(action)

    from app.tasks.agent_tasks import resume_agent_session
    resume_agent_session.delay(
        user_id=str(user.id),
        session_id=session_id,
        approval_status="rejected",
    )

    return ApprovalResponse(
        session_id=session_id,
        status="rejected",
        message="Trades rejected. Skipping execution.",
    )
