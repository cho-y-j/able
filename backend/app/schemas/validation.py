"""Schemas for validation API endpoints (Monte Carlo, OOS, CPCV)."""

from pydantic import BaseModel


class MonteCarloRequest(BaseModel):
    n_simulations: int = 1000
    initial_capital: float = 10_000_000


class MonteCarloResponse(BaseModel):
    mc_score: float
    simulations_run: int
    n_trades: int = 0
    statistics: dict = {}
    drawdown_stats: dict = {}
    confidence_bands: dict = {}
    percentiles: dict = {}
    message: str | None = None


class OOSRequest(BaseModel):
    oos_ratio: float = 0.3
    data_source: str = "yahoo"


class OOSResponse(BaseModel):
    oos_score: float
    oos_profitable: bool = False
    in_sample: dict = {}
    out_of_sample: dict = {}
    degradation: dict = {}
    message: str | None = None


class CPCVRequest(BaseModel):
    n_splits: int = 5
    purge_days: int = 5
    data_source: str = "yahoo"


class CPCVResponse(BaseModel):
    cpcv_score: float
    mean_sharpe: float = 0
    std_sharpe: float = 0
    positive_folds: int = 0
    total_folds: int = 0
    folds: list[dict] = []


class StrategyCompareResponse(BaseModel):
    strategies: list[dict]
    ranking: list[dict]
