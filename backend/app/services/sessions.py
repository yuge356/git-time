"""Study-session ownership, idempotency and state-machine rules."""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlanItem, DailyPlanItemStatus
from app.models.session import Session, SessionStatus
from app.models.task import TaskNodeType
from app.schemas.session import SessionStateUpsert
from app.services.daily_plans import get_owned_daily_item, mark_item_status
from app.services.tasks import get_owned_executable_task, get_owned_task, normalize_utc


def same_instant(left: datetime | None, right: datetime | None) -> bool:
    """Compare optional timestamps across PostgreSQL and SQLite representations."""

    if left is None or right is None:
        return left is right
    return normalize_utc(left) == normalize_utc(right)


async def get_owned_session(
    db: AsyncSession,
    owner_id: UUID,
    session_id: UUID,
) -> Session | None:
    """Return one active stored session without exposing another user's row."""

    return await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.owner_id == owner_id,
            Session.deleted_at.is_(None),
        )
    )


def complete_daily_item(daily_item: DailyPlanItem | None) -> None:
    """Complete the linked daily item when its timer is finished."""

    if daily_item is not None and daily_item.status != DailyPlanItemStatus.DONE:
        mark_item_status(daily_item, DailyPlanItemStatus.DONE)


def sync_daily_item_status(
    daily_item: DailyPlanItem | None,
    session_status: SessionStatus,
    *,
    complete_on_finish: bool,
) -> None:
    """Mirror active timer state without treating pause as completion."""

    if daily_item is None:
        return
    if session_status == SessionStatus.RUNNING:
        mark_item_status(daily_item, DailyPlanItemStatus.IN_PROGRESS)
    elif session_status == SessionStatus.PAUSED:
        mark_item_status(daily_item, DailyPlanItemStatus.PAUSED)
    elif session_status == SessionStatus.COMPLETED and complete_on_finish:
        complete_daily_item(daily_item)


def validate_transition(current: SessionStatus, incoming: SessionStatus) -> None:
    """Apply the start/pause/resume/finish state machine."""

    allowed = {
        SessionStatus.RUNNING: {
            SessionStatus.RUNNING,
            SessionStatus.PAUSED,
            SessionStatus.COMPLETED,
        },
        SessionStatus.PAUSED: {
            SessionStatus.PAUSED,
            SessionStatus.RUNNING,
            SessionStatus.COMPLETED,
        },
        SessionStatus.COMPLETED: {SessionStatus.COMPLETED},
    }
    if incoming not in allowed[current]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change session from {current} to {incoming}",
        )


async def apply_session_snapshot(
    db: AsyncSession,
    owner_id: UUID,
    session_id: UUID,
    payload: SessionStateUpsert,
) -> Session:
    """Create or update one session from the client's latest durable snapshot."""

    existing = await get_owned_session(db, owner_id, session_id)
    if existing is None:
        daily_item: DailyPlanItem | None = None
        if payload.daily_plan_item_id is not None:
            daily_item = await get_owned_daily_item(
                db,
                owner_id,
                payload.daily_plan_item_id,
            )
        resolved_task_id = payload.task_id
        if daily_item is not None and daily_item.task_id is not None:
            linked_task = await get_owned_task(db, owner_id, daily_item.task_id)
            if linked_task.node_type != TaskNodeType.TASK:
                # Compatibility for daily snapshots created before explicit
                # project/module roles existed. They remain timeable as ad-hoc
                # daily items, but containers themselves are never timed.
                legacy_task_id = daily_item.task_id
                daily_item.task_id = None
                if resolved_task_id == legacy_task_id:
                    resolved_task_id = None
        if resolved_task_id is not None:
            await get_owned_executable_task(db, owner_id, resolved_task_id)
        if daily_item is not None and daily_item.task_id != resolved_task_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session task must match the daily plan item task",
            )
        session = Session(
            id=session_id,
            owner_id=owner_id,
            task_id=resolved_task_id,
            daily_plan_item_id=payload.daily_plan_item_id,
            client_id=payload.client_id,
            status=payload.status,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            duration_seconds=payload.duration_seconds,
            last_resumed_at=payload.last_resumed_at,
            client_updated_at=payload.client_updated_at,
        )
        db.add(session)
        sync_daily_item_status(
            daily_item,
            payload.status,
            complete_on_finish=payload.complete_daily_item,
        )
        return session

    if normalize_utc(payload.client_updated_at) <= normalize_utc(existing.client_updated_at):
        return existing
    if existing.task_id != payload.task_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session cannot be moved to another task",
        )
    if existing.daily_plan_item_id != payload.daily_plan_item_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session cannot be moved to another daily plan item",
        )
    if existing.client_id != payload.client_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session cannot change its originating client",
        )
    if not same_instant(existing.started_at, payload.started_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session cannot change its start time",
        )
    if payload.duration_seconds < existing.duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session duration cannot decrease",
        )

    validate_transition(existing.status, payload.status)
    if existing.status == SessionStatus.COMPLETED:
        if (
            payload.duration_seconds != existing.duration_seconds
            or not same_instant(existing.ended_at, payload.ended_at)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Completed sessions cannot be changed",
            )

    existing.status = payload.status
    existing.ended_at = payload.ended_at
    existing.duration_seconds = payload.duration_seconds
    existing.last_resumed_at = payload.last_resumed_at
    existing.client_updated_at = payload.client_updated_at
    daily_item = (
        await get_owned_daily_item(db, owner_id, existing.daily_plan_item_id)
        if existing.daily_plan_item_id is not None
        else None
    )
    sync_daily_item_status(
        daily_item,
        payload.status,
        complete_on_finish=payload.complete_daily_item,
    )
    return existing
