import uuid
from datetime import date, datetime
from sqlalchemy import String, Float, Integer, Date, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Backtest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backtests"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    date_range_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_range_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Core metrics
    total_return: Mapped[float | None] = mapped_column(Float)
    annual_return: Mapped[float | None] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    sortino_ratio: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    total_trades: Mapped[int | None] = mapped_column(Integer)
    calmar_ratio: Mapped[float | None] = mapped_column(Float)

    # Validation scores
    wfa_score: Mapped[float | None] = mapped_column(Float)
    oos_score: Mapped[float | None] = mapped_column(Float)
    mc_score: Mapped[float | None] = mapped_column(Float)

    # Raw data
    equity_curve: Mapped[dict | None] = mapped_column(JSONB)
    trade_log: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    strategy = relationship("Strategy", back_populates="backtests")
