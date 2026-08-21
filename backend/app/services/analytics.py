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
    HourlyFocusPoint,
    HourlyFocusResponse,
    ProjectTimeHistory,
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


async def build_hourly_focus(
    db: AsyncSession,
    owner_id: UUID,
    timezone_name: str,
    day: date,
) -> HourlyFocusResponse:
    """Bucket one local date's session time into 24 clock hours.

    Sessions are attributed to the clock hour in which they started, matching
    how ``daily_trend`` attributes whole sessions to their start date.
    """

    timezone = resolve_timezone(timezone_name)
    start_at = datetime.combine(day, time.min, tzinfo=timezone).astimezone(UTC)
    end_at = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone).astimezone(UTC)
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
    hourly_seconds = [0] * 24
    for session in sessions:
        seconds = effective_session_duration(session)
        if seconds <= 0:
            continue
        hour = normalize_utc(session.started_at).astimezone(timezone).hour
        hourly_seconds[hour] += seconds
    return HourlyFocusResponse(
        date=day,
        total_seconds=sum(hourly_seconds),
        hours=[
            HourlyFocusPoint(hour=hour, seconds=seconds)
            for hour, seconds in enumerate(hourly_seconds)
        ],
    )


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

    all_tasks = list(
        (
            await db.scalars(
                select(Task).where(
                    Task.owner_id == owner_id,
                )
            )
        ).all()
    )
    tasks = [task for task in all_tasks if task.deleted_at is None]
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
    task_titles = {task.id: task.title for task in all_tasks}
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
    # Anything added to a daily plan belongs on the analytics page even
    # before its first timer start — show planned-but-untimed items with
    # zero seconds. Removing the item from the plan (soft delete) hides it
    # again, while its recorded sessions keep counting on their own.
    distribution_task_ids = {slice.task_id for slice in distribution}
    distribution_titles = {slice.title for slice in distribution}
    for item in items:
        if item.task_id is not None:
            if item.task_id in distribution_task_ids:
                continue
            distribution_task_ids.add(item.task_id)
        else:
            if item.title in distribution_titles:
                continue
            distribution_titles.add(item.title)
        distribution.append(
            TaskTimeSlice(
                task_id=item.task_id,
                title=item.title,
                seconds=0,
                percentage=0,
            )
        )

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

    task_by_id = {task.id: task for task in all_tasks}
    project_seconds: dict[UUID, int] = {}
    project_session_counts: dict[UUID, int] = {}
    project_task_ids: dict[UUID, set[UUID]] = {}
    project_last_tracked: dict[UUID, datetime] = {}

    def resolve_project(task_id: UUID | None) -> Task | None:
        current = task_by_id.get(task_id) if task_id is not None else None
        visited: set[UUID] = set()
        while current is not None and current.id not in visited:
            visited.add(current.id)
            if current.node_type == TaskNodeType.PROJECT:
                return current
            current = task_by_id.get(current.parent_id) if current.parent_id is not None else None
        return None

    for session in sessions:
        seconds = session_durations[session.id]
        project = resolve_project(session.task_id)
        if project is None or seconds <= 0:
            continue
        project_seconds[project.id] = project_seconds.get(project.id, 0) + seconds
        project_session_counts[project.id] = project_session_counts.get(project.id, 0) + 1
        if session.task_id is not None:
            project_task_ids.setdefault(project.id, set()).add(session.task_id)
        started_at = normalize_utc(session.started_at)
        previous = project_last_tracked.get(project.id)
        if previous is None or started_at > previous:
            project_last_tracked[project.id] = started_at

    project_history = [
        ProjectTimeHistory(
            project_id=project_id,
            title=task_by_id[project_id].title,
            seconds=seconds,
            session_count=project_session_counts[project_id],
            task_count=len(project_task_ids.get(project_id, set())),
            last_tracked_at=project_last_tracked[project_id],
        )
        for project_id, seconds in project_seconds.items()
    ]
    project_history.sort(key=lambda item: item.last_tracked_at, reverse=True)

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

    # The Today page completes a durable DailyPlanItem snapshot, not the
    # source project Task. Counting Task.completed_at here made a successfully
    # completed Today item invisible in analytics (and would also break
    # recurring tasks, whose project definition must stay open for the next
    # occurrence). Use the same date-bounded daily items as the Today page so
    # every checked/finished item is reflected exactly once.
    completed_tasks = sum(
        item.status == DailyPlanItemStatus.DONE
        for item in items
    )
    return AnalyticsSummary(
        date_from=date_from,
        date_to=date_to,
        total_learning_seconds=total_seconds,
        completed_session_count=sum(
            session.status == SessionStatus.COMPLETED for session in sessions
        ),
        completed_task_count=completed_tasks,
        total_task_count=len(items),
        task_distribution=distribution,
        daily_trend=daily_trend,
        budget_comparison=budget_comparison,
        project_history=project_history,
    )
