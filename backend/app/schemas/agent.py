from pydantic import BaseModel
from datetime import datetime


class AgentStartRequest(BaseModel):
    session_type: str = "full_cycle"  # 'full_cycle', 'analysis_only', 'execution_only'
    stock_codes: list[str] = []
    hitl_enabled: bool = False
    approval_threshold: float = 5_000_000  # KRW


class AgentStopRequest(BaseModel):
    session_id: str


class AgentStatusResponse(BaseModel):
    session_id: str
    status: str
    session_type: str
    current_agent: str | None = None
    market_regime: str | None
    iteration_count: int
    active_strategies: int = 0
    started_at: datetime
    recent_actions: list[dict] = []


class AgentSessionResponse(BaseModel):
    id: str
    session_type: str
    status: str
    market_regime: str | None
    iteration_count: int
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    session_id: str


class ApprovalResponse(BaseModel):
    session_id: str
    status: str
    message: str
