"""Daily planning, ad-hoc timer and check-in API tests."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_plan import DailyPlanItem
from tests.conftest import profile_today
from tests.test_sessions_api import create_task
from tests.test_tasks_api import auth_header, create_structured_task, register_user


async def create_plan(client: AsyncClient, token: str, plan_date: date) -> dict:
    """Create and return a daily plan fixture."""

    response = await client.post(
        "/api/v1/daily-plans",
        headers=auth_header(token),
        json={"plan_date": plan_date.isoformat()},
    )
    assert response.status_code == 201
    return response.json()


async def add_item(
    client: AsyncClient,
    token: str,
    plan_id: str,
    *,
    title: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Append one linked or ad-hoc item."""

    response = await client.post(
        f"/api/v1/daily-plans/{plan_id}/items",
        headers=auth_header(token),
        json={"title": title, "task_id": task_id, "estimated_seconds": 1_800},
    )
    assert response.status_code == 201
    return response.json()


async def test_empty_project_can_be_planned_timed_and_reported(client: AsyncClient) -> None:
    """A newly created project is actionable until child tasks are added."""

    token, _ = await register_user(client, "empty_project_today")
    project = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "直接执行的项目", "node_type": "PROJECT"},
    )
    assert project.status_code == 201
    assert project.json()["is_leaf"] is True

    plan = await create_plan(client, token, profile_today())
    item = await add_item(
        client,
        token,
        plan["id"],
        task_id=project.json()["id"],
    )
    assert item["title"] == "直接执行的项目"
    assert item["task_id"] == project.json()["id"]

    started = datetime.now(UTC)
    ended = started + timedelta(minutes=5)
    timed = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json={
            "task_id": project.json()["id"],
            "daily_plan_item_id": item["id"],
            "client_id": str(uuid4()),
            "status": "COMPLETED",
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_seconds": 300,
            "last_resumed_at": None,
            "client_updated_at": ended.isoformat(),
        },
    )
    assert timed.status_code == 200

    refreshed = await client.get(
        f"/api/v1/tasks/{project.json()['id']}",
        headers=auth_header(token),
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["direct_actual_seconds"] == 300
    assert refreshed.json()["actual_seconds"] == 300


async def test_daily_plan_items_progress_time_and_streak(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    today = profile_today()
    yesterday = today - timedelta(days=1)
    task_id = await create_task(client, token, "Long-term task")

    old_plan = await create_plan(client, token, yesterday)
    old_item = await add_item(client, token, old_plan["id"], title="Review")
    old_done = await client.patch(
        f"/api/v1/daily-plan-items/{old_item['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert old_done.status_code == 200
    assert old_done.json()["completed_at"] is not None

    plan = await create_plan(client, token, today)
    linked = await add_item(client, token, plan["id"], task_id=task_id)
    ad_hoc = await add_item(client, token, plan["id"], title="Read notes")
    assert linked["title"] == "Long-term task project/Long-term task"
    assert linked["task_id"] == task_id
    assert ad_hoc["task_id"] is None

    done = await client.patch(
        f"/api/v1/daily-plan-items/{ad_hoc['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert done.status_code == 200

    started = datetime.now(UTC)
    ended = started + timedelta(minutes=12)
    session = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json={
            "task_id": None,
            "daily_plan_item_id": ad_hoc["id"],
            "client_id": str(uuid4()),
            "status": "COMPLETED",
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_seconds": 720,
            "last_resumed_at": None,
            "client_updated_at": ended.isoformat(),
        },
    )
    assert session.status_code == 200

    read = await client.get(
        f"/api/v1/daily-plans/by-date/{today.isoformat()}",
        headers=auth_header(token),
    )
    assert read.status_code == 200
    data = read.json()
    assert data["total_items"] == 2
    assert data["completed_items"] == 1
    assert data["completion_rate"] == 0.5
    assert data["actual_seconds"] == 720

    check_in = await client.get(
        f"/api/v1/check-ins/{today.isoformat()}",
        headers=auth_header(token),
    )
    assert check_in.status_code == 200
    assert check_in.json() == {
        "plan_date": today.isoformat(),
        "learning_seconds": 720,
        "completed_items": 1,
        "total_items": 2,
        "streak_days": 2,
    }


async def test_daily_plan_uniqueness_and_owner_isolation(client: AsyncClient) -> None:
    first_token, _ = await register_user(client, "first")
    second_token, _ = await register_user(client, "second")
    today = profile_today()
    plan = await create_plan(client, first_token, today)
    item = await add_item(client, first_token, plan["id"], title="Private")

    duplicate = await client.post(
        "/api/v1/daily-plans",
        headers=auth_header(first_token),
        json={"plan_date": today.isoformat()},
    )
    private_read = await client.get(
        f"/api/v1/daily-plans/by-date/{today.isoformat()}",
        headers=auth_header(second_token),
    )
    private_update = await client.patch(
        f"/api/v1/daily-plan-items/{item['id']}",
        headers=auth_header(second_token),
        json={"status": "DONE"},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == plan["id"]
    assert private_read.status_code == 404
    assert private_update.status_code == 404


async def test_active_daily_item_timer_blocks_item_deletion(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    plan = await create_plan(client, token, profile_today())
    item = await add_item(client, token, plan["id"], title="Focused reading")
    started = datetime.now(UTC)
    session = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json={
            "task_id": None,
            "daily_plan_item_id": item["id"],
            "client_id": str(uuid4()),
            "status": "RUNNING",
            "started_at": started.isoformat(),
            "ended_at": None,
            "duration_seconds": 0,
            "last_resumed_at": started.isoformat(),
            "client_updated_at": started.isoformat(),
        },
    )
    assert session.status_code == 200

    deleted = await client.delete(
        f"/api/v1/daily-plan-items/{item['id']}",
        headers=auth_header(token),
    )
    assert deleted.status_code == 409


async def test_client_generated_daily_item_id_is_idempotent(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "stable_daily_item")
    plan = await create_plan(client, token, profile_today())
    item_id = str(uuid4())
    payload = {
        "id": item_id,
        "title": "Offline-created item",
        "task_id": None,
        "estimated_seconds": 900,
    }
    first = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/items",
        headers=auth_header(token),
        json=payload,
    )
    replay = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/items",
        headers=auth_header(token),
        json=payload,
    )
    reloaded = await client.get(
        f"/api/v1/daily-plans/by-date/{profile_today().isoformat()}",
        headers=auth_header(token),
    )
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == item_id
    assert reloaded.status_code == 200
    assert [item["id"] for item in reloaded.json()["items"]] == [item_id]


async def test_auto_populate_adds_due_project_tasks_once(client: AsyncClient) -> None:
    token, _ = await register_user(client, "auto_populate")
    today = profile_today()
    yesterday = today - timedelta(days=1)

    _, module, _ = await create_structured_task(client, token, "占位")
    child = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "每日子任务",
            "node_type": "TASK",
            "parent_id": module["id"],
            "repeat_rule": "DAILY",
            "estimated_seconds": 900,
        },
    )
    assert child.status_code == 201
    expired = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "已截止任务",
            "node_type": "TASK",
            "parent_id": module["id"],
            "repeat_rule": "DAILY",
            "repeat_end_date": yesterday.isoformat(),
        },
    )
    assert expired.status_code == 201

    plan = await create_plan(client, token, today)
    first = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/auto-populate",
        headers=auth_header(token),
    )
    replay = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/auto-populate",
        headers=auth_header(token),
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert {item["title"] for item in first.json()["items"]} == {
        "占位 project/每日子任务"
    }
    assert {item["id"] for item in replay.json()["items"]} == {
        item["id"] for item in first.json()["items"]
    }


