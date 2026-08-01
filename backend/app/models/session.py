"""Independent, synchronizable study-session records."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SessionStatus(StrEnum):
    """Timer states required by start, pause, resume and finish actions."""

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class Session(TimestampMixin, Base):
    """One user's independently stored period of study."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("duration_seconds >= 0", name="ck_sessions_duration_seconds"),
        CheckConstraint(
            "task_id IS NOT NULL OR daily_plan_item_id IS NOT NULL",
            name="ck_sessions_has_subject",
        ),
        CheckConstraint(
            """
            (status = 'RUNNING' AND last_resumed_at IS NOT NULL AND ended_at IS NULL)
            OR (status = 'PAUSED' AND last_resumed_at IS NULL AND ended_at IS NULL)
            OR (status = 'COMPLETED' AND last_resumed_at IS NULL AND ended_at IS NOT NULL)
            """,
            name="ck_sessions_state_timestamps",
        ),
        Index("ix_sessions_owner_started", "owner_id", "started_at"),
        Index("ix_sessions_task_started", "task_id", "started_at"),
        Index("ix_sessions_daily_item_started", "daily_plan_item_id", "started_at"),
        Index("ix_sessions_owner_updated", "owner_id", "updated_at"),
        Index(
            "uq_sessions_one_active_owner",
            "owner_id",
            unique=True,
            postgresql_where=text(
                "status IN ('RUNNING', 'PAUSED') AND deleted_at IS NULL"
            ),
            sqlite_where=text("status IN ('RUNNING', 'PAUSED') AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    daily_plan_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("daily_plan_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_resumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    client_id: Mapped[UUID] = mapped_column(nullable=False)
    client_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
