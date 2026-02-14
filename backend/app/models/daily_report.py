"""Daily Market Intelligence Report model."""

import uuid
from datetime import date

from sqlalchemy import Date, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class DailyMarketReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "daily_market_reports"

    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    # Raw market data (all numbers pre-computed)
    market_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Theme analysis with leader/follower stocks
    themes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # AI-generated summary and recommendations
    ai_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Full raw text from AI
    ai_raw_text: Mapped[str | None] = mapped_column(Text)
