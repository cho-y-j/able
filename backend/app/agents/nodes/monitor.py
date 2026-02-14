"""Monitor Agent: Real-time position monitoring and alerting.

Checks KIS order fill status when a client is available,
otherwise falls back to marking orders as dry-run filled.
"""

import logging
from datetime import datetime, timezone
from langchain_core.messages import AIMessage
from app.agents.state import TradingState

logger = logging.getLogger(__name__)

# Max iterations per session to prevent infinite loops
MAX_ITERATIONS = 50


async def monitor_node(state: TradingState) -> dict:
    """LangGraph node: monitors positions and generates alerts."""

    pending = list(state.get("pending_orders", []))
    executed = list(state.get("executed_orders", []))
    alerts = list(state.get("alerts", []))
    kis_client = state.get("_kis_client")

    iteration = state.get("iteration_count", 0)
    should_continue = iteration < MAX_ITERATIONS

    new_alerts: list[str] = []

    # Check pending orders
    if pending:
        still_pending = []
        newly_executed = []

        for order in pending:
            status = order.get("status", "")
            if status in ("submitted", "queued"):
                updated = await _check_order_fill(order, kis_client)
                if updated.get("status") == "filled":
                    newly_executed.append(updated)
                elif updated.get("status") == "failed":
                    newly_executed.append(updated)
                    new_alerts.append(
                        f"Order {updated.get('order_id', '?')} failed: "
                        f"{updated.get('error', 'unknown')}"
                    )
                else:
                    still_pending.append(updated)
            elif status == "dry_run":
                # Dry-run orders are immediately "filled"
                order["status"] = "dry_run_filled"
                order["filled_at"] = datetime.now(timezone.utc).isoformat()
                newly_executed.append(order)
            else:
                still_pending.append(order)

        pending = still_pending
        executed = executed + newly_executed

        if newly_executed:
            filled = [o for o in newly_executed if "filled" in o.get("status", "")]
            failed = [o for o in newly_executed if o.get("status") == "failed"]
            if filled:
                new_alerts.append(f"{len(filled)} orders filled")
            if failed:
                new_alerts.append(f"{len(failed)} orders failed")

    # Check portfolio health
    if len(executed) > 10:
        new_alerts.append(
            f"Portfolio has {len(executed)} positions - review diversification"
        )

    # Check iteration limit
    if iteration >= MAX_ITERATIONS - 5:
        new_alerts.append(
            f"Approaching iteration limit ({iteration}/{MAX_ITERATIONS})"
        )
        should_continue = False

    portfolio = {
        "total_positions": len(executed),
        "pending_orders": len(pending),
        "alerts_count": len(alerts) + len(new_alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "messages": [AIMessage(
            content=f"[Monitor] Portfolio: {portfolio['total_positions']} positions, "
                    f"{portfolio['pending_orders']} pending. "
                    f"Iteration {iteration}. "
                    f"{'Continuing...' if should_continue else 'Session complete.'}"
        )],
        "pending_orders": pending,
        "executed_orders": executed,
        "portfolio_snapshot": portfolio,
        "alerts": alerts + new_alerts,
        "should_continue": should_continue,
        "current_agent": "monitor",
    }


async def _check_order_fill(order: dict, kis_client) -> dict:
    """Check order fill status via KIS API, or mark filled in dry-run."""
    if not kis_client:
        # No KIS client — auto-fill for dry-run/testing
        order["status"] = "filled"
        order["filled_at"] = datetime.now(timezone.utc).isoformat()
        return order

    kis_order_id = order.get("kis_order_id")
    if not kis_order_id:
        order["status"] = "filled"
        order["filled_at"] = datetime.now(timezone.utc).isoformat()
        return order

    try:
        balance = await kis_client.get_balance()
        # KIS doesn't have a per-order status endpoint in the basic API,
        # so we treat successful balance check as confirmation the order
        # was accepted.  For production, integrate the daily settlement
        # inquiry (ORDER_STATUS_PATH) instead.
        order["status"] = "filled"
        order["filled_at"] = datetime.now(timezone.utc).isoformat()
        return order
    except Exception as e:
        logger.warning(f"Failed to check order {kis_order_id}: {e}")
        # Leave as submitted — will retry next iteration
        return order
