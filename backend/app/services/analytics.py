"""Aggregate existing tasks, sessions and daily-plan completions."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlan, DailyPlanItem, DailyPlanItemStatus
from app.models.session import Session, SessionStatus
from app.models.task import Task, TaskNodeType
from app.schemas.analytics import (
    AnalyticsSummary,
    BudgetComparison,
    DailyTrendPoint,
    TaskTimeSlice,
)
from app.services.tasks import (
    calculate_task_time_totals,
    effective_session_duration,
    normalize_utc,
)


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    """Use the validated profile timezone, with a safe legacy-row fallback."""

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


async def build_analytics_summary(
    db: AsyncSession,
    owner_id: UUID,
    timezone_name: str,
    date_from: date,
    date_to: date,
) -> AnalyticsSummary:
    """Build a bounded, owner-filtered analytics snapshot."""

    timezone = resolve_timezone(timezone_name)
    start_at = datetime.combine(date_from, time.min, tzinfo=timezone).astimezone(UTC)
    end_at = datetime.combine(
        date_to + timedelta(days=1),
        time.min,
        tzinfo=timezone,
    ).astimezone(UTC)

    tasks = list(
        (
            await db.scalars(
                select(Task).where(
                    Task.owner_id == owner_id,
                    Task.deleted_at.is_(None),
                )
            )
        ).all()
    )
    executable_tasks = [task for task in tasks if task.node_type == TaskNodeType.TASK]
    sessions = list(
        (
            await db.scalars(
                select(Session).where(
                    Session.owner_id == owner_id,
                    Session.started_at >= start_at,
                    Session.started_at < end_at,
                    Session.deleted_at.is_(None),
                )
            )
        ).all()
    )
    items = list(
        (
            await db.scalars(
                select(DailyPlanItem)
                .join(DailyPlan, DailyPlan.id == DailyPlanItem.daily_plan_id)
                .where(
                    DailyPlan.owner_id == owner_id,
                    DailyPlan.plan_date >= date_from,
                    DailyPlan.plan_date <= date_to,
                    DailyPlan.deleted_at.is_(None),
                    DailyPlanItem.deleted_at.is_(None),
                )
            )
        ).all()
    )
    plans = list(
        (
            await db.scalars(
                select(DailyPlan).where(
                    DailyPlan.owner_id == owner_id,
                    DailyPlan.plan_date >= date_from,
                    DailyPlan.plan_date <= date_to,
                    DailyPlan.deleted_at.is_(None),
                )
            )
        ).all()
    )

    session_durations = {
        session.id: effective_session_duration(session) for session in sessions
    }
    total_seconds = sum(session_durations.values())
    task_titles = {task.id: task.title for task in tasks}
    direct_distribution: dict[UUID | None, int] = {}
    for session in sessions:
        direct_distribution[session.task_id] = (
            direct_distribution.get(session.task_id, 0)
            + session_durations[session.id]
        )
    distribution = [
        TaskTimeSlice(
            task_id=task_id,
            title=task_titles.get(task_id, "当日临时事项"),
            seconds=seconds,
            percentage=seconds / total_seconds if total_seconds else 0,
        )
        for task_id, seconds in sorted(
            direct_distribution.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if seconds > 0
    ]

    _, task_totals = calculate_task_time_totals(tasks, sessions)
    budget_comparison = [
        BudgetComparison(
            task_id=task.id,
            title=task.title,
            estimated_seconds=task.estimated_seconds,
            actual_seconds=task_totals.get(task.id, 0),
            deviation_seconds=task_totals.get(task.id, 0) - task.estimated_seconds,
            usage_ratio=(
                task_totals.get(task.id, 0) / task.estimated_seconds
                if task.estimated_seconds > 0
                else None
            ),
        )
        for task in executable_tasks
        if task.estimated_seconds > 0 or task_totals.get(task.id, 0) > 0
    ]
    budget_comparison.sort(key=lambda item: item.actual_seconds, reverse=True)

    daily_seconds: dict[date, int] = {}
    for session in sessions:
        local_date = normalize_utc(session.started_at).astimezone(timezone).date()
        daily_seconds[local_date] = (
            daily_seconds.get(local_date, 0) + session_durations[session.id]
        )
    plan_dates = {plan.id: plan.plan_date for plan in plans}
    daily_completed: dict[date, int] = {}
    for item in items:
        if item.status == DailyPlanItemStatus.DONE:
            item_date = plan_dates[item.daily_plan_id]
            daily_completed[item_date] = daily_completed.get(item_date, 0) + 1

    daily_trend: list[DailyTrendPoint] = []
    cursor = date_from
    while cursor <= date_to:
        daily_trend.append(
            DailyTrendPoint(
                date=cursor,
                seconds=daily_seconds.get(cursor, 0),
                completed_items=daily_completed.get(cursor, 0),
            )
        )
        cursor += timedelta(days=1)

    completed_tasks = sum(
        task.completed_at is not None
        and start_at <= normalize_utc(task.completed_at) < end_at
        for task in executable_tasks
    )
    return AnalyticsSummary(
        date_from=date_from,
        date_to=date_to,
        total_learning_seconds=total_seconds,
        completed_session_count=sum(
            session.status == SessionStatus.COMPLETED for session in sessions
        ),
        completed_task_count=completed_tasks,
        total_task_count=len(executable_tasks),
        task_distribution=distribution,
        daily_trend=daily_trend,
        budget_comparison=budget_comparison,
    )