async def test_new_day_keeps_only_due_recurring_tasks(client: AsyncClient) -> None:
    token, _ = await register_user(client, "daily_refresh")
    today = profile_today()
    tomorrow = today + timedelta(days=1)
    ordinary_task_id = await create_task(client, token, "One day only")
    recurring_task_id = await create_task(client, token, "Repeat daily")
    updated = await client.patch(
        f"/api/v1/tasks/{recurring_task_id}",
        headers=auth_header(token),
        json={"repeat_rule": "DAILY"},
    )
    assert updated.status_code == 200

    today_plan = await create_plan(client, token, today)
    ordinary_item = await add_item(
        client,
        token,
        today_plan["id"],
        task_id=ordinary_task_id,
    )
    recurring_item = await add_item(
        client,
        token,
        today_plan["id"],
        task_id=recurring_task_id,
    )

    tomorrow_plan = await create_plan(client, token, tomorrow)
    refreshed = await client.post(
        f"/api/v1/daily-plans/{tomorrow_plan['id']}/auto-populate",
        headers=auth_header(token),
    )

    assert refreshed.status_code == 200
    assert [item["task_id"] for item in refreshed.json()["items"]] == [
        recurring_task_id
    ]
    assert refreshed.json()["items"][0]["id"] not in {
        ordinary_item["id"],
        recurring_item["id"],
    }


