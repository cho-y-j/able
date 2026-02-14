"""Performance attribution: P&L contribution by strategy and by stock."""

from dataclasses import dataclass


@dataclass
class AttributionEntry:
    key: str  # strategy_id or stock_code
    name: str  # strategy name or stock code
    pnl: float
    pnl_pct: float  # contribution percentage of total P&L
    trade_count: int
    win_count: int
    loss_count: int
    avg_pnl_per_trade: float


@dataclass
class AttributionResult:
    total_pnl: float
    by_strategy: list[AttributionEntry]
    by_stock: list[AttributionEntry]
    best_strategy: AttributionEntry | None
    worst_strategy: AttributionEntry | None
    best_stock: AttributionEntry | None
    worst_stock: AttributionEntry | None


class PerformanceAttribution:
    """Computes P&L attribution by strategy and by stock."""

    @staticmethod
    def compute(trades: list[dict]) -> AttributionResult:
        """Calculate performance attribution from a list of trades.

        Each trade dict should contain:
            - strategy_id: str
            - strategy_name: str
            - stock_code: str
            - pnl: float
        """
        if not trades:
            return AttributionResult(
                total_pnl=0,
                by_strategy=[], by_stock=[],
                best_strategy=None, worst_strategy=None,
                best_stock=None, worst_stock=None,
            )

        total_pnl = sum(t.get("pnl", 0) for t in trades)

        by_strategy = _group_attribution(trades, key_field="strategy_id", name_field="strategy_name", total_pnl=total_pnl)
        by_stock = _group_attribution(trades, key_field="stock_code", name_field="stock_code", total_pnl=total_pnl)

        by_strategy.sort(key=lambda e: e.pnl, reverse=True)
        by_stock.sort(key=lambda e: e.pnl, reverse=True)

        return AttributionResult(
            total_pnl=total_pnl,
            by_strategy=by_strategy,
            by_stock=by_stock,
            best_strategy=by_strategy[0] if by_strategy else None,
            worst_strategy=by_strategy[-1] if by_strategy else None,
            best_stock=by_stock[0] if by_stock else None,
            worst_stock=by_stock[-1] if by_stock else None,
        )


def _group_attribution(
    trades: list[dict],
    key_field: str,
    name_field: str,
    total_pnl: float,
) -> list[AttributionEntry]:
    """Group trades by a key field and compute attribution metrics."""
    groups: dict[str, dict] = {}

    for t in trades:
        key = t.get(key_field, "unknown")
        name = t.get(name_field, key)
        pnl = t.get("pnl", 0)

        if key not in groups:
            groups[key] = {
                "name": name,
                "pnl": 0,
                "trade_count": 0,
                "win_count": 0,
                "loss_count": 0,
            }

        g = groups[key]
        g["pnl"] += pnl
        g["trade_count"] += 1
        if pnl > 0:
            g["win_count"] += 1
        elif pnl < 0:
            g["loss_count"] += 1

    entries = []
    for key, g in groups.items():
        pnl_pct = (g["pnl"] / total_pnl * 100) if total_pnl != 0 else 0
        avg_pnl = g["pnl"] / g["trade_count"] if g["trade_count"] > 0 else 0
        entries.append(AttributionEntry(
            key=key,
            name=g["name"],
            pnl=round(g["pnl"], 2),
            pnl_pct=round(pnl_pct, 2),
            trade_count=g["trade_count"],
            win_count=g["win_count"],
            loss_count=g["loss_count"],
            avg_pnl_per_trade=round(avg_pnl, 2),
        ))

    return entries
