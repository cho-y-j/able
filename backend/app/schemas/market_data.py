from pydantic import BaseModel


class OHLCVData(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceResponse(BaseModel):
    stock_code: str
    stock_name: str | None
    current_price: float
    change: float
    change_percent: float
    volume: int
    high: float
    low: float
    open: float


class IndicatorRequest(BaseModel):
    stock_code: str
    indicators: list[str]  # e.g., ['RSI_14', 'SMA_20', 'MACD_12_26_9']
    period: str = "1y"


class IndicatorResponse(BaseModel):
    stock_code: str
    indicators: dict[str, list[dict]]  # indicator_name -> time series values
