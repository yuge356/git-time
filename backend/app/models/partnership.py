"""Learning partnerships and user-level privacy blocks."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PartnershipStatus(StrEnum):
    """Invitation states kept while a relationship is active."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class Partnership(TimestampMixin, Base):
    """One directional invitation for a canonical pair of users."""

    __tablename__ = "partnerships"
    __table_args__ = (
        CheckConstraint(
            "requester_id <> addressee_id",
            name="ck_partnerships_distinct_users",
        ),
        Index("ix_partnerships_requester_status", "requester_id", "status"),
        Index("ix_partnerships_addressee_status", "addressee_id", "status"),
        Index(
            "uq_partnerships_active_pair",
            "pair_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requester_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    addressee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    pair_key: Mapped[str] = mapped_column(String(73), nullable=False)
    status: Mapped[PartnershipStatus] = mapped_column(
        Enum(PartnershipStatus, name="partnership_status"),
        nullable=False,
        default=PartnershipStatus.PENDING,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserBlock(Base):
    """A unilateral block that disables discovery and collaboration both ways."""

    __tablename__ = "user_blocks"
    __table_args__ = (
        CheckConstraint("blocker_id <> blocked_id", name="ck_user_blocks_distinct_users"),
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
        Index("ix_user_blocks_blocked", "blocked_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    blocker_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    blocked_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
