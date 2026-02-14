"""Tests for agent memory system and HITL approval node."""

import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from app.agents.memory import AgentMemoryManager
from app.models.agent_memory import AgentMemory
from app.agents.nodes.human_approval import (
    human_approval_node,
    DEFAULT_APPROVAL_THRESHOLD,
    CRISIS_APPROVAL_THRESHOLD,
)


# ── AgentMemory Model ────────────────────────────────────

class TestAgentMemoryModel:
    def test_model_has_required_fields(self):
        mem = AgentMemory(
            user_id=uuid.uuid4(),
            agent_name="market_analyst",
            category="market_pattern",
            content="KOSPI showed strong bullish divergence",
            extra_data={"regime": "bull"},
            importance=0.8,
        )
        assert mem.agent_name == "market_analyst"
        assert mem.category == "market_pattern"
        assert mem.importance == 0.8

    def test_default_values(self):
        mem = AgentMemory(
            user_id=uuid.uuid4(),
            agent_name="risk_manager",
            category="risk_event",
            content="Daily loss limit breached",
        )
        # Defaults are applied at DB level, but None/unset are fine before flush
        assert mem.last_accessed_at is None
        assert mem.expires_at is None
        assert mem.session_id is None


# ── AgentMemoryManager ───────────────────────────────────

class TestMemoryManagerSummarize:
    def test_summarize_empty(self):
        mgr = AgentMemoryManager(user_id=uuid.uuid4(), db=MagicMock())
        result = mgr.summarize_memories([])
        assert result == ""

    def test_summarize_basic(self):
        mgr = AgentMemoryManager(user_id=uuid.uuid4(), db=MagicMock())
        memories = [
            _make_memory("market_pattern", "KOSPI bullish above 2500"),
            _make_memory("strategy_result", "RSI strategy worked well in bull"),
        ]
        result = mgr.summarize_memories(memories)
        assert "[market_pattern]" in result
        assert "[strategy_result]" in result
        assert "KOSPI bullish above 2500" in result

    def test_summarize_truncation(self):
        mgr = AgentMemoryManager(user_id=uuid.uuid4(), db=MagicMock())
        memories = [_make_memory("test", "x" * 3000)]
        result = mgr.summarize_memories(memories, max_tokens=100)
        assert len(result) <= 500  # 100 tokens * 4 chars + truncation msg
        assert "truncated" in result


# ── Human Approval Node ──────────────────────────────────

class TestHumanApprovalNode:
    @pytest.mark.asyncio
    async def test_skip_when_hitl_disabled(self):
        state = _make_state(hitl_enabled=False)
        result = await human_approval_node(state)
        assert result.get("pending_approval") is None
        assert result["current_agent"] == "human_approval"

    @pytest.mark.asyncio
    async def test_no_approval_needed_below_threshold(self):
        state = _make_state(
            hitl_enabled=True,
            approved_trades=["005930"],
            candidates=[{
                "stock_code": "005930",
                "position_sizing": {"position_value": 1_000_000, "shares": 10},
            }],
            approval_threshold=5_000_000,
        )
        result = await human_approval_node(state)
        assert not result.get("pending_approval")

    @pytest.mark.asyncio
    async def test_approval_required_above_threshold(self):
        state = _make_state(
            hitl_enabled=True,
            approved_trades=["005930"],
            candidates=[{
                "stock_code": "005930",
                "position_sizing": {"position_value": 6_000_000, "shares": 60, "kelly_adjusted": 5.0},
            }],
            approval_threshold=5_000_000,
        )
        result = await human_approval_node(state)
        assert result["pending_approval"] is True
        assert len(result["pending_trades"]) == 1
        assert result["pending_trades"][0]["stock_code"] == "005930"

    @pytest.mark.asyncio
    async def test_crisis_lowers_threshold(self):
        state = _make_state(
            hitl_enabled=True,
            approved_trades=["005930"],
            candidates=[{
                "stock_code": "005930",
                "position_sizing": {"position_value": 3_000_000, "shares": 30, "kelly_adjusted": 3.0},
            }],
            approval_threshold=5_000_000,
            market_regime="crisis",
        )
        result = await human_approval_node(state)
        assert result["pending_approval"] is True

    @pytest.mark.asyncio
    async def test_user_approved_proceeds(self):
        state = _make_state(
            hitl_enabled=True,
            approval_status="approved",
        )
        result = await human_approval_node(state)
        assert result.get("pending_approval") is False
        assert "approved" in result["messages"][0].content.lower()

    @pytest.mark.asyncio
    async def test_user_rejected_clears_trades(self):
        state = _make_state(
            hitl_enabled=True,
            approval_status="rejected",
            approved_trades=["005930", "035720"],
        )
        result = await human_approval_node(state)
        assert result.get("pending_approval") is False
        risk = result.get("risk_assessment", {})
        assert risk.get("approved_trades") == []
        assert "005930" in risk.get("rejected_trades", [])


