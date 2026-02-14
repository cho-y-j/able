"""Risk Manager Agent: Controls position sizing and risk limits.

Uses Kelly Criterion for dynamic sizing, enforces daily loss limits,
implements drawdown recovery mode, and checks cross-strategy exposure.
"""

from langchain_core.messages import AIMessage
from app.agents.state import TradingState
from app.analysis.risk.position_sizing import adaptive_position_size
from app.analysis.risk.limits import RiskLimits
from app.analysis.portfolio.aggregator import PortfolioAggregator, StrategyExposure


SYSTEM_PROMPT = """You are the Risk Manager agent in an AI-powered trading team.

Your responsibilities:
1. Evaluate proposed trades against risk parameters
2. Calculate appropriate position sizes using Kelly Criterion
3. Enforce daily loss limits and maximum exposure
4. Approve or reject trade proposals
5. Monitor portfolio-level risk and drawdown

Risk rules:
- Max single position: 10% of total portfolio (5% in crisis)
- Max daily loss: 3% of total portfolio
- Max total exposure: 80% of portfolio
- Stop-loss mandatory for all positions
- Crisis regime: reduce all limits by 50%
- Drawdown > 15%: halt all new trades

Always err on the side of caution. Reject unclear or high-risk trades.

Respond with approval/rejection decisions in JSON format."""


