"""Reusable project blueprints applied when creating a new project."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.task import TaskBudgetMode


class ProjectTemplate(TimestampMixin, Base):
    """An owner's saved project skeleton.

    ``structure`` holds the module/task outline as nested JSON rather than
    real task rows: a template is a blueprint, so it must not appear on the
    projects page, in analytics or in a daily plan until it is applied.
    """

    __tablename__ = "project_templates"
    __table_args__ = (
        CheckConstraint(
            "fixed_budget_seconds IS NULL OR fixed_budget_seconds >= 0",
            name="ck_project_templates_fixed_budget_seconds",
        ),
        CheckConstraint(
            "default_estimated_seconds IS NULL OR default_estimated_seconds >= 0",
            name="ck_project_templates_default_estimated_seconds",
        ),
        Index("ix_project_templates_owner_sort", "owner_id", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Non-null when the template started as a copy of a built-in preset, so
    # the UI can keep showing that preset in place of its edited copy.
    preset_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    budget_mode: Mapped[TaskBudgetMode] = mapped_column(
        Enum(TaskBudgetMode, name="task_budget_mode", native_enum=False),
        nullable=False,
        default=TaskBudgetMode.ROLLUP,
    )
    fixed_budget_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_estimated_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_repeat_rule: Mapped[str | None] = mapped_column(String(16), nullable=True)
    structure: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
