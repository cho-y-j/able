"""Real-time trigger service for evaluating active recipe conditions."""

import logging
from collections import defaultdict

import pandas as pd

from app.analysis.composer import SignalComposer

logger = logging.getLogger(__name__)


class TriggerService:
    """Evaluate real-time data against active recipe conditions.

    Used by the WebSocket listener and periodic polling tasks to detect
    when recipe conditions are met and trigger order execution.
    """

    def __init__(self):
        self.composer = SignalComposer()
        # In-memory tick buffer: stock_code -> list of tick dicts
        self._tick_buffer: dict[str, list[dict]] = defaultdict(list)
        self._buffer_max_size = 500  # Keep last N ticks per stock

    def add_tick(self, stock_code: str, tick_data: dict):
        """Add a real-time tick to the buffer."""
        buf = self._tick_buffer[stock_code]
        buf.append(tick_data)
        if len(buf) > self._buffer_max_size:
            self._tick_buffer[stock_code] = buf[-self._buffer_max_size:]

    def get_recent_df(self, stock_code: str) -> pd.DataFrame | None:
        """Convert tick buffer to OHLCV-like DataFrame for signal evaluation."""
        ticks = self._tick_buffer.get(stock_code, [])
        if len(ticks) < 10:
            return None

        df = pd.DataFrame(ticks)
        # Ensure required columns exist
        required = {"close", "open", "high", "low", "volume"}
        if not required.issubset(df.columns):
            # Map from tick data format
            if "current_price" in df.columns:
                df["close"] = df["current_price"]
                df["open"] = df["current_price"]
                df["high"] = df["current_price"]
                df["low"] = df["current_price"]
            if not required.issubset(df.columns):
                return None

        return df

    def evaluate_recipe(
        self, stock_code: str, signal_config: dict, custom_filters: dict | None = None
    ) -> dict:
        """Evaluate a single recipe's conditions against buffered data.

        Returns:
            {
                "should_enter": bool,
                "should_exit": bool,
                "signal_details": {...},
            }
        """
        df = self.get_recent_df(stock_code)
        if df is None:
            return {"should_enter": False, "should_exit": False, "signal_details": {"reason": "insufficient_data"}}

        try:
            entry, exit_ = self.composer.compose(df, signal_config)
        except Exception as e:
            logger.error(f"Signal composition failed for {stock_code}: {e}")
            return {"should_enter": False, "should_exit": False, "signal_details": {"error": str(e)}}

        # Check latest bar
        should_enter = bool(entry.iloc[-1]) if len(entry) > 0 else False
        should_exit = bool(exit_.iloc[-1]) if len(exit_) > 0 else False

        # Apply custom filters
        if should_enter and custom_filters:
            should_enter = self._check_custom_filters(stock_code, custom_filters, df)

        return {
            "should_enter": should_enter,
            "should_exit": should_exit,
            "signal_details": {
                "entry_signals_last_5": entry.tail(5).tolist() if len(entry) >= 5 else entry.tolist(),
                "exit_signals_last_5": exit_.tail(5).tolist() if len(exit_) >= 5 else exit_.tolist(),
            },
        }

    def _check_custom_filters(
        self, stock_code: str, filters: dict, df: pd.DataFrame
    ) -> bool:
        """Apply custom filters (volume_min, price_range, etc.)."""
        latest = df.iloc[-1] if len(df) > 0 else None
        if latest is None:
            return False

        # Volume minimum filter
        volume_min = filters.get("volume_min")
        if volume_min and latest.get("volume", 0) < volume_min:
            return False

        # Price range filter
        price_range = filters.get("price_range")
        if price_range and len(price_range) == 2:
            price = latest.get("close", 0)
            if price < price_range[0] or price > price_range[1]:
                return False

        return True

    def clear_buffer(self, stock_code: str | None = None):
        """Clear tick buffer for a stock or all stocks."""
        if stock_code:
            self._tick_buffer.pop(stock_code, None)
        else:
            self._tick_buffer.clear()
