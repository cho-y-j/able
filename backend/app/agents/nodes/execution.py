"""Execution Agent: Handles order placement through KIS API.

Uses ExecutionEngine for smart routing (direct/TWAP/VWAP) and
tracks slippage for execution quality analysis.
Persists orders to DB with recipe_id for traceability.
"""

import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from langchain_core.messages import AIMessage
from app.agents.state import TradingState
from app.execution.engine import ExecutionEngine

logger = logging.getLogger(__name__)


async def execution_node(state: TradingState) -> dict:
    """LangGraph node: executes approved trades via KIS API.

    Uses the ExecutionEngine for smart order routing and slippage tracking.
    Requires _kis_client to be set in state by agent_tasks.py.
    """
    risk = state.get("risk_assessment", {})
    approved = risk.get("approved_trades", []) if risk else []
    candidates = state.get("strategy_candidates", [])
    kis_client = state.get("_kis_client")

    pending = state.get("pending_orders", [])
    executed = state.get("executed_orders", [])
    slippage_report = state.get("slippage_report", [])

    exec_config = state.get("execution_config", {}) or {}
    strategy_override = exec_config.get("strategy")  # None = auto

    if not approved:
        return {
            "messages": [AIMessage(
                content="[Execution] No approved trades. Skipping execution."
            )],
            "pending_orders": pending,
            "current_agent": "execution",
        }

    # If no KIS client, fall back to order queuing (dry-run mode)
    if not kis_client:
        logger.warning("No KIS client available, running in dry-run mode")
        return _dry_run_execution(state, approved, candidates, pending, executed)

    # Execute each approved trade via ExecutionEngine
    engine = ExecutionEngine(kis_client)
    new_orders = []
    new_slippage = []
    submitted_count = 0
    failed_count = 0

    for candidate in candidates:
        stock_code = candidate.get("stock_code", "")
        if stock_code not in approved:
            continue

        # Get quantity from position sizing (set by risk manager)
        sizing = candidate.get("position_sizing", {})
        quantity = sizing.get("shares", 1)
        if quantity <= 0:
            quantity = 1

        result = await engine.execute(
            stock_code=stock_code,
            side="buy",
            quantity=quantity,
            strategy_override=strategy_override if strategy_override != "auto" else None,
        )

        order_record = {
            "order_id": result.kis_order_id or f"DRY_{stock_code}",
            "stock_code": stock_code,
            "side": "buy",
            "order_type": "market" if result.execution_strategy == "direct" else "limit",
            "quantity": quantity,
            "execution_strategy": result.execution_strategy,
            "expected_price": result.expected_price,
            "fill_price": result.fill_price,
            "kis_order_id": result.kis_order_id,
            "status": "submitted" if result.success else "failed",
            "strategy_name": candidate.get("strategy_name", ""),
            "child_orders": result.child_orders,
            "error": result.error_message,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        new_orders.append(order_record)

        if result.success:
            submitted_count += 1
        else:
            failed_count += 1

        # Persist order to DB
        await _persist_order(state, stock_code, order_record, result)

        # Track slippage
        if result.slippage:
            slip = {
                "stock_code": stock_code,
                "expected_price": result.slippage.expected_price,
                "actual_price": result.slippage.actual_price,
                "slippage_bps": result.slippage.slippage_bps,
                "execution_strategy": result.execution_strategy,
            }
            new_slippage.append(slip)

    # Build summary message
    parts = [f"[Execution] Submitted {submitted_count} orders"]
    if failed_count:
        parts.append(f", {failed_count} failed")
    if new_slippage:
        avg_slip = sum(s["slippage_bps"] for s in new_slippage) / len(new_slippage)
        parts.append(f". Avg slippage: {avg_slip:.1f}bps")

    return {
        "messages": [AIMessage(content="".join(parts))],
        "pending_orders": pending + new_orders,
        "slippage_report": slippage_report + new_slippage,
        "current_agent": "execution",
    }


async def _persist_order(state: TradingState, stock_code: str, order_record: dict, result) -> None:
    """Save order to DB with recipe_id if available."""
    try:
        from app.db.session import async_session_factory
        from app.models.order import Order

        user_id = state.get("user_id")
        if not user_id:
            return

        # Find recipe_id from recipe_signals
        recipe_id = None
        recipe_signals = state.get("recipe_signals", {})
        for rid, data in recipe_signals.items():
            results = data.get("results", {})
            if stock_code in results and results[stock_code].get("entry"):
                recipe_id = rid
                break

        async with async_session_factory() as db:
            order = Order(
                user_id=uuid_mod.UUID(user_id),
                recipe_id=uuid_mod.UUID(recipe_id) if recipe_id else None,
                agent_session_id=uuid_mod.UUID(state["session_id"]) if state.get("session_id") else None,
                stock_code=stock_code,
                side=order_record.get("side", "buy"),
                order_type=order_record.get("order_type", "market"),
                quantity=order_record.get("quantity", 0),
                kis_order_id=result.kis_order_id,
                status="submitted" if result.success else "failed",
                execution_strategy=result.execution_strategy,
                expected_price=Decimal(str(result.expected_price)) if result.expected_price else None,
                avg_fill_price=Decimal(str(result.fill_price)) if result.fill_price else None,
                slippage_bps=result.slippage.slippage_bps if result.slippage else None,
                submitted_at=datetime.now(timezone.utc),
                error_message=result.error_message,
            )
            db.add(order)
            await db.commit()
            logger.info(f"Order persisted: {stock_code} recipe={recipe_id} status={order.status}")
    except Exception as e:
        logger.warning(f"Failed to persist order for {stock_code}: {e}")


def _dry_run_execution(state, approved, candidates, pending, executed):
    """Fallback execution without KIS client (for testing/dry-run)."""
    new_orders = []
    iteration = state.get("iteration_count", 0)

    for candidate in candidates:
        stock_code = candidate.get("stock_code", "")
        if stock_code not in approved:
            continue

        sizing = candidate.get("position_sizing", {})
        quantity = sizing.get("shares", 1)

        new_orders.append({
            "order_id": f"DRY_{stock_code}_{iteration}",
            "stock_code": stock_code,
            "side": "buy",
            "order_type": "market",
            "quantity": max(quantity, 1),
            "execution_strategy": "dry_run",
            "status": "dry_run",
            "strategy_name": candidate.get("strategy_name", ""),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "messages": [AIMessage(
            content=f"[Execution] DRY RUN: {len(new_orders)} orders queued (no KIS client)."
        )],
        "pending_orders": pending + new_orders,
        "current_agent": "execution",
    }
