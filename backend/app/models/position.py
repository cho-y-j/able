import uuid
from decimal import Decimal
from sqlalchemy import String, Integer, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class Position(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("user_id", "stock_code", "strategy_id", name="uq_position"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cost_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
