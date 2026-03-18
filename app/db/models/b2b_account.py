import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class B2BAccount(Base):
    __tablename__ = "b2b_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    private_key: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted AES-256-GCM
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_assigned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_b2b_accounts_is_assigned", "is_assigned"),
    )