async def test_completed_project_keeps_existing_today_item(client: AsyncClient) -> None:
    token, _ = await register_user(client, "keep_done_item")
    today = profile_today()
    _, _, task = await create_structured_task(
        client,
        token,
        "今天已安排的项目任务",
    )
    recurring = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=auth_header(token),
        json={"repeat_rule": "DAILY", "estimated_seconds": 1_800},
    )
    assert recurring.status_code == 200
    plan = await create_plan(client, token, today)
    populated = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/auto-populate",
        headers=auth_header(token),
    )
    assert populated.status_code == 200
    item_id = populated.json()["items"][0]["id"]

    completed = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert completed.status_code == 200

    reopened = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/auto-populate",
        headers=auth_header(token),
    )
    assert reopened.status_code == 200
    assert [item["id"] for item in reopened.json()["items"]] == [item_id]
    assert reopened.json()["items"][0]["title"] == (
        "今天已安排的项目任务 project/今天已安排的项目任务"
    )


async def test_auto_populate_adds_scheduled_and_due_tasks(client: AsyncClient) -> None:
    """A task scheduled on the projects page lands in that day's plan."""

    token, _ = await register_user(client, "scheduled_today")
    today = profile_today()
    _, module, _ = await create_structured_task(client, token, "排期")

    due_today = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "今天截止",
            "node_type": "TASK",
            "parent_id": module["id"],
            "due_date": today.isoformat(),
            "estimated_seconds": 900,
        },
    )
    planned_window = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "本周排期",
            "node_type": "TASK",
            "parent_id": module["id"],
            "planned_start_date": (today - timedelta(days=1)).isoformat(),
            "planned_end_date": (today + timedelta(days=2)).isoformat(),
            "estimated_seconds": 1_800,
        },
    )
    unscheduled = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "还没排期",
            "node_type": "TASK",
            "parent_id": module["id"],
            "estimated_seconds": 600,
        },
    )
    assert due_today.status_code == 201
    assert planned_window.status_code == 201
    assert unscheduled.status_code == 201

    plan = await create_plan(client, token, today)
    populated = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/auto-populate",
        headers=auth_header(token),
    )
    assert populated.status_code == 200
    assert {item["task_id"] for item in populated.json()["items"]} == {
        due_today.json()["id"],
        planned_window.json()["id"],
    }


