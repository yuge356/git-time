"""Public-facing user profile model."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Profile(TimestampMixin, Base):
    """User-editable identity and preference fields."""

    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Shanghai",
    )
    is_searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship(back_populates="profile", lazy="raise")


from app.models.user import User  # noqa: E402

