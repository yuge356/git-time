"""Task-tree validation and budget-calculation helpers."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, time
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, SessionStatus
from app.models.task import Task, TaskBudgetMode, TaskNodeType, TaskStatus
from app.schemas.task import BudgetLevel, TaskResponse


def calculate_budget_level(estimated_seconds: int, actual_seconds: int) -> BudgetLevel:
    """Map actual/estimated time to the required 80%, 100% and 150% bands."""

    if estimated_seconds <= 0:
        return BudgetLevel.NOT_SET
    ratio = actual_seconds / estimated_seconds
    if ratio >= 1.5:
        return BudgetLevel.SEVERE
    if ratio >= 1:
        return BudgetLevel.EXHAUSTED
    if ratio >= 0.8:
        return BudgetLevel.NEAR_LIMIT
    return BudgetLevel.NORMAL


def to_task_response(
    task: Task,
    actual_seconds: int = 0,
    direct_actual_seconds: int = 0,
    planned_seconds: int = 0,
    children_estimated_seconds: int = 0,
    task_count: int = 0,
    completed_task_count: int = 0,
) -> TaskResponse:
    """Build a response from server-owned hierarchy and budget summaries."""

    ratio = actual_seconds / planned_seconds if planned_seconds > 0 else None
    return TaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        parent_id=task.parent_id,
        node_type=task.node_type,
        title=task.title,
        status=task.status,
        estimated_seconds=task.estimated_seconds,
        budget_mode=task.budget_mode,
        fixed_budget_seconds=task.fixed_budget_seconds,
        default_estimated_seconds=task.default_estimated_seconds,
        default_repeat_rule=task.default_repeat_rule,
        default_daily_reminder_time=task.default_daily_reminder_time,
        repeat_rule=task.repeat_rule,
        repeat_end_date=task.repeat_end_date,
        daily_reminder_time=task.daily_reminder_time,
        sort_order=task.sort_order,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        direct_actual_seconds=direct_actual_seconds,
        actual_seconds=actual_seconds,
        planned_seconds=planned_seconds,
        children_estimated_seconds=children_estimated_seconds,
        is_leaf=task.node_type == TaskNodeType.TASK,
        task_count=task_count,
        completed_task_count=completed_task_count,
        progress_ratio=(completed_task_count / task_count if task_count else None),
        budget_usage_ratio=ratio,
        budget_level=calculate_budget_level(planned_seconds, actual_seconds),
    )


def normalize_utc(value: datetime) -> datetime:
    """Normalize SQLite-naive and PostgreSQL-aware timestamps for arithmetic."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def effective_session_duration(session: Session, now: datetime | None = None) -> int:
    """Include the current running interval without rewriting the row every second."""

    duration = session.duration_seconds
    if session.status == SessionStatus.RUNNING and session.last_resumed_at is not None:
        current_time = normalize_utc(now or datetime.now(UTC))
        resumed_at = normalize_utc(session.last_resumed_at)
        duration += max(0, int((current_time - resumed_at).total_seconds()))
    return duration


def calculate_task_time_totals(
    tasks: Sequence[Task],
    sessions: Iterable[Session],
    now: datetime | None = None,
) -> tuple[dict[UUID, int], dict[UUID, int]]:
    """Return direct time and descendant-inclusive time for every task."""

    direct: dict[UUID, int] = {task.id: 0 for task in tasks}
    for session in sessions:
        if session.task_id in direct:
            direct[session.task_id] += effective_session_duration(session, now)

    children: dict[UUID, list[UUID]] = {}
    for task in tasks:
        if task.parent_id is not None:
            children.setdefault(task.parent_id, []).append(task.id)

    totals: dict[UUID, int] = {}

    def visit(task_id: UUID, active_path: set[UUID]) -> int:
        if task_id in totals:
            return totals[task_id]
        if task_id in active_path:
            # The database and API both prevent cycles. This guard keeps a
            # malformed legacy row from causing infinite recursion.
            return direct.get(task_id, 0)
        next_path = {*active_path, task_id}
        total = direct.get(task_id, 0)
        for child_id in children.get(task_id, []):
            total += visit(child_id, next_path)
        totals[task_id] = total
        return total

    for task in tasks:
        visit(task.id, set())
    return direct, totals


def calculate_task_summaries(
    tasks: Sequence[Task],
) -> tuple[dict[UUID, int], dict[UUID, int], dict[UUID, int], dict[UUID, int]]:
    """Return descendant budgets, display budgets and task completion totals."""

    children_map: dict[UUID, list[UUID]] = {}
    for task in tasks:
        if task.parent_id is not None:
            children_map.setdefault(task.parent_id, []).append(task.id)

    task_by_id = {task.id: task for task in tasks}
    descendant_budgets: dict[UUID, int] = {}
    planned_budgets: dict[UUID, int] = {}
    task_counts: dict[UUID, int] = {}
    completed_counts: dict[UUID, int] = {}

    def visit(task_id: UUID, active_path: set[UUID]) -> tuple[int, int, int]:
        if task_id in descendant_budgets:
            task = task_by_id[task_id]
            return (
                (
                    task.estimated_seconds
                    if task.node_type == TaskNodeType.TASK
                    else descendant_budgets[task_id]
                ),
                task_counts[task_id],
                completed_counts[task_id],
            )
        task = task_by_id[task_id]
        if task_id in active_path:
            return (0, 0, 0)
        if task.node_type == TaskNodeType.TASK:
            descendant_budgets[task_id] = 0
            planned_budgets[task_id] = task.estimated_seconds
            task_counts[task_id] = 1
            completed_counts[task_id] = int(task.status == TaskStatus.DONE)
            return (task.estimated_seconds, 1, completed_counts[task_id])

        next_path = {*active_path, task_id}
        rolled_up_budget = 0
        task_count = 0
        completed_count = 0
        for child_id in children_map.get(task_id, []):
            if child_id not in task_by_id:
                continue
            child_budget, child_count, child_completed = visit(child_id, next_path)
            rolled_up_budget += child_budget
            task_count += child_count
            completed_count += child_completed
        descendant_budgets[task_id] = rolled_up_budget
        planned_budgets[task_id] = (
            task.fixed_budget_seconds or 0
            if task.budget_mode == TaskBudgetMode.FIXED_CAP
            else rolled_up_budget
        )
        task_counts[task_id] = task_count
        completed_counts[task_id] = completed_count
        return (rolled_up_budget, task_count, completed_count)

    for task in tasks:
        visit(task.id, set())

    return descendant_budgets, planned_budgets, task_counts, completed_counts


