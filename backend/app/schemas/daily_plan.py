"""Daily-plan input, item and check-in response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.daily_plan import DailyPlanItemStatus


class DailyPlanCreate(BaseModel):
    """Create the single daily plan for a local calendar date."""

    id: UUID | None = None
    plan_date: date


class DailyPlanItemCreate(BaseModel):
    """Add a linked long-term task or a standalone daily item."""

    id: UUID | None = None
    task_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def require_ad_hoc_title(self) -> "DailyPlanItemCreate":
        if self.task_id is None and self.title is None:
            raise ValueError("Standalone daily items require a title")
        return self


class DailyPlanItemUpdate(BaseModel):
    """Edit the daily snapshot without changing its long-term task link."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    estimated_seconds: int | None = Field(default=None, ge=0, le=315_360_000)
    status: DailyPlanItemStatus | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Title cannot be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank")
        return normalized

    @field_validator("estimated_seconds", "status", "sort_order")
    @classmethod
    def reject_null_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class DailyPlanItemResponse(BaseModel):
    """Stored daily item plus calculated study duration."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    daily_plan_id: UUID
    owner_id: UUID
    task_id: UUID | None
    title: str
    status: DailyPlanItemStatus
    estimated_seconds: int
    actual_seconds: int
    sort_order: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DailyPlanResponse(BaseModel):
    """One daily plan and its progress summary."""

    id: UUID
    owner_id: UUID
    plan_date: date
    items: list[DailyPlanItemResponse]
    total_items: int
    completed_items: int
    completion_rate: float
    actual_seconds: int
    created_at: datetime
    updated_at: datetime


class CheckInResponse(BaseModel):
    """Daily check-in figures displayed on the Today page."""

    plan_date: date
    learning_seconds: int
    completed_items: int
    total_items: int
    streak_days: int
