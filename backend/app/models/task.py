"""Hierarchical learning task and time-budget model."""

from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
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
    BLOCKED = "BLOCKED"
    DONE = "DONE"


class TaskRepeatRule(StrEnum):
    """Supported task recurrence patterns."""

    NONE = "NONE"
    DAILY = "DAILY"
    WEEKDAYS = "WEEKDAYS"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class TaskNodeType(StrEnum):
    """Stable business role for each node in the three-level task tree."""

    PROJECT = "PROJECT"
    MODULE = "MODULE"
    TASK = "TASK"


class TaskBudgetMode(StrEnum):
    """How a project or module obtains its display budget."""

    ROLLUP = "ROLLUP"
    FIXED_CAP = "FIXED_CAP"


class TaskPriority(StrEnum):
    """Small, stable priority scale shared by every task view."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


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
        CheckConstraint(
            "fixed_budget_seconds IS NULL OR fixed_budget_seconds >= 0",
            name="ck_tasks_fixed_budget_seconds",
        ),
        CheckConstraint(
            "default_estimated_seconds IS NULL OR default_estimated_seconds >= 0",
            name="ck_tasks_default_estimated_seconds",
        ),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_tasks_not_own_parent"),
        Index("ix_tasks_owner_parent_sort", "owner_id", "parent_id", "sort_order"),
        Index("ix_tasks_owner_node_type", "owner_id", "node_type"),
        Index("ix_tasks_owner_status", "owner_id", "status"),
        Index("ix_tasks_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    node_type: Mapped[TaskNodeType] = mapped_column(
        Enum(TaskNodeType, name="task_node_type", native_enum=False),
        nullable=False,
        default=TaskNodeType.PROJECT,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority", native_enum=False),
        nullable=False,
        default=TaskPriority.MEDIUM,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Executable-task planning window shown and dragged on the Today page
    # Gantt chart. Always null for project/module containers.
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.TODO,
    )
    estimated_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    budget_mode: Mapped[TaskBudgetMode] = mapped_column(
        Enum(TaskBudgetMode, name="task_budget_mode", native_enum=False),
        nullable=False,
        default=TaskBudgetMode.ROLLUP,
    )
    fixed_budget_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_estimated_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_repeat_rule: Mapped[str | None] = mapped_column(String(16), nullable=True)
    default_daily_reminder_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    repeat_rule: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TaskRepeatRule.NONE,
    )
    repeat_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_reminder_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskDependency(Base):
    """A directed prerequisite edge kept separate from the task hierarchy."""

    __tablename__ = "task_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "owner_id"],
            ["tasks.id", "tasks.owner_id"],
            name="fk_task_dependencies_task_same_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["depends_on_task_id", "owner_id"],
            ["tasks.id", "tasks.owner_id"],
            name="fk_task_dependencies_prerequisite_same_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "task_id <> depends_on_task_id",
            name="ck_task_dependencies_not_self",
        ),
        Index("ix_task_dependencies_owner_task", "owner_id", "task_id"),
        Index(
            "ix_task_dependencies_owner_prerequisite",
            "owner_id",
            "depends_on_task_id",
        ),
    )

    task_id: Mapped[UUID] = mapped_column(primary_key=True)
    depends_on_task_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
