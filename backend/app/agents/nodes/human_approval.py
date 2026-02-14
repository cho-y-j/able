"""Human-in-the-Loop approval node for large or risky trades."""

import logging
from langchain_core.messages import AIMessage
from app.agents.state import TradingState

logger = logging.getLogger(__name__)

# Thresholds for requiring human approval
DEFAULT_APPROVAL_THRESHOLD = 5_000_000  # 500만원 이상 주문 시 승인 필요
CRISIS_APPROVAL_THRESHOLD = 2_000_000   # 위기 시 200만원 이상


async def human_approval_node(state: TradingState) -> dict:
    """LangGraph node: pauses execution to request human approval for large trades.

    Checks if any approved trade exceeds the approval threshold.
    If so, marks the state as pending_approval and halts execution
    until the user approves or rejects via the API.
    """
    risk = state.get("risk_assessment", {})
    approved_trades = risk.get("approved_trades", [])
    candidates = state.get("strategy_candidates", [])
    regime = state.get("market_regime", {})
    classification = regime.get("classification", "sideways") if regime else "sideways"

    # Skip if HITL is disabled
    if not state.get("hitl_enabled", False):
        return {"current_agent": "human_approval"}

    # Already approved or rejected by user
    approval_status = state.get("approval_status")
    if approval_status == "approved":
        return {
            "messages": [AIMessage(
                content="[HITL] User approved the pending trades. Proceeding to execution."
            )],
            "pending_approval": False,
            "current_agent": "human_approval",
        }
    elif approval_status == "rejected":
        # Clear approved trades - nothing to execute
        if risk:
            risk["approved_trades"] = []
            risk["rejected_trades"] = approved_trades + risk.get("rejected_trades", [])
            risk["warnings"] = risk.get("warnings", []) + ["User rejected proposed trades"]
        return {
            "messages": [AIMessage(
                content="[HITL] User rejected the proposed trades. Skipping execution."
            )],
            "risk_assessment": risk,
            "pending_approval": False,
            "current_agent": "human_approval",
        }

    # Determine threshold based on regime
    threshold = state.get("approval_threshold", DEFAULT_APPROVAL_THRESHOLD)
    if classification == "crisis":
        threshold = min(threshold, CRISIS_APPROVAL_THRESHOLD)

    # Check if any trade exceeds threshold
    trades_needing_approval = []
    for code in approved_trades:
        candidate = next(
            (c for c in candidates if c.get("stock_code") == code),
            None,
        )
        if not candidate:
            continue
        sizing = candidate.get("position_sizing", {})
        value = sizing.get("position_value", 0)
        if value >= threshold:
            trades_needing_approval.append({
                "stock_code": code,
                "position_value": value,
                "shares": sizing.get("shares", 0),
                "kelly_adjusted": sizing.get("kelly_adjusted", 0),
            })

    if not trades_needing_approval:
        return {"current_agent": "human_approval"}

    # Request human approval
    trade_summary = "; ".join(
        f"{t['stock_code']}: {t['position_value']:,.0f}원 ({t['shares']}주)"
        for t in trades_needing_approval
    )

    return {
        "messages": [AIMessage(
            content=f"[HITL] Approval required for {len(trades_needing_approval)} trade(s): "
                    f"{trade_summary}. Threshold: {threshold:,.0f}원. "
                    f"Waiting for user approval via API."
        )],
        "pending_approval": True,
        "pending_trades": trades_needing_approval,
        "current_agent": "human_approval",
    }
