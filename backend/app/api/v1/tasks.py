"""Hierarchical task CRUD and time-budget endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.session import Session, SessionStatus
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.tasks import (
    build_owned_task_responses,
    collect_subtree_ids,
    get_owned_task,
    validate_parent,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def next_sort_order(
    db: DatabaseSession,
    owner_id: UUID,
    parent_id: UUID | None,
) -> int:
    """Append a new or moved task to the end of its sibling list."""

    parent_filter = Task.parent_id.is_(None) if parent_id is None else Task.parent_id == parent_id
    current_max = await db.scalar(
        select(func.max(Task.sort_order)).where(
            Task.owner_id == owner_id,
            parent_filter,
            Task.deleted_at.is_(None),
        )
    )
    return (current_max if current_max is not None else -1) + 1


@router.get("", response_model=list[TaskResponse])
async def list_tasks(db: DatabaseSession, current_user: CurrentUser) -> list[TaskResponse]:
    """Return all active owned tasks as a stable flat list for tree construction."""

    return await build_owned_task_responses(db, current_user.id)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> TaskResponse:
    """Create a root task or an owned child task."""

    if payload.id is not None:
        existing = await db.scalar(
            select(Task).where(
                Task.id == payload.id,
                Task.owner_id == current_user.id,
                Task.deleted_at.is_(None),
            )
        )
        if existing is not None:
            responses = await build_owned_task_responses(db, current_user.id)
            return next(item for item in responses if item.id == existing.id)
    await validate_parent(db, current_user.id, payload.parent_id)
    task = Task(
        **({"id": payload.id} if payload.id is not None else {}),
        owner_id=current_user.id,
        parent_id=payload.parent_id,
        title=payload.title,
        estimated_seconds=payload.estimated_seconds,
        repeat_rule=payload.repeat_rule,
        repeat_end_date=payload.repeat_end_date,
        daily_reminder_time=payload.daily_reminder_time,
        sort_order=await next_sort_order(db, current_user.id, payload.parent_id),
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    responses = await build_owned_task_responses(db, current_user.id)
    response = next(item for item in responses if item.id == task.id)
    await db.commit()
    return response


@router.get("/{task_id}", response_model=TaskResponse)
async def read_task(
    task_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> TaskResponse:
    """Return one active owned task."""

    await get_owned_task(db, current_user.id, task_id)
    responses = await build_owned_task_responses(db, current_user.id)
    return next(item for item in responses if item.id == task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> TaskResponse:
    """Update task content, hierarchy, budget or lifecycle status."""

    task = await get_owned_task(db, current_user.id, task_id)
    changes = payload.model_dump(exclude_unset=True)

    if "parent_id" in changes:
        new_parent_id = changes["parent_id"]
        await validate_parent(db, current_user.id, new_parent_id, task.id)
        if new_parent_id != task.parent_id:
            task.parent_id = new_parent_id
            task.sort_order = await next_sort_order(db, current_user.id, new_parent_id)

    if "title" in changes:
        task.title = changes["title"]
    if "estimated_seconds" in changes:
        task.estimated_seconds = changes["estimated_seconds"]
    if "repeat_rule" in changes:
        task.repeat_rule = changes["repeat_rule"]
    if "repeat_end_date" in changes:
        task.repeat_end_date = changes["repeat_end_date"]
    if "daily_reminder_time" in changes:
        task.daily_reminder_time = changes["daily_reminder_time"]
    if "status" in changes:
        task.status = changes["status"]
        task.completed_at = datetime.now(UTC) if task.status == TaskStatus.DONE else None

    await db.flush()
    await db.refresh(task)
    responses = await build_owned_task_responses(db, current_user.id)
    response = next(item for item in responses if item.id == task.id)
    await db.commit()
    return response


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Soft-delete a task and every descendant in its subtree."""

    await get_owned_task(db, current_user.id, task_id)
    result = await db.scalars(
        select(Task).where(
            Task.owner_id == current_user.id,
            Task.deleted_at.is_(None),
        )
    )
    owned_tasks = result.all()
    subtree_ids = collect_subtree_ids(owned_tasks, task_id)
    active_session = await db.scalar(
        select(Session.id).where(
            Session.owner_id == current_user.id,
            Session.task_id.in_(subtree_ids),
            Session.status.in_([SessionStatus.RUNNING, SessionStatus.PAUSED]),
            Session.deleted_at.is_(None),
        )
    )
    if active_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finish the active timer before deleting its task",
        )

    deleted_at = datetime.now(UTC)
    for task in owned_tasks:
        if task.id in subtree_ids:
            task.deleted_at = deleted_at

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
