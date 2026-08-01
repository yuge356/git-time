"""Partner plan sharing, fixed encouragements and persisted notifications."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EncouragementType(StrEnum):
    """Closed encouragement list; free-form messages are intentionally excluded."""

    KEEP_GOING = "KEEP_GOING"
    GREAT_JOB = "GREAT_JOB"
    WELL_DONE = "WELL_DONE"
    YOU_CAN_DO_IT = "YOU_CAN_DO_IT"


class NotificationType(StrEnum):
    """Events surfaced in the notification center."""

    PARTNER_INVITE = "PARTNER_INVITE"
    PARTNER_ACCEPTED = "PARTNER_ACCEPTED"
    PLAN_SHARED = "PLAN_SHARED"
    ENCOURAGEMENT = "ENCOURAGEMENT"
    TASK_COMPLETED = "TASK_COMPLETED"


class DailyPlanShare(TimestampMixin, Base):
    """A daily plan shared by its owner with one accepted partner."""

    __tablename__ = "daily_plan_shares"
    __table_args__ = (
        CheckConstraint("owner_id <> partner_id", name="ck_daily_plan_shares_distinct_users"),
        Index("ix_daily_plan_shares_owner", "owner_id", "created_at"),
        Index("ix_daily_plan_shares_partner", "partner_id", "created_at"),
        Index(
            "uq_daily_plan_shares_active_recipient",
            "daily_plan_id",
            "partner_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    daily_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    partner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    share_duration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Encouragement(Base):
    """One fixed-form reaction sent through an active plan share."""

    __tablename__ = "encouragements"
    __table_args__ = (
        CheckConstraint("sender_id <> receiver_id", name="ck_encouragements_distinct_users"),
        Index("ix_encouragements_share_created", "share_id", "created_at"),
        Index("ix_encouragements_receiver_created", "receiver_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    share_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_plan_shares.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    receiver_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    encouragement_type: Mapped[EncouragementType] = mapped_column(
        Enum(EncouragementType, name="encouragement_type"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Notification(TimestampMixin, Base):
    """A durable notification delivered to one user."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
            sqlite_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
    )
    payload: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
