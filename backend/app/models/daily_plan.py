"""Daily learning plans and their ordered task snapshots."""

from datetime import date, datetime
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DailyPlanItemStatus(StrEnum):
    """Lifecycle states shared by long-term tasks and daily plan items."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    DONE = "DONE"


class DailyPlan(TimestampMixin, Base):
    """One plan for one owner and one local calendar day."""

    __tablename__ = "daily_plans"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_daily_plans_id_owner"),
        UniqueConstraint("owner_id", "plan_date", name="uq_daily_plans_owner_date"),
        Index("ix_daily_plans_owner_date", "owner_id", "plan_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyPlanItem(TimestampMixin, Base):
    """A linked task snapshot or an ad-hoc item inside a daily plan."""

    __tablename__ = "daily_plan_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["daily_plan_id", "owner_id"],
            ["daily_plans.id", "daily_plans.owner_id"],
            name="fk_daily_plan_items_plan_same_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "estimated_seconds >= 0",
            name="ck_daily_plan_items_estimated_seconds",
        ),
        Index(
            "ix_daily_plan_items_plan_sort",
            "daily_plan_id",
            "sort_order",
        ),
        Index("ix_daily_plan_items_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    daily_plan_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[DailyPlanItemStatus] = mapped_column(
        Enum(DailyPlanItemStatus, name="daily_plan_item_status"),
        nullable=False,
        default=DailyPlanItemStatus.TODO,
    )
    estimated_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
