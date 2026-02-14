from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal


class OrderCreate(BaseModel):
    stock_code: str
    stock_name: str | None = None
    side: str  # 'buy' or 'sell'
    order_type: str = "market"  # 'market', 'limit'
    quantity: int
    limit_price: float | None = None
    strategy_id: str | None = None


class OrderResponse(BaseModel):
    id: str
    stock_code: str
    stock_name: str | None
    side: str
    order_type: str
    quantity: int
    limit_price: float | None
    filled_quantity: int
    avg_fill_price: float | None
    status: str
    submitted_at: datetime | None
    filled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: str
    stock_code: str
    stock_name: str | None
    quantity: int
    avg_cost_price: float
    current_price: float | None
    unrealized_pnl: float | None
    realized_pnl: float

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    total_balance: float
    available_cash: float
    invested_amount: float
    total_pnl: float
    total_pnl_percent: float
