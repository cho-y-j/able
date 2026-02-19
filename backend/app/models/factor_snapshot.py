import uuid
from datetime import date
from sqlalchemy import String, Float, Date, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class FactorSnapshot(Base, UUIDMixin, TimestampMixin):
    """Stores point-in-time factor values for stocks and global indicators."""

    __tablename__ = "factor_snapshots"

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_code: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "_GLOBAL" for macro factors
    timeframe: Mapped[str] = mapped_column(
        String(10), nullable=False, default="daily"
    )
    factor_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=dict
    )  # category, source, params

    __table_args__ = (
        UniqueConstraint(
            "snapshot_date", "stock_code", "timeframe", "factor_name",
            name="uq_factor_snapshot",
        ),
        Index("ix_factor_date_stock", "snapshot_date", "stock_code"),
        Index("ix_factor_name_date", "factor_name", "snapshot_date"),
        Index(
            "ix_factor_date_name_stock",
            "snapshot_date", "factor_name", "stock_code",
        ),
    )
