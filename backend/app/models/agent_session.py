import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class AgentSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    session_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    market_regime: Mapped[str | None] = mapped_column(String(20))
    strategy_candidates: Mapped[dict] = mapped_column(JSONB, default=list)
    risk_assessment: Mapped[dict | None] = mapped_column(JSONB)
    execution_summary: Mapped[dict | None] = mapped_column(JSONB)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[dict] = mapped_column(JSONB, default=list)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    actions = relationship("AgentAction", back_populates="session", cascade="all, delete-orphan")


class AgentAction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_actions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    session = relationship("AgentSession", back_populates="actions")
