from pydantic import BaseModel
from datetime import datetime


class SignalEntry(BaseModel):
    type: str  # "recommended", "volume_spike", "vwap_deviation", "volume_breakout", "kis_condition"
    strategy_type: str | None = None  # for recommended signals
    params: dict = {}
    weight: float = 1.0
    condition_id: str | None = None  # for kis_condition
    condition_name: str | None = None


class SignalConfig(BaseModel):
    combinator: str = "AND"  # "AND", "OR", "MIN_AGREE", "WEIGHTED"
    min_agree: int = 2  # for MIN_AGREE mode
    weight_threshold: float = 0.5  # for WEIGHTED mode
    signals: list[SignalEntry] = []


class RecipeCreate(BaseModel):
    name: str
    description: str | None = None
    signal_config: dict
    custom_filters: dict = {}
    stock_codes: list[str] = []
    risk_config: dict = {}


class RecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    signal_config: dict | None = None
    custom_filters: dict | None = None
    stock_codes: list[str] | None = None
    risk_config: dict | None = None


class RecipeResponse(BaseModel):
    id: str
    name: str
    description: str | None
    signal_config: dict
    custom_filters: dict
    stock_codes: list[str]
    risk_config: dict
    is_active: bool
    is_template: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipeBacktestRequest(BaseModel):
    stock_code: str
    date_range_start: str | None = None
    date_range_end: str | None = None


class TradeLogEntry(BaseModel):
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_percent: float
    hold_days: int


class EquityCurvePoint(BaseModel):
    date: str
    value: float


class RecipeBacktestResponse(BaseModel):
    composite_score: float | None
    grade: str | None
    metrics: dict
    equity_curve: list[EquityCurvePoint] = []
    trade_log: list[TradeLogEntry] = []


# ── Execution schemas ──


class RecipeExecutionRequest(BaseModel):
    stock_code: str | None = None  # Execute for specific stock, or all if None


class RecipeOrderResponse(BaseModel):
    id: str
    stock_code: str
    side: str
    order_type: str
    quantity: int
    avg_fill_price: float | None
    kis_order_id: str | None
    status: str
    execution_strategy: str | None
    slippage_bps: float | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecipeExecutionResponse(BaseModel):
    recipe_id: str
    orders: list[RecipeOrderResponse]
    total_submitted: int
    total_failed: int
