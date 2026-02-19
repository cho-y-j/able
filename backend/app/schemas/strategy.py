from pydantic import BaseModel
from datetime import datetime


class StrategyCreate(BaseModel):
    name: str
    stock_code: str
    stock_name: str | None = None
    strategy_type: str = "indicator_based"
    indicators: list[dict] = []
    parameters: dict = {}
    entry_rules: dict = {}
    exit_rules: dict = {}
    risk_params: dict = {}
    description: str | None = None


class StrategyUpdate(BaseModel):
    name: str | None = None
    parameters: dict | None = None
    entry_rules: dict | None = None
    exit_rules: dict | None = None
    risk_params: dict | None = None
    description: str | None = None


class StrategyResponse(BaseModel):
    id: str
    name: str
    stock_code: str
    stock_name: str | None
    strategy_type: str
    indicators: list[dict]
    parameters: dict
    entry_rules: dict
    exit_rules: dict
    risk_params: dict
    composite_score: float | None
    validation_results: dict | None
    status: str
    is_auto_trading: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategySearchRequest(BaseModel):
    stock_code: str
    stock_name: str | None = None
    date_range_start: str  # YYYY-MM-DD
    date_range_end: str
    optimization_method: str = "grid"  # 'grid', 'bayesian', 'genetic'
    max_iterations: int = 500
    data_source: str = "yahoo"  # 'yahoo' or 'kis'
    market: str = "kr"  # 'kr' or 'us'
    signal_generators: list[str] | None = None


class StrategySearchResponse(BaseModel):
    job_id: str
    status: str
    message: str
