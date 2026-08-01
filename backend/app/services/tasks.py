"""Task-tree validation and budget-calculation helpers."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, SessionStatus
from app.models.task import Task
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
    children_estimated_seconds: int = 0,
    is_leaf: bool = True,
) -> TaskResponse:
    """Build a task response from calculated direct and descendant totals."""

    ratio = actual_seconds / task.estimated_seconds if task.estimated_seconds > 0 else None
    return TaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        parent_id=task.parent_id,
        title=task.title,
        status=task.status,
        estimated_seconds=task.estimated_seconds,
        repeat_rule=task.repeat_rule,
        repeat_end_date=task.repeat_end_date,
        daily_reminder_time=task.daily_reminder_time,
        sort_order=task.sort_order,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        direct_actual_seconds=direct_actual_seconds,
        actual_seconds=actual_seconds,
        children_estimated_seconds=children_estimated_seconds,
        is_leaf=is_leaf,
        budget_usage_ratio=ratio,
        budget_level=calculate_budget_level(task.estimated_seconds, actual_seconds),
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


def calculate_children_budgets(
    tasks: Sequence[Task],
) -> tuple[dict[UUID, int], dict[UUID, bool]]:
    """Return children estimated_seconds sum and leaf status for every task."""
    children_map: dict[UUID, list[UUID]] = {}
    for task in tasks:
        if task.parent_id is not None:
            children_map.setdefault(task.parent_id, []).append(task.id)
    
    is_leaf = {task.id: task.id not in children_map for task in tasks}
    
    task_by_id = {task.id: task for task in tasks}
    budget_totals: dict[UUID, int] = {}
    
    def visit(task_id: UUID) -> int:
        if task_id in budget_totals:
            return budget_totals[task_id]
        total = 0
        for child_id in children_map.get(task_id, []):
            child = task_by_id.get(child_id)
            if child:
                child_children_sum = visit(child_id)
                total += child.estimated_seconds if is_leaf[child_id] else child_children_sum
        budget_totals[task_id] = total
        return total
    
    for task in tasks:
        visit(task.id)
    
    return budget_totals, is_leaf


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
    children_estimated, is_leaf = calculate_children_budgets(tasks)
    return [
        to_task_response(
            task,
            actual_seconds=totals.get(task.id, 0),
            direct_actual_seconds=direct.get(task.id, 0),
            children_estimated_seconds=children_estimated.get(task.id, 0),
            is_leaf=is_leaf.get(task.id, True),
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


async def validate_parent(
    db: AsyncSession,
    owner_id: UUID,
    parent_id: UUID | None,
    task_id: UUID | None = None,
) -> Task | None:
    """Ensure a parent exists, belongs to the owner and does not form a cycle."""

    if parent_id is None:
        return None
    if task_id is not None and parent_id == task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task cannot be its own parent",
        )

    parent = await get_owned_task(db, owner_id, parent_id)
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
