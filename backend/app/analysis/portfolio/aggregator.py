"""Portfolio aggregation: cross-strategy exposure, concentration (HHI), conflict detection."""

from dataclasses import dataclass, field


@dataclass
class StrategyExposure:
    strategy_id: str
    strategy_name: str
    stock_code: str
    quantity: int
    value: float  # quantity * current_price
    side: str  # "long" or "short"


@dataclass
class AggregationResult:
    total_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    stock_exposures: dict[str, float]  # stock_code → net value
    strategy_exposures: dict[str, float]  # strategy_id → total value
    hhi: float  # Herfindahl-Hirschman Index (0-10000)
    conflicts: list[dict]  # opposing positions on same stock
    warnings: list[str]


class PortfolioAggregator:
    """Aggregates exposures across multiple strategies and detects conflicts."""

    @staticmethod
    def aggregate(
        positions: list[StrategyExposure],
        total_capital: float = 0,
    ) -> AggregationResult:
        """Compute portfolio-level metrics from per-strategy positions.

        Args:
            positions: List of strategy-level position exposures.
            total_capital: Total portfolio capital for concentration checks.
        """
        if not positions:
            return AggregationResult(
                total_exposure=0, net_exposure=0,
                long_exposure=0, short_exposure=0,
                stock_exposures={}, strategy_exposures={},
                hhi=0, conflicts=[], warnings=[],
            )

        # Aggregate by stock and strategy
        stock_long: dict[str, float] = {}
        stock_short: dict[str, float] = {}
        strategy_totals: dict[str, float] = {}

        for pos in positions:
            val = abs(pos.value)
            sid = pos.strategy_id

            strategy_totals[sid] = strategy_totals.get(sid, 0) + val

            if pos.side == "long":
                stock_long[pos.stock_code] = stock_long.get(pos.stock_code, 0) + val
            else:
                stock_short[pos.stock_code] = stock_short.get(pos.stock_code, 0) + val

        long_exposure = sum(stock_long.values())
        short_exposure = sum(stock_short.values())
        total_exposure = long_exposure + short_exposure
        net_exposure = long_exposure - short_exposure

        # Net exposure per stock
        all_stocks = set(stock_long) | set(stock_short)
        stock_exposures = {
            s: stock_long.get(s, 0) - stock_short.get(s, 0) for s in all_stocks
        }

        # HHI — concentration index based on stock weights
        hhi = _calculate_hhi(stock_exposures, total_exposure)

        # Conflict detection — same stock with opposing positions across strategies
        conflicts = _detect_conflicts(positions)

        # Warnings
        warnings = []
        if hhi > 2500:
            warnings.append(f"High concentration (HHI={hhi:.0f}): portfolio is not diversified")
        if total_capital > 0 and total_exposure > total_capital * 0.8:
            warnings.append(
                f"Total exposure ({total_exposure:,.0f}) exceeds 80% of capital ({total_capital:,.0f})"
            )
        for stock, net_val in stock_exposures.items():
            if total_capital > 0 and abs(net_val) > total_capital * 0.15:
                warnings.append(
                    f"{stock}: single-stock exposure ({abs(net_val):,.0f}) > 15% of capital"
                )
        if conflicts:
            warnings.append(f"{len(conflicts)} conflicting position(s) detected across strategies")

        return AggregationResult(
            total_exposure=total_exposure,
            net_exposure=net_exposure,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            stock_exposures=stock_exposures,
            strategy_exposures=strategy_totals,
            hhi=hhi,
            conflicts=conflicts,
            warnings=warnings,
        )


def _calculate_hhi(stock_exposures: dict[str, float], total_exposure: float) -> float:
    """Herfindahl-Hirschman Index: sum of squared market-share percentages.

    Range: ~0 (perfect diversification) to 10000 (single position).
    """
    if total_exposure <= 0:
        return 0.0
    return sum(
        ((abs(val) / total_exposure) * 100) ** 2
        for val in stock_exposures.values()
    )


def _detect_conflicts(positions: list[StrategyExposure]) -> list[dict]:
    """Find stocks where different strategies have opposing positions."""
    stock_sides: dict[str, dict[str, list[str]]] = {}  # stock → side → [strategy_ids]

    for pos in positions:
        if pos.stock_code not in stock_sides:
            stock_sides[pos.stock_code] = {"long": [], "short": []}
        stock_sides[pos.stock_code][pos.side].append(pos.strategy_id)

    conflicts = []
    for stock, sides in stock_sides.items():
        if sides["long"] and sides["short"]:
            conflicts.append({
                "stock_code": stock,
                "long_strategies": sides["long"],
                "short_strategies": sides["short"],
            })

    return conflicts
