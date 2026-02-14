"""Signal generator registry for trading strategies.

Each signal generator converts OHLCV data + parameters into entry/exit boolean
signals used by the backtest engine and optimization pipeline.
"""

from typing import Callable

import pandas as pd

SignalGenerator = Callable[..., tuple[pd.Series, pd.Series]]

_SIGNAL_REGISTRY: dict[str, dict] = {}


def register_signal(
    name: str,
    *,
    category: str = "general",
    param_space: dict[str, dict] | None = None,
):
    """Decorator to register a signal generator with its default param search space."""

    def decorator(func: SignalGenerator):
        _SIGNAL_REGISTRY[name] = {
            "generator": func,
            "param_space": param_space or {},
            "category": category,
        }
        return func

    return decorator


def get_signal_generator(name: str) -> SignalGenerator:
    """Get signal generator function by name."""
    if name not in _SIGNAL_REGISTRY:
        available = ", ".join(sorted(_SIGNAL_REGISTRY.keys()))
        raise ValueError(f"Unknown signal: {name}. Available: [{available}]")
    return _SIGNAL_REGISTRY[name]["generator"]


def get_signal_param_space(name: str) -> dict[str, dict]:
    """Get default parameter search space for a signal generator."""
    if name not in _SIGNAL_REGISTRY:
        raise ValueError(f"Unknown signal: {name}")
    return _SIGNAL_REGISTRY[name]["param_space"]


def list_signal_generators() -> list[str]:
    """Return sorted list of all registered signal generator names."""
    return sorted(_SIGNAL_REGISTRY.keys())


def list_signal_generators_by_category() -> dict[str, list[str]]:
    """Return signal generators grouped by category."""
    result: dict[str, list[str]] = {}
    for name, entry in _SIGNAL_REGISTRY.items():
        cat = entry["category"]
        result.setdefault(cat, []).append(name)
    for signals in result.values():
        signals.sort()
    return result
