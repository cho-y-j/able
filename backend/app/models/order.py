import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class Order(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trading_recipes.id"), nullable=True
    )
    agent_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # 'buy' or 'sell'
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'market', 'limit'
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    kis_order_id: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    execution_strategy: Mapped[str | None] = mapped_column(String(10))  # direct, twap, vwap
    parent_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id")
    )
    expected_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    slippage_bps: Mapped[float | None] = mapped_column()
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
