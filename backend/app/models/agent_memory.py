"""Agent memory model for cross-session learning."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class AgentMemory(Base, UUIDMixin, TimestampMixin):
    """Stores agent observations and learnings across sessions.

    Categories:
        - market_pattern: Observed market patterns and their outcomes
        - strategy_result: Strategy performance outcomes
        - risk_event: Risk events (drawdown, loss limit breaches)
        - trade_outcome: Individual trade outcomes and lessons
        - user_preference: Learned user preferences
    """
    __tablename__ = "agent_memories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="SET NULL"),
    )

    __table_args__ = (
        Index("ix_agent_memories_user_category", "user_id", "category"),
        Index("ix_agent_memories_importance", "importance"),
    )
