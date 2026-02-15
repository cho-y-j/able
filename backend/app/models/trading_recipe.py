import uuid
from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class TradingRecipe(Base, UUIDMixin, TimestampMixin):
    """User-created trading recipe combining multiple signal generators."""

    __tablename__ = "trading_recipes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Signal combination config: { "combinator": "AND"|"OR"|"MIN_AGREE"|"WEIGHTED", "min_agree": 2, "signals": [...] }
    signal_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Custom filters: { "volume_min": 1000000, "price_range": [50000, 100000], ... }
    custom_filters: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Target stock codes
    stock_codes: Mapped[list] = mapped_column(JSONB, default=list)

    # Risk parameters: { "stop_loss": 3, "take_profit": 5, "position_size": 0.1 }
    risk_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="recipes")
