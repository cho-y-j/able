import uuid
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class AIAnalysisResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_analysis_results"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_name: Mapped[str | None] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # 매수/매도/관망
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    news_sentiment: Mapped[str | None] = mapped_column(String(10))  # 긍정/중립/부정
    reasoning: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    full_result: Mapped[dict] = mapped_column(JSONB, nullable=False)

    user = relationship("User")
