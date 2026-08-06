"""Read-only learning analytics response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class TaskTimeSlice(BaseModel):
    """One task's share of direct learning time."""

    task_id: UUID | None
    title: str
    seconds: int
    percentage: float


class DailyTrendPoint(BaseModel):
    """Learning and completion totals for one calendar date."""

    date: date
    seconds: int
    completed_items: int


class BudgetComparison(BaseModel):
    """Configured task budget compared with period study time."""

    task_id: UUID
    title: str
    estimated_seconds: int
    actual_seconds: int
    deviation_seconds: int
    usage_ratio: float | None


class ProjectTimeHistory(BaseModel):
    """Time recorded under one project in the selected date range."""

    project_id: UUID
    title: str
    seconds: int
    session_count: int
    task_count: int
    last_tracked_at: datetime


class AnalyticsSummary(BaseModel):
    """All charts and headline figures for a selected date range.

    Task completion counts refer to daily-plan item snapshots in the range,
    matching the completion controls on the Today page.
    """

    date_from: date
    date_to: date
    total_learning_seconds: int
    completed_session_count: int
    completed_task_count: int
    total_task_count: int
    task_distribution: list[TaskTimeSlice]
    daily_trend: list[DailyTrendPoint]
    budget_comparison: list[BudgetComparison]
    project_history: list[ProjectTimeHistory]