async def risk_manager_node(state: TradingState) -> dict:
    """LangGraph node: assesses risk and approves/rejects trades."""

    candidates = state.get("strategy_candidates", [])
    regime = state.get("market_regime", {})
    classification = regime.get("classification", "sideways") if regime else "sideways"
    portfolio = state.get("portfolio_snapshot", {})

    # Portfolio state
    total_capital = portfolio.get("total_balance", 10_000_000)
    current_exposure = portfolio.get("total_exposure", 0)
    daily_pnl = portfolio.get("daily_pnl", 0)
    current_drawdown = portfolio.get("current_drawdown", 0)

    # Adjust limits for crisis regime
    crisis_factor = 0.5 if classification == "crisis" else 1.0
    limits = RiskLimits(
        total_capital=total_capital,
        max_daily_loss_pct=0.03 * crisis_factor,
        max_total_exposure_pct=0.80 * crisis_factor,
        max_single_position_pct=0.10 * crisis_factor,
    )

    # Check drawdown recovery mode
    dd_check = limits.drawdown_recovery_mode(current_drawdown)
    if dd_check["action"] == "HALT_TRADING":
        return {
            "messages": [AIMessage(
                content=f"[Risk Manager] {dd_check['message']}. All trades rejected."
            )],
            "risk_assessment": {
                "max_position_size": 0,
                "current_exposure": current_exposure,
                "risk_budget_remaining": 0,
                "warnings": [dd_check["message"]],
                "approved_trades": [],
                "rejected_trades": [c.get("stock_code", "?") for c in candidates],
                "drawdown_mode": dd_check,
            },
            "current_agent": "risk_manager",
        }

    # Check daily loss
    daily_check = limits.daily_loss_check(daily_pnl, 0)
    if daily_check["breached"]:
        return {
            "messages": [AIMessage(
                content=f"[Risk Manager] Daily loss limit breached: {daily_check['total_pnl']:,.0f}. "
                        f"All trades rejected until next session."
            )],
            "risk_assessment": {
                "max_position_size": 0,
                "current_exposure": current_exposure,
                "risk_budget_remaining": 0,
                "warnings": [f"Daily loss limit breached: {daily_check['pnl_pct']:.1f}%"],
                "approved_trades": [],
                "rejected_trades": [c.get("stock_code", "?") for c in candidates],
                "daily_loss_check": daily_check,
            },
            "current_agent": "risk_manager",
        }

    # Cross-strategy exposure check from existing positions
    existing_positions = state.get("existing_positions", [])
    if existing_positions:
        exposures = [
            StrategyExposure(
                strategy_id=str(p.get("strategy_id", "manual")),
                strategy_name=p.get("strategy_name", "unknown"),
                stock_code=p.get("stock_code", ""),
                quantity=p.get("quantity", 0),
                value=p.get("value", 0),
                side="long" if p.get("quantity", 0) > 0 else "short",
            )
            for p in existing_positions
        ]
        agg = PortfolioAggregator.aggregate(exposures, total_capital)
        if agg.warnings:
            warnings_from_agg = agg.warnings
        else:
            warnings_from_agg = []
    else:
        agg = None
        warnings_from_agg = []

    # Evaluate each candidate
    approved = []
    rejected = []
    warnings = list(warnings_from_agg)

    for candidate in candidates:
        stock_code = candidate.get("stock_code", "unknown")
        score = candidate.get("composite_score", 0)

        # Minimum score gate
        if score < 40 and candidate.get("backtest_metrics"):
            rejected.append(stock_code)
            warnings.append(f"{stock_code}: low composite score ({score:.1f})")
            continue

        # Get price estimate
        price = candidate.get("current_price", 0)
        if price <= 0:
            price = candidate.get("backtest_metrics", {}).get("avg_price", 50000)

        # Adaptive position sizing with Kelly
        sizing = adaptive_position_size(
            total_capital=total_capital,
            current_price=price,
            strategy_metrics=candidate.get("backtest_metrics", {}),
            market_regime=classification,
            current_drawdown=current_drawdown,
            max_position_pct=limits.max_single_position_pct,
        )

        # Apply drawdown recovery scaling
        if dd_check["recovery_mode"]:
            sizing["shares"] = int(sizing["shares"] * dd_check["position_scale"])
            sizing["position_value"] = sizing["shares"] * price

        order_value = sizing["position_value"]

        # Check against risk limits
        limit_check = limits.check_order(
            order_value=order_value,
            current_exposure=current_exposure,
            daily_pnl=daily_pnl,
            stock_code=stock_code,
        )

        if not limit_check["approved"]:
            rejected.append(stock_code)
            warnings.append(f"{stock_code}: {limit_check['reason']}")
            continue

        # Adjust order value if limits constrained it
        if limit_check["max_allowed_value"] < order_value:
            adjusted_shares = int(limit_check["max_allowed_value"] / price) if price > 0 else 0
            sizing["shares"] = adjusted_shares
            sizing["position_value"] = adjusted_shares * price
            warnings.append(f"{stock_code}: position capped by limits")

        if sizing["shares"] > 0:
            candidate["position_sizing"] = sizing
            approved.append(stock_code)
            current_exposure += sizing["position_value"]
        else:
            rejected.append(stock_code)
            warnings.append(f"{stock_code}: calculated 0 shares")

    if classification == "crisis":
        warnings.append("CRISIS regime detected: all limits reduced by 50%")
    if daily_check["action"] == "WARNING":
        warnings.append(f"Daily loss warning: {daily_check['pnl_pct']:.1f}% of capital")
    if dd_check["recovery_mode"]:
        warnings.append(f"Drawdown recovery mode: positions scaled to {dd_check['position_scale']:.0%}")

    risk_assessment = {
        "max_position_size": limits.max_single_position_pct,
        "current_exposure": current_exposure,
        "risk_budget_remaining": max(0, limits.max_total_exposure - current_exposure),
        "warnings": warnings,
        "approved_trades": approved,
        "rejected_trades": rejected,
        "daily_loss_check": daily_check,
        "drawdown_mode": dd_check,
    }

    return {
        "messages": [AIMessage(
            content=f"[Risk Manager] Approved {len(approved)} trades, "
                    f"rejected {len(rejected)}. "
                    f"Exposure: {current_exposure:,.0f}/{limits.max_total_exposure:,.0f}. "
                    f"{'Warnings: ' + '; '.join(warnings) if warnings else 'No warnings.'}"
        )],
        "risk_assessment": risk_assessment,
        "current_agent": "risk_manager",
    }
