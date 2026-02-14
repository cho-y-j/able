"""Abstract base class for data providers."""

from abc import ABC, abstractmethod
import pandas as pd


class DataProvider(ABC):
    """Unified interface for market data retrieval.

    All providers must return OHLCV data in a standard pandas DataFrame format:
        Index: DatetimeIndex (named 'date')
        Columns: open, high, low, close, volume (all numeric)
    """

    @abstractmethod
    def get_ohlcv(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a stock.

        Args:
            stock_code: Stock ticker (e.g., "005930" for Samsung)
            start_date: Start date as YYYYMMDD or YYYY-MM-DD
            end_date: End date as YYYYMMDD or YYYY-MM-DD
            interval: Data interval ("1d", "1h", "1m" etc.)

        Returns:
            DataFrame with columns [open, high, low, close, volume]
            and a DatetimeIndex.
        """
        ...

    @abstractmethod
    def get_price(self, stock_code: str) -> dict:
        """Fetch current price for a stock.

        Returns:
            Dict with keys: stock_code, current_price, change, change_percent,
            volume, high, low, open
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...

    @property
    def requires_credentials(self) -> bool:
        """Whether this provider requires API credentials."""
        return True
