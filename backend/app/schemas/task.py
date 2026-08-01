"""Task API input, output and budget-status schemas."""

from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import TaskRepeatRule, TaskStatus


class BudgetLevel(StrEnum):
    """Budget warning bands defined in the project requirements."""

    NOT_SET = "NOT_SET"
    NORMAL = "NORMAL"
    NEAR_LIMIT = "NEAR_LIMIT"
    EXHAUSTED = "EXHAUSTED"
    SEVERE = "SEVERE"


class TaskCreate(BaseModel):
    """Fields accepted when creating a root task or child task."""

    id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None
    estimated_seconds: int = Field(default=0, ge=0, le=315_360_000)
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

    @field_validator("estimated_seconds", "status", "repeat_rule")
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
    title: str
    status: TaskStatus
    estimated_seconds: int
    repeat_rule: TaskRepeatRule
    repeat_end_date: date | None
    daily_reminder_time: time | None
    sort_order: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    direct_actual_seconds: int
    actual_seconds: int
    children_estimated_seconds: int
    is_leaf: bool
    budget_usage_ratio: float | None
    budget_level: BudgetLevel
