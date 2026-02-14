"""Notification model for persistent in-app notifications."""

from sqlalchemy import String, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped["UUID"] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Categories: trade, agent, order, position, system, alert
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Optional link for frontend navigation
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)


class NotificationPreference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notification_preferences"

    user_id: Mapped["UUID"] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Channel toggles
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Category toggles
    trade_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    agent_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    order_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    position_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    system_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    # Email address (fallback to user.email)
    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
