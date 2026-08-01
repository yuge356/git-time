"""Hierarchical learning task and time-budget model."""

from datetime import datetime, time
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TaskStatus(StrEnum):
    """Allowed lifecycle states from the product requirements."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    DONE = "DONE"


class TaskRepeatRule(StrEnum):
    """Supported task recurrence patterns."""

    NONE = "NONE"
    DAILY = "DAILY"
    WEEKDAYS = "WEEKDAYS"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class Task(TimestampMixin, Base):
    """A node in an owner's learning-task tree."""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_tasks_id_owner"),
        ForeignKeyConstraint(
            ["parent_id", "owner_id"],
            ["tasks.id", "tasks.owner_id"],
            name="fk_tasks_parent_same_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("estimated_seconds >= 0", name="ck_tasks_estimated_seconds"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_tasks_not_own_parent"),
        Index("ix_tasks_owner_parent_sort", "owner_id", "parent_id", "sort_order"),
        Index("ix_tasks_owner_status", "owner_id", "status"),
        Index("ix_tasks_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.TODO,
    )
    estimated_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repeat_rule: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TaskRepeatRule.NONE,
    )
    daily_reminder_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
