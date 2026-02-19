import uuid
from sqlalchemy import String, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class DiscoveredPattern(Base, UUIDMixin, TimestampMixin):
    """ML-discovered multi-factor pattern for predicting stock movements."""

    __tablename__ = "discovered_patterns"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Pattern type: "rise_5pct_5day", "volume_breakout", etc.
    pattern_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # ML feature importance: {"rsi_14": 0.25, "macd_histogram": 0.18, ...}
    feature_importance: Mapped[dict] = mapped_column(JSONB, default=dict)

    # ML model metrics: {"accuracy": 0.72, "precision": 0.65, "recall": 0.70, "f1": 0.67}
    model_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)

    # AI-generated natural language description
    rule_description: Mapped[str | None] = mapped_column(Text)

    # Machine-readable screening rule for live use
    rule_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Walk-forward validation results
    validation_results: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status: draft → validated → active → deprecated
    status: Mapped[str] = mapped_column(String(20), default="draft")

    # Training data stats
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
