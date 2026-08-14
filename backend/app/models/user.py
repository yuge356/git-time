"""Private authentication account model."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Authentication data that is never exposed through public profile search."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_phone", "phone", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True, nullable=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    profile: Mapped[Profile] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="raise",
    )


from app.models.profile import Profile  # noqa: E402