# ── Orchestrator Graph Routing ───────────────────────────

class TestOrchestratorRouting:
    def test_should_approve_routes_to_hitl_when_enabled(self):
        from app.agents.orchestrator import should_approve
        state = _make_state(
            hitl_enabled=True,
            risk_assessment={"approved_trades": ["005930"]},
        )
        assert should_approve(state) == "human_approval"

    def test_should_approve_routes_to_execution_when_disabled(self):
        from app.agents.orchestrator import should_approve
        state = _make_state(
            hitl_enabled=False,
            risk_assessment={"approved_trades": ["005930"]},
        )
        assert should_approve(state) == "execution"

    def test_should_approve_routes_to_monitor_when_no_trades(self):
        from app.agents.orchestrator import should_approve
        state = _make_state(risk_assessment={"approved_trades": []})
        assert should_approve(state) == "monitor"

    def test_after_approval_halts_when_pending(self):
        from app.agents.orchestrator import after_approval
        from langgraph.graph import END
        state = _make_state(pending_approval=True)
        assert after_approval(state) == END

    def test_after_approval_continues_to_execution(self):
        from app.agents.orchestrator import after_approval
        state = _make_state(
            pending_approval=False,
            risk_assessment={"approved_trades": ["005930"]},
        )
        assert after_approval(state) == "execution"


# ── State Fields ─────────────────────────────────────────

class TestStateFields:
    def test_new_hitl_fields_exist(self):
        from app.agents.state import TradingState
        annotations = TradingState.__annotations__
        assert "pending_approval" in annotations
        assert "approval_status" in annotations
        assert "hitl_enabled" in annotations
        assert "approval_threshold" in annotations
        assert "pending_trades" in annotations
        assert "memory_context" in annotations


# ── Helpers ──────────────────────────────────────────────

def _make_memory(category: str, content: str, importance: float = 0.5) -> AgentMemory:
    mem = AgentMemory(
        user_id=uuid.uuid4(),
        agent_name="test",
        category=category,
        content=content,
        importance=importance,
    )
    mem.access_count = 0
    return mem


def _make_state(**overrides) -> dict:
    base = {
        "messages": [],
        "user_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "market_regime": {"classification": overrides.pop("market_regime", "sideways")} if "market_regime" in overrides else {},
        "watchlist": [],
        "strategy_candidates": overrides.pop("candidates", []),
        "optimization_status": "",
        "risk_assessment": overrides.pop("risk_assessment", {"approved_trades": overrides.pop("approved_trades", []), "rejected_trades": [], "warnings": []}),
        "pending_orders": [],
        "executed_orders": [],
        "portfolio_snapshot": {},
        "alerts": [],
        "current_agent": "",
        "iteration_count": 0,
        "should_continue": True,
        "error_state": None,
        "pending_approval": False,
        "pending_trades": [],
        "approval_status": None,
        "approval_threshold": DEFAULT_APPROVAL_THRESHOLD,
        "hitl_enabled": False,
        "memory_context": "",
    }
    base.update(overrides)
    return base