async def build_owned_task_responses(
    db: AsyncSession,
    owner_id: UUID,
) -> list[TaskResponse]:
    """Load active tasks and sessions and calculate all budget statistics."""

    task_result = await db.scalars(
        select(Task)
        .where(Task.owner_id == owner_id, Task.deleted_at.is_(None))
        .order_by(Task.sort_order, Task.created_at, Task.id)
    )
    tasks = task_result.all()
    session_result = await db.scalars(
        select(Session).where(
            Session.owner_id == owner_id,
            Session.deleted_at.is_(None),
        )
    )
    sessions = session_result.all()
    direct, totals = calculate_task_time_totals(tasks, sessions)
    children_estimated, planned, task_counts, completed_counts = calculate_task_summaries(tasks)
    return [
        to_task_response(
            task,
            actual_seconds=totals.get(task.id, 0),
            direct_actual_seconds=direct.get(task.id, 0),
            planned_seconds=planned.get(task.id, 0),
            children_estimated_seconds=children_estimated.get(task.id, 0),
            task_count=task_counts.get(task.id, 0),
            completed_task_count=completed_counts.get(task.id, 0),
        )
        for task in tasks
    ]


async def get_owned_task(
    db: AsyncSession,
    owner_id: UUID,
    task_id: UUID,
) -> Task:
    """Return one active owned task or a non-disclosing 404."""

    task = await db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.owner_id == owner_id,
            Task.deleted_at.is_(None),
        )
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def get_owned_executable_task(
    db: AsyncSession,
    owner_id: UUID,
    task_id: UUID,
) -> Task:
    """Return an owned executable task and reject project/module containers."""

    task = await get_owned_task(db, owner_id, task_id)
    if task.node_type != TaskNodeType.TASK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only executable tasks can be timed or added to a daily plan",
        )
    return task


async def validate_parent(
    db: AsyncSession,
    owner_id: UUID,
    parent_id: UUID | None,
    node_type: TaskNodeType,
    task_id: UUID | None = None,
) -> Task | None:
    """Enforce PROJECT -> MODULE -> TASK and prevent hierarchy cycles."""

    if node_type == TaskNodeType.PROJECT:
        if parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Projects must stay at the top level",
            )
        return None
    if parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{node_type.value.title()} nodes require a parent",
        )
    if task_id is not None and parent_id == task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task cannot be its own parent",
        )

    parent = await get_owned_task(db, owner_id, parent_id)
    expected_parent_type = {
        TaskNodeType.MODULE: TaskNodeType.PROJECT,
        TaskNodeType.TASK: TaskNodeType.MODULE,
    }[node_type]
    if parent.node_type != expected_parent_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{node_type.value.title()} nodes must be placed under "
                f"{expected_parent_type.value.lower()} nodes"
            ),
        )
    if task_id is None:
        return parent

    # Walk toward the root. The database trigger repeats this invariant for
    # writes that do not pass through FastAPI.
    visited: set[UUID] = set()
    current: Task | None = parent
    while current is not None:
        if current.id == task_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task hierarchy cannot contain a cycle",
            )
        if current.id in visited:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Existing task hierarchy is invalid",
            )
        visited.add(current.id)
        if current.parent_id is None:
            current = None
        else:
            current = await get_owned_task(db, owner_id, current.parent_id)
    return parent


async def resolve_container_defaults(
    db: AsyncSession,
    owner_id: UUID,
    module: Task,
) -> tuple[int | None, str | None, time | None]:
    """Resolve new-task defaults with module values taking priority over project values."""

    project = (
        await get_owned_task(db, owner_id, module.parent_id)
        if module.parent_id is not None
        else None
    )
    estimated = module.default_estimated_seconds
    repeat_rule = module.default_repeat_rule
    reminder = module.default_daily_reminder_time
    if project is not None:
        if estimated is None:
            estimated = project.default_estimated_seconds
        if repeat_rule is None:
            repeat_rule = project.default_repeat_rule
        if reminder is None:
            reminder = project.default_daily_reminder_time
    return estimated, repeat_rule, reminder


def collect_subtree_ids(tasks: Sequence[Task], root_id: UUID) -> set[UUID]:
    """Collect a subtree from an owner-filtered task list."""

    children_by_parent: dict[UUID | None, list[UUID]] = {}
    for task in tasks:
        children_by_parent.setdefault(task.parent_id, []).append(task.id)

    result: set[UUID] = set()
    pending = [root_id]
    while pending:
        current_id = pending.pop()
        if current_id in result:
            continue
        result.add(current_id)
        pending.extend(children_by_parent.get(current_id, []))
    return result