async def test_auto_populate_skips_tasks_that_own_subtasks(client: AsyncClient) -> None:
    """A task with subtasks is a container and can never be timed."""

    token, _ = await register_user(client, "scheduled_container")
    today = profile_today()
    _, module, parent_task = await create_structured_task(client, token, "容器")
    scheduled_parent = await client.patch(
        f"/api/v1/tasks/{parent_task['id']}",
        headers=auth_header(token),
        json={"due_date": today.isoformat()},
    )
    assert scheduled_parent.status_code == 200
    subtask = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "子任务",
            "node_type": "TASK",
            "parent_id": parent_task["id"],
            "due_date": today.isoformat(),
            "estimated_seconds": 600,
        },
    )
    assert subtask.status_code == 201

    plan = await create_plan(client, token, today)
    populated = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/auto-populate",
        headers=auth_header(token),
    )
    assert populated.status_code == 200
    assert [item["task_id"] for item in populated.json()["items"]] == [
        subtask.json()["id"]
    ]


async def test_scheduled_task_enters_the_day_only_once(client: AsyncClient) -> None:
    """A client import of an already auto-populated task reuses its item."""

    token, _ = await register_user(client, "one_item_per_task")
    _, _, task = await create_structured_task(client, token, "只出现一次")
    today = profile_today()
    assert (
        await client.patch(
            f"/api/v1/tasks/{task['id']}",
            headers=auth_header(token),
            json={"due_date": today.isoformat()},
        )
    ).status_code == 200

    opened = await client.post(
        "/api/v1/daily-plans/open",
        headers=auth_header(token),
        json={"plan_date": today.isoformat()},
    )
    assert opened.status_code == 200
    plan = opened.json()["plan"]
    auto_item_id = next(
        item["id"] for item in plan["items"] if item["task_id"] == task["id"]
    )

    # The browser imports newly scheduled tasks with an id of its own. That
    # write must land on the existing item instead of listing the task twice.
    imported = await client.post(
        f"/api/v1/daily-plans/{plan['id']}/items",
        headers=auth_header(token),
        json={
            "id": str(uuid4()),
            "task_id": task["id"],
            "title": "只出现一次",
            "estimated_seconds": 1_800,
        },
    )
    assert imported.status_code == 201
    assert imported.json()["id"] == auto_item_id

    reopened = await client.post(
        "/api/v1/daily-plans/open",
        headers=auth_header(token),
        json={"plan_date": today.isoformat()},
    )
    assert reopened.status_code == 200
    items = [
        item
        for item in reopened.json()["plan"]["items"]
        if item["task_id"] == task["id"]
    ]
    assert [item["id"] for item in items] == [auto_item_id]


async def test_opening_a_day_collapses_duplicate_task_items(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Duplicates left by earlier releases disappear, keeping the timed one."""

    token, _ = await register_user(client, "collapse_duplicates")
    _, _, task = await create_structured_task(client, token, "重复条目")
    today = profile_today()
    plan = await create_plan(client, token, today)
    kept = await add_item(client, token, plan["id"], task_id=task["id"])

    # Stage the duplicate the old race produced: the same task, a second id.
    stray_id = uuid4()
    db_session.add(
        DailyPlanItem(
            id=stray_id,
            daily_plan_id=UUID(plan["id"]),
            owner_id=UUID(kept["owner_id"]),
            task_id=UUID(task["id"]),
            title="重复条目",
            estimated_seconds=1_800,
            sort_order=9,
            created_at=datetime.fromisoformat(kept["created_at"]),
        )
    )
    await db_session.commit()

    before = await client.get(
        f"/api/v1/daily-plans/by-date/{today.isoformat()}",
        headers=auth_header(token),
    )
    assert {item["id"] for item in before.json()["items"]} == {
        kept["id"],
        str(stray_id),
    }

    opened = await client.post(
        "/api/v1/daily-plans/open",
        headers=auth_header(token),
        json={"plan_date": today.isoformat()},
    )
    assert opened.status_code == 200
    assert [item["id"] for item in opened.json()["plan"]["items"]] == [kept["id"]]
