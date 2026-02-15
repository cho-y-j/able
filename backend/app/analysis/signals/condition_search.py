"""KIS condition search (조건검색) signal generator."""

import pandas as pd

from app.analysis.signals.registry import register_signal


@register_signal(
    "kis_condition",
    category="condition_search",
    param_space={"condition_id": {"type": "str", "default": "0000"}},
)
def kis_condition_signal(
    df: pd.DataFrame,
    *,
    matching_stocks: list[str] | None = None,
    stock_code: str | None = None,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Convert KIS condition search results to entry/exit signals.

    This signal is a snapshot-based filter: if the target stock_code is in the
    matching_stocks list from the condition search, it generates an entry signal
    for the latest bar. Otherwise, no signal is generated.

    In practice, the caller (SignalComposer or TriggerService) pre-fetches the
    condition search results and passes them as matching_stocks.

    Args:
        df: OHLCV DataFrame
        matching_stocks: List of stock codes matching the condition search
        stock_code: Current stock being evaluated
    """
    entry = pd.Series(False, index=df.index)
    exit_ = pd.Series(False, index=df.index)

    if matching_stocks and stock_code and stock_code in matching_stocks:
        # Signal entry on the latest bar
        if len(df) > 0:
            entry.iloc[-1] = True

    return entry, exit_
