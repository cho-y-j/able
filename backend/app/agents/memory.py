"""Agent Memory Manager: recall, record, and summarize cross-session learnings."""

import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.agent_memory import AgentMemory

logger = logging.getLogger(__name__)


class AgentMemoryManager:
    """Manages agent memories for cross-session learning.

    Supports both async (FastAPI) and sync (Celery) database sessions.
    """

    def __init__(self, user_id: str | uuid.UUID, db: AsyncSession | Session):
        self.user_id = uuid.UUID(str(user_id))
        self.db = db
        self._is_async = isinstance(db, AsyncSession)

    # ── Record ──────────────────────────────────────────────

    async def record_async(
        self,
        agent_name: str,
        category: str,
        content: str,
        extra_data: dict | None = None,
        importance: float = 0.5,
        session_id: str | None = None,
    ) -> AgentMemory:
        memory = AgentMemory(
            user_id=self.user_id,
            agent_name=agent_name,
            category=category,
            content=content,
            extra_data=extra_data or {},
            importance=importance,
            session_id=uuid.UUID(session_id) if session_id else None,
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    def record_sync(
        self,
        agent_name: str,
        category: str,
        content: str,
        extra_data: dict | None = None,
        importance: float = 0.5,
        session_id: str | None = None,
    ) -> AgentMemory:
        memory = AgentMemory(
            user_id=self.user_id,
            agent_name=agent_name,
            category=category,
            content=content,
            extra_data=extra_data or {},
            importance=importance,
            session_id=uuid.UUID(session_id) if session_id else None,
        )
        self.db.add(memory)
        self.db.flush()
        return memory

    # ── Recall ──────────────────────────────────────────────

    async def recall_async(
        self,
        agent_name: str | None = None,
        category: str | None = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[AgentMemory]:
        """Retrieve relevant memories, ordered by importance then recency."""
        stmt = (
            select(AgentMemory)
            .where(AgentMemory.user_id == self.user_id)
            .where(AgentMemory.importance >= min_importance)
        )
        if agent_name:
            stmt = stmt.where(AgentMemory.agent_name == agent_name)
        if category:
            stmt = stmt.where(AgentMemory.category == category)

        # Filter out expired memories
        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            (AgentMemory.expires_at == None) | (AgentMemory.expires_at > now)  # noqa: E711
        )
        stmt = stmt.order_by(desc(AgentMemory.importance), desc(AgentMemory.created_at))
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        memories = list(result.scalars().all())

        # Bump access counts
        if memories:
            ids = [m.id for m in memories]
            await self.db.execute(
                update(AgentMemory)
                .where(AgentMemory.id.in_(ids))
                .values(access_count=AgentMemory.access_count + 1, last_accessed_at=now)
            )

        return memories

    def recall_sync(
        self,
        agent_name: str | None = None,
        category: str | None = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[AgentMemory]:
        """Retrieve relevant memories (sync version for Celery tasks)."""
        stmt = (
            select(AgentMemory)
            .where(AgentMemory.user_id == self.user_id)
            .where(AgentMemory.importance >= min_importance)
        )
        if agent_name:
            stmt = stmt.where(AgentMemory.agent_name == agent_name)
        if category:
            stmt = stmt.where(AgentMemory.category == category)

        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            (AgentMemory.expires_at == None) | (AgentMemory.expires_at > now)  # noqa: E711
        )
        stmt = stmt.order_by(desc(AgentMemory.importance), desc(AgentMemory.created_at))
        stmt = stmt.limit(limit)

        result = self.db.execute(stmt)
        memories = list(result.scalars().all())

        if memories:
            ids = [m.id for m in memories]
            self.db.execute(
                update(AgentMemory)
                .where(AgentMemory.id.in_(ids))
                .values(access_count=AgentMemory.access_count + 1, last_accessed_at=now)
            )

        return memories

    # ── Summarize ───────────────────────────────────────────

    def summarize_memories(self, memories: list[AgentMemory], max_tokens: int = 500) -> str:
        """Build a concise context string from memories for LLM prompt injection."""
        if not memories:
            return ""

        lines = []
        for m in memories:
            prefix = f"[{m.category}]"
            lines.append(f"{prefix} {m.content}")

        summary = "\n".join(lines)
        # Rough truncation (4 chars ≈ 1 token)
        max_chars = max_tokens * 4
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "\n... (truncated)"

        return summary

    # ── Decay ───────────────────────────────────────────────

    async def decay_old_memories_async(self, decay_factor: float = 0.95, min_importance: float = 0.1):
        """Gradually reduce importance of old, unused memories."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(AgentMemory)
            .where(
                and_(
                    AgentMemory.user_id == self.user_id,
                    AgentMemory.importance > min_importance,
                )
            )
            .values(importance=AgentMemory.importance * decay_factor)
        )

    def decay_old_memories_sync(self, decay_factor: float = 0.95, min_importance: float = 0.1):
        """Sync version of memory decay."""
        self.db.execute(
            update(AgentMemory)
            .where(
                and_(
                    AgentMemory.user_id == self.user_id,
                    AgentMemory.importance > min_importance,
                )
            )
            .values(importance=AgentMemory.importance * decay_factor)
        )
