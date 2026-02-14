from typing import Callable
import numpy as np
import pandas as pd

# Global indicator registry
_REGISTRY: dict[str, Callable] = {}


def register_indicator(name: str):
    """Decorator to register an indicator function."""
    def decorator(func: Callable):
        _REGISTRY[name] = func
        return func
    return decorator


def get_indicator(name: str) -> Callable:
    base_name = name.split("_")[0].upper()
    if name in _REGISTRY:
        return _REGISTRY[name]
    if base_name in _REGISTRY:
        return _REGISTRY[base_name]
    raise ValueError(f"Unknown indicator: {name}. Available: {list(_REGISTRY.keys())}")


def list_indicators() -> list[str]:
    return sorted(_REGISTRY.keys())


def calculate_indicator(df: pd.DataFrame, name: str, **params) -> pd.DataFrame:
    """Calculate a single indicator and add it to the dataframe."""
    func = get_indicator(name)
    return func(df, **params)


def calculate_multiple(df: pd.DataFrame, indicators: list[dict]) -> pd.DataFrame:
    """Calculate multiple indicators.
    Each indicator is a dict: {"name": "RSI", "params": {"period": 14}}
    """
    result = df.copy()
    for ind in indicators:
        name = ind["name"]
        params = ind.get("params", {})
        result = calculate_indicator(result, name, **params)
    return result


def get_available_indicators() -> list[str]:
    """Return list of available indicator names including built-in strategy types."""
    built_in = ["rsi", "sma", "bollinger"]
    return sorted(set(built_in + list_indicators()))


# ---------------------------------------------------------------------------
# Signal generators for common strategy types
# ---------------------------------------------------------------------------

def _rsi_signal_generator(df: pd.DataFrame, *, period: int = 14,
                          oversold: int = 30, overbought: int = 70,
                          **_kwargs) -> tuple[pd.Series, pd.Series]:
    """Generate entry/exit signals from RSI mean-reversion strategy."""
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)

    entry_signals = rsi < oversold
    exit_signals = rsi > overbought
    return entry_signals, exit_signals


def _sma_crossover_signal_generator(df: pd.DataFrame, *, fast_period: int = 10,
                                     slow_period: int = 50,
                                     **_kwargs) -> tuple[pd.Series, pd.Series]:
    """Generate entry/exit signals from SMA crossover strategy."""
    close = df["close"]
    fast_sma = close.rolling(window=fast_period, min_periods=fast_period).mean()
    slow_sma = close.rolling(window=slow_period, min_periods=slow_period).mean()

    # Entry when fast crosses above slow, exit when fast crosses below slow
    above = fast_sma > slow_sma
    entry_signals = above & ~above.shift(1).fillna(False).astype(bool)
    exit_signals = ~above & above.shift(1).fillna(True).astype(bool)
    return entry_signals, exit_signals


def _bollinger_signal_generator(df: pd.DataFrame, *, period: int = 20,
                                 std_dev: float = 2.0,
                                 **_kwargs) -> tuple[pd.Series, pd.Series]:
    """Generate entry/exit signals from Bollinger Bands bounce strategy."""
    close = df["close"]
    sma = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    lower_band = sma - std_dev * std
    upper_band = sma + std_dev * std

    # Buy on touch of lower band, sell on touch of upper band
    entry_signals = close <= lower_band
    exit_signals = close >= upper_band
    return entry_signals, exit_signals


# Map of parameter-grid keys to signal generators
_STRATEGY_DETECTORS: list[tuple[set[str], Callable]] = [
    ({"period", "oversold", "overbought"}, _rsi_signal_generator),
    ({"fast_period", "slow_period"}, _sma_crossover_signal_generator),
    ({"period", "std_dev"}, _bollinger_signal_generator),
]


def get_signal_generator(
    param_grid: dict[str, list] | dict[str, object] | None = None,
    *,
    name: str | None = None,
) -> Callable:
    """Return a signal generator callable.

    If *name* is given, look up a signal generator from the new signal registry.
    Otherwise, fall back to legacy detection based on *param_grid* keys.

    If nothing matches, the RSI mean-reversion generator is returned as default.
    """
    if name is not None:
        from app.analysis.signals.registry import (
            get_signal_generator as _get_signal,
        )
        return _get_signal(name)

    if param_grid is not None:
        grid_keys = set(param_grid.keys())
        for required_keys, generator in _STRATEGY_DETECTORS:
            if required_keys <= grid_keys:
                return generator

    # Default fallback
    return _rsi_signal_generator
