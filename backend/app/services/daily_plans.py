"""Daily-plan ownership, progress and check-in calculations."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlan, DailyPlanItem, DailyPlanItemStatus
from app.models.session import Session
from app.models.task import Task, TaskRepeatRule
from app.schemas.daily_plan import (
    CheckInResponse,
    DailyPlanItemResponse,
    DailyPlanResponse,
)
from app.services.analytics import resolve_timezone
from app.services.tasks import effective_session_duration


async def get_owned_daily_plan(
    db: AsyncSession,
    owner_id: UUID,
    plan_id: UUID,
) -> DailyPlan:
    """Return an active owned plan without revealing other users' rows."""

    plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.id == plan_id,
            DailyPlan.owner_id == owner_id,
            DailyPlan.deleted_at.is_(None),
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily plan not found")
    return plan


async def get_owned_daily_plan_by_date(
    db: AsyncSession,
    owner_id: UUID,
    plan_date: date,
) -> DailyPlan:
    """Return the owner's plan for one local date."""

    plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.owner_id == owner_id,
            DailyPlan.plan_date == plan_date,
            DailyPlan.deleted_at.is_(None),
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily plan not found")
    return plan


async def get_owned_daily_item(
    db: AsyncSession,
    owner_id: UUID,
    item_id: UUID,
) -> DailyPlanItem:
    """Return an active owned daily item."""

    item = await db.scalar(
        select(DailyPlanItem).where(
            DailyPlanItem.id == item_id,
            DailyPlanItem.owner_id == owner_id,
            DailyPlanItem.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily plan item not found",
        )
    return item


async def build_daily_plan_response(
    db: AsyncSession,
    plan: DailyPlan,
) -> DailyPlanResponse:
    """Load ordered items and calculate their linked session totals."""

    items = list(
        (
            await db.scalars(
                select(DailyPlanItem)
                .where(
                    DailyPlanItem.daily_plan_id == plan.id,
                    DailyPlanItem.owner_id == plan.owner_id,
                    DailyPlanItem.deleted_at.is_(None),
                )
                .order_by(
                    DailyPlanItem.sort_order,
                    DailyPlanItem.created_at,
                    DailyPlanItem.id,
                )
            )
        ).all()
    )
    item_ids = [item.id for item in items]
    sessions: list[Session] = []
    if item_ids:
        sessions = list(
            (
                await db.scalars(
                    select(Session).where(
                        Session.owner_id == plan.owner_id,
                        Session.daily_plan_item_id.in_(item_ids),
                        Session.deleted_at.is_(None),
                    )
                )
            ).all()
        )

    durations: dict[UUID, int] = {item.id: 0 for item in items}
    for session in sessions:
        if session.daily_plan_item_id in durations:
            durations[session.daily_plan_item_id] += effective_session_duration(session)

    responses = [
        DailyPlanItemResponse(
            id=item.id,
            daily_plan_id=item.daily_plan_id,
            owner_id=item.owner_id,
            task_id=item.task_id,
            title=item.title,
            status=item.status,
            estimated_seconds=item.estimated_seconds,
            actual_seconds=durations[item.id],
            sort_order=item.sort_order,
            completed_at=item.completed_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]
    completed = sum(item.status == DailyPlanItemStatus.DONE for item in items)
    total = len(items)
    return DailyPlanResponse(
        id=plan.id,
        owner_id=plan.owner_id,
        plan_date=plan.plan_date,
        items=responses,
        total_items=total,
        completed_items=completed,
        completion_rate=completed / total if total else 0,
        actual_seconds=sum(durations.values()),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


async def build_check_in(
    db: AsyncSession,
    owner_id: UUID,
    plan_date: date,
    timezone_name: str = "UTC",
) -> CheckInResponse:
    """Return progress and the consecutive completed-plan streak.

    ``learning_seconds`` records the whole day's study time: every session
    the owner started on that local date counts, whether or not it was
    linked to a daily plan item.
    """

    timezone = resolve_timezone(timezone_name)
    day_start = datetime.combine(plan_date, time.min, tzinfo=timezone).astimezone(UTC)
    day_end = day_start + timedelta(days=1)
    day_sessions = list(
        (
            await db.scalars(
                select(Session).where(
                    Session.owner_id == owner_id,
                    Session.deleted_at.is_(None),
                    Session.started_at >= day_start,
                    Session.started_at < day_end,
                )
            )
        ).all()
    )
    learning_seconds = sum(effective_session_duration(session) for session in day_sessions)

    plan = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.owner_id == owner_id,
            DailyPlan.plan_date == plan_date,
            DailyPlan.deleted_at.is_(None),
        )
    )
    if plan is None:
        return CheckInResponse(
            plan_date=plan_date,
            learning_seconds=learning_seconds,
            completed_items=0,
            total_items=0,
            streak_days=0,
        )

    response = await build_daily_plan_response(db, plan)
    completed_dates = set(
        (
            await db.scalars(
                select(DailyPlan.plan_date)
                .join(
                    DailyPlanItem,
                    DailyPlanItem.daily_plan_id == DailyPlan.id,
                )
                .where(
                    DailyPlan.owner_id == owner_id,
                    DailyPlan.plan_date <= plan_date,
                    DailyPlan.deleted_at.is_(None),
                    DailyPlanItem.deleted_at.is_(None),
                    DailyPlanItem.status == DailyPlanItemStatus.DONE,
                )
                .distinct()
            )
        ).all()
    )
    streak = 0
    cursor = plan_date
    while cursor in completed_dates:
        streak += 1
        cursor -= timedelta(days=1)

    return CheckInResponse(
        plan_date=plan_date,
        learning_seconds=learning_seconds,
        completed_items=response.completed_items,
        total_items=response.total_items,
        streak_days=streak,
    )


def mark_item_status(item: DailyPlanItem, incoming: DailyPlanItemStatus) -> None:
    """Keep completion timestamps consistent with daily-item status."""

    item.status = incoming
    item.completed_at = datetime.now(UTC) if incoming == DailyPlanItemStatus.DONE else None


async def auto_populate_recurring_items(
    db: AsyncSession,
    owner_id: UUID,
    plan_id: UUID,
) -> DailyPlanResponse:
    """Populate a daily plan with recurring tasks that don't already exist in it."""
    
    plan = await get_owned_daily_plan(db, owner_id, plan_id)
    
    task_result = await db.scalars(
        select(Task).where(
            Task.owner_id == owner_id,
            Task.deleted_at.is_(None)
        )
    )
    tasks = task_result.all()
    
    children_map = {t.parent_id for t in tasks if t.parent_id is not None}
    is_weekday = plan.plan_date.weekday() < 5
    
    existing_items_result = await db.scalars(
        select(DailyPlanItem).where(
            DailyPlanItem.daily_plan_id == plan.id,
            DailyPlanItem.deleted_at.is_(None)
        )
    )
    existing_task_ids = {item.task_id for item in existing_items_result.all() if item.task_id is not None}
    
    current_max = await db.scalar(
        select(func.max(DailyPlanItem.sort_order)).where(
            DailyPlanItem.daily_plan_id == plan.id,
            DailyPlanItem.deleted_at.is_(None),
        )
    )
    sort_order = (current_max if current_max is not None else -1) + 1
    
    new_items = []
    for t in tasks:
        if t.id in children_map:
            continue
        if t.repeat_rule not in (TaskRepeatRule.DAILY, TaskRepeatRule.WEEKDAYS):
            continue
        if t.repeat_rule == TaskRepeatRule.WEEKDAYS and not is_weekday:
            continue
        if t.repeat_end_date and t.repeat_end_date < plan.plan_date:
            continue
        if t.id in existing_task_ids:
            continue
            
        item = DailyPlanItem(
            daily_plan_id=plan.id,
            owner_id=owner_id,
            task_id=t.id,
            title=t.title,
            estimated_seconds=t.estimated_seconds,
            sort_order=sort_order
        )
        db.add(item)
        sort_order += 1
        new_items.append(item)
        
    if new_items:
        await db.flush()
        
    return await build_daily_plan_response(db, plan)
