"""Task API input, output and budget-status schemas."""

from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import (
    TaskBudgetMode,
    TaskNodeType,
    TaskRepeatRule,
    TaskStatus,
)


class BudgetLevel(StrEnum):
    """Budget warning bands defined in the project requirements."""

    NOT_SET = "NOT_SET"
    NORMAL = "NORMAL"
    NEAR_LIMIT = "NEAR_LIMIT"
    EXHAUSTED = "EXHAUSTED"
    SEVERE = "SEVERE"


class TaskCreate(BaseModel):
    """Fields accepted when creating a project, module or executable task."""

    id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None
    node_type: TaskNodeType = TaskNodeType.PROJECT
    estimated_seconds: int = Field(default=0, ge=0, le=315_360_000)
    budget_mode: TaskBudgetMode = TaskBudgetMode.ROLLUP
    fixed_budget_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_repeat_rule: TaskRepeatRule | None = None
    default_daily_reminder_time: time | None = None
    repeat_rule: TaskRepeatRule = TaskRepeatRule.NONE
    repeat_end_date: date | None = None
    daily_reminder_time: time | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Task title cannot be blank")
        return normalized


class TaskUpdate(BaseModel):
    """Editable task fields; omitted values remain unchanged."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    budget_mode: TaskBudgetMode | None = None
    fixed_budget_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    default_repeat_rule: TaskRepeatRule | None = None
    default_daily_reminder_time: time | None = None
    status: TaskStatus | None = None
    repeat_rule: TaskRepeatRule | None = None
    repeat_end_date: date | None = None
    daily_reminder_time: time | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Task title cannot be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Task title cannot be blank")
        return normalized

    @field_validator("estimated_seconds", "status", "repeat_rule", "budget_mode")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class TaskResponse(BaseModel):
    """Task data plus calculated time-budget information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    parent_id: UUID | None
    node_type: TaskNodeType
    title: str
    status: TaskStatus
    estimated_seconds: int
    budget_mode: TaskBudgetMode
    fixed_budget_seconds: int | None
    default_estimated_seconds: int | None
    default_repeat_rule: TaskRepeatRule | None
    default_daily_reminder_time: time | None
    repeat_rule: TaskRepeatRule
    repeat_end_date: date | None
    daily_reminder_time: time | None
    sort_order: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    direct_actual_seconds: int
    actual_seconds: int
    planned_seconds: int
    children_estimated_seconds: int
    is_leaf: bool
    task_count: int
    completed_task_count: int
    progress_ratio: float | None
    budget_usage_ratio: float | None
    budget_level: BudgetLevel


class TaskBulkApplyRequest(BaseModel):
    """Choose which container defaults to apply to descendant tasks."""

    overwrite: bool = False
    apply_estimated_seconds: bool = True
    apply_repeat_rule: bool = True
    apply_daily_reminder_time: bool = True


class TaskBulkApplyResponse(BaseModel):
    """Impact summary plus the refreshed flat task list."""

    affected_count: int
    skipped_count: int
    tasks: list[TaskResponse]
