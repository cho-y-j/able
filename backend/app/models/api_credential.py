import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, LargeBinary, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class ApiCredential(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "api_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'kis' or 'llm'
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)  # 'kis', 'openai', 'anthropic', 'google'
    label: Mapped[str | None] = mapped_column(String(100))
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_secret: Mapped[bytes | None] = mapped_column(LargeBinary)
    account_number: Mapped[str | None] = mapped_column(String(100))  # encrypted
    model_name: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_paper_trading: Mapped[bool] = mapped_column(Boolean, default=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="api_credentials")
