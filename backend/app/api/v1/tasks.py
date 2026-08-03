"""Hierarchical task CRUD and time-budget endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.session import Session, SessionStatus
from app.models.task import (
    Task,
    TaskBudgetMode,
    TaskNodeType,
    TaskRepeatRule,
    TaskStatus,
)
from app.schemas.task import (
    TaskBulkApplyRequest,
    TaskBulkApplyResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.tasks import (
    build_owned_task_responses,
    collect_subtree_ids,
    get_owned_task,
    resolve_container_defaults,
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
    """Create one node while enforcing the fixed three-level hierarchy."""

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
    parent = await validate_parent(
        db,
        current_user.id,
        payload.parent_id,
        payload.node_type,
    )
    estimated_seconds = payload.estimated_seconds
    repeat_rule = payload.repeat_rule
    daily_reminder_time = payload.daily_reminder_time
    if payload.node_type == TaskNodeType.TASK and parent is not None:
        inherited_estimated, inherited_repeat, inherited_reminder = (
            await resolve_container_defaults(db, current_user.id, parent)
        )
        if "estimated_seconds" not in payload.model_fields_set and inherited_estimated is not None:
            estimated_seconds = inherited_estimated
        if "repeat_rule" not in payload.model_fields_set and inherited_repeat is not None:
            repeat_rule = inherited_repeat
        if (
            "daily_reminder_time" not in payload.model_fields_set
            and inherited_reminder is not None
        ):
            daily_reminder_time = inherited_reminder

    if payload.node_type != TaskNodeType.TASK:
        estimated_seconds = 0
        repeat_rule = TaskRepeatRule.NONE
        daily_reminder_time = None
        if (
            payload.budget_mode == TaskBudgetMode.FIXED_CAP
            and payload.fixed_budget_seconds is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A fixed budget requires a time limit",
            )
    elif (
        payload.budget_mode != TaskBudgetMode.ROLLUP
        or payload.fixed_budget_seconds is not None
        or payload.default_estimated_seconds is not None
        or payload.default_repeat_rule is not None
        or payload.default_daily_reminder_time is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Executable tasks cannot contain project or module defaults",
        )

    task = Task(
        **({"id": payload.id} if payload.id is not None else {}),
        owner_id=current_user.id,
        parent_id=payload.parent_id,
        node_type=payload.node_type,
        title=payload.title,
        estimated_seconds=estimated_seconds,
        budget_mode=payload.budget_mode,
        fixed_budget_seconds=(
            payload.fixed_budget_seconds
            if payload.budget_mode == TaskBudgetMode.FIXED_CAP
            else None
        ),
        default_estimated_seconds=payload.default_estimated_seconds,
        default_repeat_rule=payload.default_repeat_rule,
        default_daily_reminder_time=payload.default_daily_reminder_time,
        repeat_rule=repeat_rule,
        repeat_end_date=(
            payload.repeat_end_date if payload.node_type == TaskNodeType.TASK else None
        ),
        daily_reminder_time=daily_reminder_time,
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
        await validate_parent(
            db,
            current_user.id,
            new_parent_id,
            task.node_type,
            task.id,
        )
        if new_parent_id != task.parent_id:
            task.parent_id = new_parent_id
            task.sort_order = await next_sort_order(db, current_user.id, new_parent_id)

    if "title" in changes:
        task.title = changes["title"]
    task_only_fields = {
        "estimated_seconds",
        "repeat_rule",
        "repeat_end_date",
        "daily_reminder_time",
        "status",
    }
    container_only_fields = {
        "budget_mode",
        "fixed_budget_seconds",
        "default_estimated_seconds",
        "default_repeat_rule",
        "default_daily_reminder_time",
    }
    if task.node_type != TaskNodeType.TASK and task_only_fields.intersection(changes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Projects and modules derive task status, time and recurrence",
        )
    if task.node_type == TaskNodeType.TASK and container_only_fields.intersection(changes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Executable tasks cannot define container defaults",
        )

    for field_name in task_only_fields | container_only_fields:
        if field_name in changes:
            setattr(task, field_name, changes[field_name])
    if "budget_mode" in changes and task.budget_mode == TaskBudgetMode.ROLLUP:
        task.fixed_budget_seconds = None
    if task.budget_mode == TaskBudgetMode.FIXED_CAP and task.fixed_budget_seconds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A fixed budget requires a time limit",
        )
    if "status" in changes:
        task.completed_at = datetime.now(UTC) if task.status == TaskStatus.DONE else None

    await db.flush()
    await db.refresh(task)
    responses = await build_owned_task_responses(db, current_user.id)
    response = next(item for item in responses if item.id == task.id)
    await db.commit()
    return response


@router.post("/{task_id}/apply-defaults", response_model=TaskBulkApplyResponse)
async def apply_container_defaults(
    task_id: UUID,
    payload: TaskBulkApplyRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> TaskBulkApplyResponse:
    """Apply project/module defaults to existing descendant executable tasks."""

    container = await get_owned_task(db, current_user.id, task_id)
    if container.node_type == TaskNodeType.TASK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only projects and modules can apply defaults",
        )
    result = await db.scalars(
        select(Task).where(
            Task.owner_id == current_user.id,
            Task.deleted_at.is_(None),
        )
    )
    owned_tasks = list(result.all())
    subtree_ids = collect_subtree_ids(owned_tasks, container.id)
    descendants = [
        task
        for task in owned_tasks
        if task.id != container.id
        and task.id in subtree_ids
        and task.node_type == TaskNodeType.TASK
    ]
    affected_count = 0
    for task in descendants:
        changed = False
        if (
            payload.apply_estimated_seconds
            and container.default_estimated_seconds is not None
            and (payload.overwrite or task.estimated_seconds == 0)
        ):
            task.estimated_seconds = container.default_estimated_seconds
            changed = True
        if (
            payload.apply_repeat_rule
            and container.default_repeat_rule is not None
            and (payload.overwrite or task.repeat_rule == TaskRepeatRule.NONE)
        ):
            task.repeat_rule = container.default_repeat_rule
            changed = True
        if (
            payload.apply_daily_reminder_time
            and container.default_daily_reminder_time is not None
            and (payload.overwrite or task.daily_reminder_time is None)
        ):
            task.daily_reminder_time = container.default_daily_reminder_time
            changed = True
        if changed:
            affected_count += 1

    await db.flush()
    responses = await build_owned_task_responses(db, current_user.id)
    await db.commit()
    return TaskBulkApplyResponse(
        affected_count=affected_count,
        skipped_count=len(descendants) - affected_count,
        tasks=responses,
    )


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
