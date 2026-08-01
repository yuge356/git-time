"""Daily plan creation, item editing and check-in endpoints."""

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.daily_plan import DailyPlan, DailyPlanItem
from app.models.session import Session, SessionStatus
from app.models.sharing import DailyPlanShare, NotificationType
from app.schemas.daily_plan import (
    CheckInResponse,
    DailyPlanCreate,
    DailyPlanItemCreate,
    DailyPlanItemResponse,
    DailyPlanItemUpdate,
    DailyPlanResponse,
)
from app.services.daily_plans import (
    build_check_in,
    build_daily_plan_response,
    get_owned_daily_item,
    get_owned_daily_plan,
    get_owned_daily_plan_by_date,
    mark_item_status,
)
from app.services.notifications import create_notification, notification_manager
from app.services.tasks import get_owned_task

router = APIRouter(tags=["daily plans"])


@router.post(
    "/daily-plans",
    response_model=DailyPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_daily_plan(
    payload: DailyPlanCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> DailyPlanResponse:
    """Create the owner's unique plan for a local date."""

    existing = await db.scalar(
        select(DailyPlan).where(
            DailyPlan.owner_id == current_user.id,
            DailyPlan.plan_date == payload.plan_date,
            DailyPlan.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return await build_daily_plan_response(db, existing)
    plan = DailyPlan(
        **({"id": payload.id} if payload.id is not None else {}),
        owner_id=current_user.id,
        plan_date=payload.plan_date,
    )
    db.add(plan)
    try:
        await db.flush()
        await db.refresh(plan)
        response = await build_daily_plan_response(db, plan)
        await db.commit()
        return response
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A daily plan already exists for this date",
        ) from exc


@router.get("/daily-plans/by-date/{plan_date}", response_model=DailyPlanResponse)
async def read_daily_plan_by_date(
    plan_date: date,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> DailyPlanResponse:
    """Return one daily plan with item and study-time totals."""

    plan = await get_owned_daily_plan_by_date(db, current_user.id, plan_date)
    return await build_daily_plan_response(db, plan)


@router.post(
    "/daily-plans/{plan_id}/items",
    response_model=DailyPlanItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_daily_plan_item(
    plan_id: UUID,
    payload: DailyPlanItemCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> DailyPlanItemResponse:
    """Append a linked long-term task or ad-hoc item to a daily plan."""

    plan = await get_owned_daily_plan(db, current_user.id, plan_id)
    if payload.id is not None:
        existing = await db.scalar(
            select(DailyPlanItem).where(
                DailyPlanItem.id == payload.id,
                DailyPlanItem.daily_plan_id == plan.id,
                DailyPlanItem.owner_id == current_user.id,
                DailyPlanItem.deleted_at.is_(None),
            )
        )
        if existing is not None:
            response = await build_daily_plan_response(db, plan)
            return next(item for item in response.items if item.id == existing.id)
    linked_task = (
        await get_owned_task(db, current_user.id, payload.task_id)
        if payload.task_id is not None
        else None
    )
    title = linked_task.title if linked_task is not None else payload.title
    estimated = (
        payload.estimated_seconds
        if payload.estimated_seconds is not None
        else linked_task.estimated_seconds if linked_task is not None else 0
    )
    current_max = await db.scalar(
        select(func.max(DailyPlanItem.sort_order)).where(
            DailyPlanItem.daily_plan_id == plan.id,
            DailyPlanItem.deleted_at.is_(None),
        )
    )
    item = DailyPlanItem(
        **({"id": payload.id} if payload.id is not None else {}),
        daily_plan_id=plan.id,
        owner_id=current_user.id,
        task_id=linked_task.id if linked_task is not None else None,
        title=title,
        estimated_seconds=estimated,
        sort_order=(current_max if current_max is not None else -1) + 1,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    response = DailyPlanItemResponse(
        **{
            column: getattr(item, column)
            for column in (
                "id",
                "daily_plan_id",
                "owner_id",
                "task_id",
                "title",
                "status",
                "estimated_seconds",
                "sort_order",
                "completed_at",
                "created_at",
                "updated_at",
            )
        },
        actual_seconds=0,
    )
    await db.commit()
    return response


@router.patch("/daily-plan-items/{item_id}", response_model=DailyPlanItemResponse)
async def update_daily_plan_item(
    item_id: UUID,
    payload: DailyPlanItemUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> DailyPlanItemResponse:
    """Edit a daily item and keep its completion timestamp consistent."""

    item = await get_owned_daily_item(db, current_user.id, item_id)
    was_done = item.status.value == "DONE"
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        item.title = changes["title"]
    if "estimated_seconds" in changes:
        item.estimated_seconds = changes["estimated_seconds"]
    if "sort_order" in changes:
        item.sort_order = changes["sort_order"]
    if "status" in changes:
        mark_item_status(item, changes["status"])
    notifications = []
    if (
        "status" in changes
        and changes["status"].value == "DONE"
        and not was_done
    ):
        shares = list(
            (
                await db.scalars(
                    select(DailyPlanShare).where(
                        DailyPlanShare.daily_plan_id == item.daily_plan_id,
                        DailyPlanShare.owner_id == current_user.id,
                        DailyPlanShare.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        for share in shares:
            notifications.append(
                await create_notification(
                    db,
                    user_id=share.partner_id,
                    actor_id=current_user.id,
                    notification_type=NotificationType.TASK_COMPLETED,
                    payload={
                        "daily_plan_id": str(item.daily_plan_id),
                        "item_id": str(item.id),
                        "item_title": item.title,
                    },
                )
            )
    await db.flush()
    await db.refresh(item)
    plan = await get_owned_daily_plan(db, current_user.id, item.daily_plan_id)
    response = await build_daily_plan_response(db, plan)
    await db.commit()
    for notification in notifications:
        await notification_manager.publish(notification)
    return next(candidate for candidate in response.items if candidate.id == item.id)


@router.delete("/daily-plan-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_plan_item(
    item_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Soft-delete a daily item after its active timer has finished."""

    item = await get_owned_daily_item(db, current_user.id, item_id)
    active_session = await db.scalar(
        select(Session.id).where(
            Session.owner_id == current_user.id,
            Session.daily_plan_item_id == item.id,
            Session.status.in_([SessionStatus.RUNNING, SessionStatus.PAUSED]),
            Session.deleted_at.is_(None),
        )
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish the active timer before deleting this daily item",
        )
    item.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/check-ins/{plan_date}", response_model=CheckInResponse)
async def read_check_in(
    plan_date: date,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> CheckInResponse:
    """Return the selected day's learning, completion and streak figures."""

    return await build_check_in(
        db,
        current_user.id,
        plan_date,
        current_user.profile.timezone,
    )
