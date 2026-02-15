import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Numeric, Interval
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class Trade(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trades"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_recipes.id"), nullable=True
    )
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    pnl_percent: Mapped[float | None] = mapped_column(Float)
    entry_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    exit_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
