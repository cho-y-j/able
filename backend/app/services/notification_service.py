"""Centralized notification service.

Dispatches notifications to multiple channels:
- In-app (DB-stored notifications)
- WebSocket (real-time push to connected clients)
- Email (async via SMTP for important events)
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationCategory(str, Enum):
    TRADE = "trade"
    AGENT = "agent"
    ORDER = "order"
    POSITION = "position"
    SYSTEM = "system"
    ALERT = "alert"


@dataclass
class NotificationPayload:
    user_id: str
    category: NotificationCategory
    title: str
    message: str
    data: dict | None = None
    link: str | None = None
    send_email: bool = False


class NotificationService:
    """Sends notifications through configured channels."""

    @staticmethod
    async def send(payload: NotificationPayload, db=None) -> dict:
        """Dispatch notification to all enabled channels.

        Returns dict with channel results.
        """
        results = {}

        # 1. In-app (persist to DB)
        if db:
            try:
                notif_id = await NotificationService._save_to_db(payload, db)
                results["in_app"] = {"status": "ok", "id": str(notif_id)}
            except Exception as e:
                logger.error(f"Failed to save notification: {e}")
                results["in_app"] = {"status": "error", "error": str(e)}

        # 2. WebSocket (real-time push)
        try:
            await NotificationService._send_websocket(payload)
            results["websocket"] = {"status": "ok"}
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
            results["websocket"] = {"status": "error", "error": str(e)}

        # 3. Email (if requested)
        if payload.send_email:
            try:
                NotificationService._send_email(payload)
                results["email"] = {"status": "ok"}
            except Exception as e:
                logger.error(f"Email notification failed: {e}")
                results["email"] = {"status": "error", "error": str(e)}

        return results

    @staticmethod
    async def _save_to_db(payload: NotificationPayload, db) -> str:
        """Save notification to database."""
        import uuid
        from app.models.notification import Notification

        notif = Notification(
            user_id=uuid.UUID(payload.user_id),
            category=payload.category.value,
            title=payload.title,
            message=payload.message,
            data=payload.data,
            link=payload.link,
        )
        db.add(notif)
        await db.flush()
        return str(notif.id)

    @staticmethod
    async def _send_websocket(payload: NotificationPayload) -> None:
        """Push notification via WebSocket."""
        from app.api.v1.websocket import manager

        await manager.send_to_user(payload.user_id, {
            "type": "notification",
            "category": payload.category.value,
            "title": payload.title,
            "message": payload.message,
            "data": payload.data,
            "link": payload.link,
        })

    @staticmethod
    def _send_email(payload: NotificationPayload) -> None:
        """Send email notification using the email service.

        Looks up user email from DB or payload data, then delegates to email_service.
        """
        from app.services.email_service import send_email

        # Determine recipient email
        to_email = None
        if payload.data and payload.data.get("email"):
            to_email = payload.data["email"]

        if not to_email:
            # Try to look up from user table (sync fallback)
            try:
                from app.db.session import sync_engine
                from sqlalchemy import text
                with sync_engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT email FROM users WHERE id = :uid"),
                        {"uid": payload.user_id},
                    )
                    row = result.fetchone()
                    if row:
                        to_email = row[0]
            except Exception as e:
                logger.warning(f"Could not look up user email: {e}")

        if not to_email:
            logger.debug("No email address for user %s, skipping email", payload.user_id)
            return

        # Build email from template based on category
        subject = f"[ABLE] {payload.title}"
        from app.services.email_service import (
            template_order_filled, template_agent_error,
            template_pending_approval, template_pnl_alert,
            _render_template,
        )

        data = payload.data or {}
        if payload.category == NotificationCategory.ORDER and "price" in data:
            subject, html = template_order_filled(
                data.get("stock_code", ""), data.get("side", ""),
                data.get("quantity", 0), data.get("price", 0),
            )
        elif payload.category == NotificationCategory.AGENT and "error" in data:
            subject, html = template_agent_error(
                data.get("session_id", ""), data.get("error", ""),
            )
        elif payload.category == NotificationCategory.TRADE and "trade_count" in data:
            subject, html = template_pending_approval(
                data.get("session_id", ""), data.get("trade_count", 0),
                data.get("total_value", 0),
            )
        elif payload.category == NotificationCategory.ALERT and "pnl" in data:
            subject, html = template_pnl_alert(
                data.get("stock_code", ""), data.get("pnl", 0),
                data.get("pnl_pct", 0),
            )
        else:
            # Generic template
            content = f"""
            <h2 style="color:#f1f5f9; font-size:18px; margin:0 0 12px;">{payload.title}</h2>
            <p style="color:#94a3b8; font-size:14px; line-height:1.6;">{payload.message}</p>
            """
            html = _render_template(content)

        send_email(to_email, subject, html)


# ── Convenience functions for common notifications ──


async def notify_order_filled(user_id: str, stock_code: str, side: str, quantity: int, price: float, db=None):
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.ORDER,
        title=f"Order Filled: {side.upper()} {stock_code}",
        message=f"{side.upper()} {quantity:,} shares of {stock_code} at ₩{price:,.0f}",
        data={"stock_code": stock_code, "side": side, "quantity": quantity, "price": price},
        link="/dashboard/trading",
    ), db)


async def notify_order_rejected(user_id: str, stock_code: str, side: str, reason: str, db=None):
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.ORDER,
        title=f"Order Rejected: {side.upper()} {stock_code}",
        message=f"Your {side} order for {stock_code} was rejected: {reason}",
        data={"stock_code": stock_code, "side": side, "reason": reason},
        link="/dashboard/trading",
    ), db)


async def notify_agent_started(user_id: str, session_id: str, session_type: str, db=None):
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.AGENT,
        title="AI Agent Started",
        message=f"Agent session ({session_type}) has started analyzing the market.",
        data={"session_id": session_id, "session_type": session_type},
        link="/dashboard/agents",
    ), db)


async def notify_agent_completed(user_id: str, session_id: str, iterations: int, db=None):
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.AGENT,
        title="AI Agent Completed",
        message=f"Agent session completed after {iterations} iteration(s).",
        data={"session_id": session_id, "iterations": iterations},
        link="/dashboard/agents",
    ), db)


async def notify_agent_error(user_id: str, session_id: str, error: str, db=None):
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.AGENT,
        title="AI Agent Error",
        message=f"Agent session encountered an error: {error}",
        data={"session_id": session_id, "error": error},
        link="/dashboard/agents",
        send_email=True,
    ), db)


async def notify_pending_approval(user_id: str, session_id: str, trade_count: int, total_value: float, db=None):
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.TRADE,
        title="Trades Pending Approval",
        message=f"{trade_count} trade(s) worth ₩{total_value:,.0f} need your approval.",
        data={"session_id": session_id, "trade_count": trade_count, "total_value": total_value},
        link="/dashboard/agents",
        send_email=True,
    ), db)


async def notify_pnl_alert(user_id: str, stock_code: str, pnl: float, pnl_pct: float, db=None):
    direction = "gain" if pnl >= 0 else "loss"
    await NotificationService.send(NotificationPayload(
        user_id=user_id,
        category=NotificationCategory.ALERT,
        title=f"P&L Alert: {stock_code} {pnl_pct:+.1f}%",
        message=f"{stock_code} has an unrealized {direction} of ₩{abs(pnl):,.0f} ({pnl_pct:+.1f}%)",
        data={"stock_code": stock_code, "pnl": pnl, "pnl_pct": pnl_pct},
        link="/dashboard/trading",
    ), db)
