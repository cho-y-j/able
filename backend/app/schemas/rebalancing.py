"""Schemas for portfolio rebalancing endpoints."""

from pydantic import BaseModel


# ─── Recipe Allocations ──────────────────────────────────────


class PositionSlice(BaseModel):
    stock_code: str
    quantity: int
    value: float
    weight_pct: float


class RecipeAllocation(BaseModel):
    recipe_id: str
    recipe_name: str
    is_active: bool
    target_weight_pct: float
    actual_weight_pct: float
    actual_value: float
    target_value: float
    drift_pct: float
    stock_codes: list[str]
    positions: list[PositionSlice]


class RecipeAllocationResponse(BaseModel):
    total_capital: float
    available_cash: float
    allocated_capital: float
    unallocated_pct: float
    recipes: list[RecipeAllocation]
    warnings: list[str]


# ─── Recipe Conflicts ────────────────────────────────────────


class ConflictRecipe(BaseModel):
    recipe_id: str
    recipe_name: str
    position_size_pct: float


class ConflictEntry(BaseModel):
    stock_code: str
    recipes: list[ConflictRecipe]
    combined_target_pct: float
    current_position_value: float
    risk_level: str  # "low", "medium", "high"


class RecipeConflictResponse(BaseModel):
    conflicts: list[ConflictEntry]
    total_overlapping_stocks: int
    risk_warnings: list[str]


# ─── Rebalancing Suggestions ────────────────────────────────


class RebalancingSuggestion(BaseModel):
    recipe_id: str
    recipe_name: str
    stock_code: str
    action: str  # "buy", "sell", "hold"
    current_quantity: int
    target_quantity: int
    delta_quantity: int
    estimated_value: float
    current_price: float
    reason: str


class RebalancingSummary(BaseModel):
    total_buys: int
    total_sells: int
    total_buy_value: float
    total_sell_value: float
    net_cash_required: float
    available_cash: float
    feasible: bool


class RebalancingSuggestionResponse(BaseModel):
    suggestions: list[RebalancingSuggestion]
    summary: RebalancingSummary
    warnings: list[str]
