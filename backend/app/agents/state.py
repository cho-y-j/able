from typing import TypedDict, Annotated, Literal, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class MarketRegime(TypedDict):
    classification: Literal["bull", "bear", "sideways", "volatile", "crisis"]
    confidence: float
    indicators: dict
    timestamp: str


class StrategyCandidate(TypedDict):
    stock_code: str
    strategy_name: str
    parameters: dict
    backtest_metrics: dict
    validation_scores: dict
    composite_score: float


class RiskAssessment(TypedDict):
    max_position_size: float
    current_exposure: float
    risk_budget_remaining: float
    warnings: list[str]
    approved_trades: list[str]
    rejected_trades: list[str]


class ExecutionPlan(TypedDict):
    order_id: str
    stock_code: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: int
    limit_price: Optional[float]
    status: str


class TradingState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    session_id: str

    # Market Analyst outputs
    market_regime: Optional[MarketRegime]
    watchlist: list[str]  # stock codes

    # Strategy Search outputs
    strategy_candidates: list[StrategyCandidate]
    optimization_status: str

    # Risk Manager outputs
    risk_assessment: Optional[RiskAssessment]

    # Execution Agent outputs
    pending_orders: list[ExecutionPlan]
    executed_orders: list[dict]

    # Monitor outputs
    portfolio_snapshot: dict
    alerts: list[str]

    # Human-in-the-Loop
    pending_approval: bool
    pending_trades: list[dict]
    approval_status: Optional[str]  # None, "approved", "rejected"
    approval_threshold: float
    hitl_enabled: bool

    # Execution
    execution_config: Optional[dict]  # {"strategy": "auto"|"twap"|"vwap"|"direct"}
    slippage_report: list[dict]

    # Agent Memory
    memory_context: str

    # Control flow
    current_agent: str
    iteration_count: int
    should_continue: bool
    error_state: Optional[str]
