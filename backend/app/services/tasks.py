"""Task-tree validation and budget-calculation helpers."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, time
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, SessionStatus
from app.models.task import Task, TaskBudgetMode, TaskDependency, TaskNodeType, TaskStatus
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
    is_leaf: bool | None = None,
    dependency_ids: Sequence[UUID] = (),
) -> TaskResponse:
    """Build a response from server-owned hierarchy and budget summaries."""

    ratio = actual_seconds / planned_seconds if planned_seconds > 0 else None
    return TaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        parent_id=task.parent_id,
        node_type=task.node_type,
        title=task.title,
        priority=task.priority,
        due_date=task.due_date,
        dependency_ids=list(dependency_ids),
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
        is_leaf=task.node_type == TaskNodeType.TASK if is_leaf is None else is_leaf,
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


def roll_up_task_time_totals(tasks: Sequence[Task], direct: dict[UUID, int]) -> dict[UUID, int]:
    """Roll database-aggregated direct seconds through the task hierarchy."""
    children: dict[UUID, list[UUID]] = {}
    for task in tasks:
        if task.parent_id is not None:
            children.setdefault(task.parent_id, []).append(task.id)
    totals: dict[UUID, int] = {}

    def visit(task_id: UUID, active: set[UUID]) -> int:
        if task_id in totals:
            return totals[task_id]
        if task_id in active:
            return direct.get(task_id, 0)
        total = direct.get(task_id, 0)
        for child_id in children.get(task_id, []):
            total += visit(child_id, {*active, task_id})
        totals[task_id] = total
        return total

    for task in tasks:
        visit(task.id, set())
    return totals


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
    session_result = await db.execute(
        select(Session.task_id, func.coalesce(func.sum(Session.duration_seconds), 0)).where(
            Session.owner_id == owner_id,
            Session.deleted_at.is_(None),
            Session.task_id.is_not(None),
        ).group_by(Session.task_id)
    )
    direct = {task.id: 0 for task in tasks}
    for task_id, seconds in session_result.all():
        if task_id in direct:
            direct[task_id] = int(seconds)
    running_sessions = list((await db.scalars(select(Session).where(
        Session.owner_id == owner_id,
        Session.deleted_at.is_(None),
        Session.status == SessionStatus.RUNNING,
        Session.last_resumed_at.is_not(None),
    ))).all())
    for session in running_sessions:
        if session.task_id in direct:
            direct[session.task_id] += (
                effective_session_duration(session) - session.duration_seconds
            )
    active_task_ids = {task.id for task in tasks}
    dependency_map: dict[UUID, list[UUID]] = {}
    if active_task_ids:
        dependency_result = await db.execute(
            select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
                TaskDependency.owner_id == owner_id,
                TaskDependency.task_id.in_(active_task_ids),
                TaskDependency.depends_on_task_id.in_(active_task_ids),
            )
        )
        for task_id, dependency_id in dependency_result.all():
            dependency_map.setdefault(task_id, []).append(dependency_id)
    parent_ids = {task.parent_id for task in tasks if task.parent_id is not None}
    totals = roll_up_task_time_totals(tasks, direct)
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
            is_leaf=task.id not in parent_ids,
            dependency_ids=dependency_map.get(task.id, ()),
        )
        for task in tasks
    ]


async def replace_task_dependencies(
    db: AsyncSession,
    owner_id: UUID,
    task_id: UUID,
    dependency_ids: Sequence[UUID],
) -> None:
    """Validate and replace a task's prerequisite edges without allowing cycles."""

    unique_ids = list(dict.fromkeys(dependency_ids))
    if task_id in unique_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task cannot depend on itself",
        )

    if unique_ids:
        owned_result = await db.scalars(
            select(Task.id).where(
                Task.owner_id == owner_id,
                Task.id.in_(unique_ids),
                Task.deleted_at.is_(None),
            )
        )
        owned_ids = set(owned_result.all())
        if owned_ids != set(unique_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dependency task not found",
            )

    edge_result = await db.execute(
        select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
            TaskDependency.owner_id == owner_id,
            TaskDependency.task_id != task_id,
        )
    )
    graph: dict[UUID, set[UUID]] = {}
    for source_id, dependency_id in edge_result.all():
        graph.setdefault(source_id, set()).add(dependency_id)
    graph[task_id] = set(unique_ids)

    def reaches(start_id: UUID, target_id: UUID) -> bool:
        pending = [start_id]
        visited: set[UUID] = set()
        while pending:
            current = pending.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(graph.get(current, ()))
        return False

    if any(reaches(dependency_id, task_id) for dependency_id in unique_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task dependencies cannot contain a cycle",
        )

    await db.execute(
        delete(TaskDependency).where(
            TaskDependency.owner_id == owner_id,
            TaskDependency.task_id == task_id,
        )
    )
    db.add_all(
        TaskDependency(
            owner_id=owner_id,
            task_id=task_id,
            depends_on_task_id=dependency_id,
        )
        for dependency_id in unique_ids
    )


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
    """Return an owned leaf node and reject containers that still have children.

    Explicit ``TASK`` nodes stay actionable while they have no children; once
    subtasks are added they act as containers and can no longer be timed or
    planned directly. An empty project or module is also directly actionable:
    this keeps the simple "create a project, add it to today" workflow useful
    without weakening the roll-up behavior once child tasks are added.
    """

    task = await get_owned_task(db, owner_id, task_id)
    if await has_active_children(db, owner_id, task.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only executable tasks can be timed or added to a daily plan",
        )
    return task


async def has_active_children(db: AsyncSession, owner_id: UUID, task_id: UUID) -> bool:
    """Whether the task still owns at least one non-deleted child node."""

    child_id = await db.scalar(
        select(Task.id)
        .where(
            Task.owner_id == owner_id,
            Task.parent_id == task_id,
            Task.deleted_at.is_(None),
        )
        .limit(1)
    )
    return child_id is not None


async def validate_parent(
    db: AsyncSession,
    owner_id: UUID,
    parent_id: UUID | None,
    node_type: TaskNodeType,
    task_id: UUID | None = None,
) -> Task | None:
    """Enforce PROJECT -> MODULE -> TASK (+ one subtask level) and prevent cycles."""

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
    if node_type == TaskNodeType.MODULE and parent.node_type != TaskNodeType.PROJECT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Module nodes must be placed under project nodes",
        )
    if node_type == TaskNodeType.TASK:
        if parent.node_type not in (TaskNodeType.PROJECT, TaskNodeType.MODULE, TaskNodeType.TASK):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task nodes must be placed under project, module or task nodes",
            )
        if parent.node_type == TaskNodeType.TASK:
            # Subtasks are allowed for exactly one extra level: the parent
            # task must itself sit directly under a project or module.
            if parent.parent_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Existing task hierarchy is invalid",
                )
            grandparent = await get_owned_task(db, owner_id, parent.parent_id)
            if grandparent.node_type == TaskNodeType.TASK:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Subtasks cannot contain further subtasks",
                )
            if task_id is not None and await has_active_children(db, owner_id, task_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only leaf tasks can become subtasks",
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
