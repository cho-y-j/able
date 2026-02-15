import uuid
from sqlalchemy import String, Float, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Strategy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "strategies"
    __table_args__ = (
        UniqueConstraint("user_id", "strategy_type", "stock_code", name="uq_strategy_user_type_stock"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_name: Mapped[str | None] = mapped_column(String(100))
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="indicator_based")
    indicators: Mapped[dict] = mapped_column(JSONB, default=list)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    entry_rules: Mapped[dict] = mapped_column(JSONB, default=dict)
    exit_rules: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    composite_score: Mapped[float | None] = mapped_column(Float)
    validation_results: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    is_auto_trading: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="strategies")
    backtests = relationship("Backtest", back_populates="strategy", cascade="all, delete-orphan")
