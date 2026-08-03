"""Calendar rules used to place recurring project tasks on daily plans."""

from datetime import UTC, date, datetime
from uuid import uuid4

from app.models.task import Task, TaskRepeatRule, TaskStatus
from app.services.daily_plans import task_repeats_on_date


def recurring_task(
    rule: TaskRepeatRule,
    *,
    created_at: datetime | None = None,
    repeat_end_date: date | None = None,
    status: TaskStatus = TaskStatus.TODO,
) -> Task:
    timestamp = created_at or datetime(2026, 1, 31, 8, tzinfo=UTC)
    task = Task(
        owner_id=uuid4(),
        title="Recurring task",
        status=status,
        estimated_seconds=600,
        repeat_rule=rule,
        repeat_end_date=repeat_end_date,
        sort_order=0,
    )
    task.created_at = timestamp
    task.updated_at = timestamp
    return task


def test_daily_and_weekday_rules() -> None:
    daily = recurring_task(TaskRepeatRule.DAILY)
    weekdays = recurring_task(TaskRepeatRule.WEEKDAYS)

    assert task_repeats_on_date(daily, date(2026, 2, 1))
    assert task_repeats_on_date(weekdays, date(2026, 2, 2))
    assert not task_repeats_on_date(weekdays, date(2026, 2, 1))


def test_weekly_rule_uses_the_creation_weekday() -> None:
    weekly = recurring_task(TaskRepeatRule.WEEKLY)

    assert task_repeats_on_date(weekly, date(2026, 2, 7))
    assert not task_repeats_on_date(weekly, date(2026, 2, 6))


def test_monthly_rule_clamps_to_the_last_day_of_short_months() -> None:
    monthly = recurring_task(TaskRepeatRule.MONTHLY)

    assert task_repeats_on_date(monthly, date(2026, 2, 28))
    assert task_repeats_on_date(monthly, date(2026, 3, 31))
    assert not task_repeats_on_date(monthly, date(2026, 2, 27))


def test_recurrence_respects_start_end_and_done_status() -> None:
    ended = recurring_task(TaskRepeatRule.DAILY, repeat_end_date=date(2026, 2, 2))
    done = recurring_task(TaskRepeatRule.DAILY, status=TaskStatus.DONE)

    assert not task_repeats_on_date(ended, date(2026, 1, 30))
    assert task_repeats_on_date(ended, date(2026, 2, 2))
    assert not task_repeats_on_date(ended, date(2026, 2, 3))
    assert not task_repeats_on_date(done, date(2026, 2, 1))
