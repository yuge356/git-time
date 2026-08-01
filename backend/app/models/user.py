"""Private authentication account model."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Authentication data that is never exposed through public profile search."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    profile: Mapped[Profile] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="raise",
    )


from app.models.profile import Profile  # noqa: E402

