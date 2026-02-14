"""Dynamic position sizing using Kelly Criterion and adaptive adjustments."""

import math


def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Calculate optimal position fraction using half-Kelly criterion.

    Args:
        win_rate: Historical win rate (0.0 to 1.0)
        avg_win: Average winning trade return (e.g., 0.05 for 5%)
        avg_loss: Average losing trade return as positive number (e.g., 0.03 for 3%)

    Returns:
        Fraction of capital to risk (0.0 to 0.25). Uses half-Kelly for safety.
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0

    b = avg_win / avg_loss  # odds ratio (win/loss)
    p = win_rate
    q = 1 - p

    kelly = (b * p - q) / b
    if kelly <= 0:
        return 0.0

    # Half-Kelly: reduces variance while retaining ~75% of optimal growth
    half_kelly = kelly * 0.5
    return min(half_kelly, 0.25)  # Cap at 25%


def calculate_position_size(
    total_capital: float,
    current_price: float,
    kelly_fraction: float,
    max_position_pct: float = 0.10,
    daily_loss_remaining: float | None = None,
) -> int:
    """Calculate number of shares to buy.

    Args:
        total_capital: Total portfolio value
        current_price: Current stock price
        kelly_fraction: Kelly-recommended fraction (from kelly_criterion)
        max_position_pct: Hard cap on single position size
        daily_loss_remaining: Remaining daily loss budget (absolute value)

    Returns:
        Number of shares (integer, Korean stocks trade in whole shares)
    """
    if current_price <= 0 or total_capital <= 0:
        return 0

    # Take the minimum of Kelly and max_position_pct
    effective_fraction = min(kelly_fraction, max_position_pct)
    position_value = total_capital * effective_fraction

    # If daily loss budget is provided, cap position value
    if daily_loss_remaining is not None and daily_loss_remaining > 0:
        # Assume worst case: 3% drop in position
        max_from_loss_budget = daily_loss_remaining / 0.03
        position_value = min(position_value, max_from_loss_budget)

    shares = int(position_value / current_price)
    return max(0, shares)


_REGIME_MULTIPLIER = {
    "bull": 1.0,
    "sideways": 0.7,
    "bear": 0.4,
    "volatile": 0.5,
    "crisis": 0.2,
}


def adaptive_position_size(
    total_capital: float,
    current_price: float,
    strategy_metrics: dict,
    market_regime: str = "sideways",
    current_drawdown: float = 0.0,
    max_position_pct: float = 0.10,
) -> dict:
    """Full adaptive position sizing: Kelly + regime adjustment + drawdown scaling.

    Args:
        total_capital: Total portfolio value
        current_price: Current stock price
        strategy_metrics: Dict with win_rate, avg_win_pct, avg_loss_pct (or proxies)
        market_regime: Current market regime classification
        current_drawdown: Current portfolio drawdown as positive fraction (e.g., 0.05 = 5%)
        max_position_pct: Hard cap on single position size

    Returns:
        Dict with shares, position_value, kelly_fraction, adjustments applied
    """
    # Extract strategy metrics
    win_rate = strategy_metrics.get("win_rate", 50) / 100
    # Derive avg win/loss from profit_factor and win_rate if not directly available
    avg_win = strategy_metrics.get("avg_win_pct", 0)
    avg_loss = strategy_metrics.get("avg_loss_pct", 0)

    if avg_win == 0 or avg_loss == 0:
        pf = strategy_metrics.get("profit_factor", 1.0)
        if pf > 0 and win_rate > 0:
            # Approximate: profit_factor = (win_rate * avg_win) / ((1 - win_rate) * avg_loss)
            # Assume avg_loss = 3% as baseline
            avg_loss = 3.0
            avg_win = pf * (1 - win_rate) * avg_loss / win_rate if win_rate > 0 else 0
        else:
            avg_win = 3.0
            avg_loss = 3.0

    # Kelly criterion
    kelly = kelly_criterion(win_rate, avg_win / 100, avg_loss / 100)

    # Regime adjustment
    regime_mult = _REGIME_MULTIPLIER.get(market_regime, 0.7)
    adjusted_kelly = kelly * regime_mult

    # Drawdown scaling: reduce size linearly as drawdown increases
    # At 15% drawdown, reduce to 50% of position; at 25%+, reduce to 20%
    dd_scale = 1.0
    if current_drawdown > 0.05:
        dd_scale = max(0.2, 1.0 - (current_drawdown - 0.05) * 4)

    final_fraction = adjusted_kelly * dd_scale

    # Calculate shares
    shares = calculate_position_size(
        total_capital, current_price, final_fraction, max_position_pct,
    )
    position_value = shares * current_price

    return {
        "shares": shares,
        "position_value": round(position_value, 0),
        "position_pct": round(position_value / total_capital * 100, 2) if total_capital > 0 else 0,
        "kelly_raw": round(kelly * 100, 2),
        "kelly_adjusted": round(final_fraction * 100, 2),
        "adjustments": {
            "regime": market_regime,
            "regime_multiplier": regime_mult,
            "drawdown": round(current_drawdown * 100, 2),
            "drawdown_scale": round(dd_scale, 2),
        },
    }
