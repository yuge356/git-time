"""Date-range learning analytics API tests."""

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

from httpx import AsyncClient

from tests.conftest import profile_today
from tests.test_daily_plans_api import add_item, create_plan
from tests.test_sessions_api import create_task, snapshot
from tests.test_tasks_api import auth_header, register_user


async def test_analytics_aggregates_time_completion_and_budget(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client)
    today = profile_today()
    child_id = await create_task(client, token, "Lesson")
    plan = await create_plan(client, token, today)
    item = await add_item(client, token, plan["id"], task_id=child_id)
    started = datetime.now(UTC)
    ended = started + timedelta(minutes=30)
    completed = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json={
            **snapshot(
                child_id,
                str(uuid4()),
                "COMPLETED",
                started,
                ended,
                1_800,
                ended_at=ended,
            ),
            "daily_plan_item_id": item["id"],
        },
    )
    assert completed.status_code == 200

    refreshed_plan = await client.get(
        f"/api/v1/daily-plans/by-date/{today.isoformat()}",
        headers=auth_header(token),
    )
    assert refreshed_plan.status_code == 200
    refreshed_item = refreshed_plan.json()["items"][0]
    assert refreshed_item["status"] == "DONE"
    assert refreshed_item["actual_seconds"] == 1_800
    assert refreshed_plan.json()["completed_items"] == 1

    response = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(token),
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_learning_seconds"] == 1_800
    assert data["completed_session_count"] == 1
    assert data["daily_trend"][0]["completed_items"] == 1
    assert data["task_distribution"][0]["task_id"] == child_id
    budgets = {item["task_id"]: item for item in data["budget_comparison"]}
    assert budgets[child_id]["actual_seconds"] == 1_800
    assert len(data["project_history"]) == 1
    project_history = data["project_history"][0]
    assert project_history["title"] == "Lesson project"
    assert project_history["seconds"] == 1_800
    assert project_history["session_count"] == 1
    assert project_history["task_count"] == 1
    assert project_history["last_tracked_at"]
    assert data["completed_task_count"] == 1
    assert data["total_task_count"] == 1


async def test_analytics_task_completion_follows_daily_items_in_range(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "daily_item_analytics")
    today = profile_today()
    yesterday = today - timedelta(days=1)
    task_id = await create_task(client, token, "Recurring project task")

    old_plan = await create_plan(client, token, yesterday)
    old_item = await add_item(client, token, old_plan["id"], task_id=task_id)
    old_done = await client.patch(
        f"/api/v1/daily-plan-items/{old_item['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert old_done.status_code == 200

    today_plan = await create_plan(client, token, today)
    linked_item = await add_item(client, token, today_plan["id"], task_id=task_id)
    ad_hoc_item = await add_item(client, token, today_plan["id"], title="Inbox task")

    before = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(token),
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
    )
    assert before.status_code == 200
    assert before.json()["completed_task_count"] == 0
    assert before.json()["total_task_count"] == 2

    for item in (linked_item, ad_hoc_item):
        completed = await client.patch(
            f"/api/v1/daily-plan-items/{item['id']}",
            headers=auth_header(token),
            json={"status": "DONE"},
        )
        assert completed.status_code == 200

    after = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(token),
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
    )
    assert after.status_code == 200
    assert after.json()["completed_task_count"] == 2
    assert after.json()["total_task_count"] == 2
    assert after.json()["daily_trend"][0]["completed_items"] == 2

    # Reopening a Today item must update both the Today page and analytics
    # instead of leaving a stale historical completion in the headline card.
    reopened = await client.patch(
        f"/api/v1/daily-plan-items/{linked_item['id']}",
        headers=auth_header(token),
        json={"status": "TODO"},
    )
    assert reopened.status_code == 200

    refreshed = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(token),
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["completed_task_count"] == 1
    assert refreshed.json()["total_task_count"] == 2

    old_range = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(token),
        params={
            "date_from": yesterday.isoformat(),
            "date_to": yesterday.isoformat(),
        },
    )
    assert old_range.status_code == 200
    assert old_range.json()["completed_task_count"] == 1
    assert old_range.json()["total_task_count"] == 1


async def test_analytics_validates_range_and_isolates_owners(
    client: AsyncClient,
) -> None:
    first_token, _ = await register_user(client, "first")
    second_token, _ = await register_user(client, "second")
    today = profile_today()
    task_id = await create_task(client, first_token, "Private work")
    started = datetime.now(UTC)
    ended = started + timedelta(minutes=5)
    await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(first_token),
        json=snapshot(
            task_id,
            str(uuid4()),
            "COMPLETED",
            started,
            ended,
            300,
            ended_at=ended,
        ),
    )

    isolated = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(second_token),
        params={"date_from": today.isoformat(), "date_to": today.isoformat()},
    )
    reversed_range = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(first_token),
        params={
            "date_from": today.isoformat(),
            "date_to": (today - timedelta(days=1)).isoformat(),
        },
    )
    assert isolated.status_code == 200
    assert isolated.json()["total_learning_seconds"] == 0
    assert isolated.json()["project_history"] == []
    assert reversed_range.status_code == 422


async def test_hourly_focus_buckets_sessions_by_start_hour(
    client: AsyncClient,
) -> None:
    from zoneinfo import ZoneInfo

    token, _ = await register_user(client, "hourly")
    today = profile_today()
    task_id = await create_task(client, token, "Hourly lesson")

    # New profiles default to Asia/Shanghai; build sessions on that local day.
    local_tz = ZoneInfo("Asia/Shanghai")
    morning = datetime.combine(today, time(9, 0), tzinfo=local_tz).astimezone(UTC)
    evening = datetime.combine(today, time(21, 30), tzinfo=local_tz).astimezone(UTC)
    for started, duration in ((morning, 1_200), (evening, 1_800)):
        response = await client.put(
            f"/api/v1/sessions/{uuid4()}",
            headers=auth_header(token),
            json=snapshot(
                task_id,
                str(uuid4()),
                "COMPLETED",
                started,
                started + timedelta(seconds=duration),
                duration,
                ended_at=started + timedelta(seconds=duration),
            ),
        )
        assert response.status_code == 200

    hourly = await client.get(
        "/api/v1/analytics/hourly-focus",
        headers=auth_header(token),
        params={"day": today.isoformat()},
    )
    assert hourly.status_code == 200
    data = hourly.json()
    assert data["date"] == today.isoformat()
    assert data["total_seconds"] == 3_000
    hours = {point["hour"]: point["seconds"] for point in data["hours"]}
    assert len(hours) == 24
    assert hours[9] == 1_200
    assert hours[21] == 1_800
    assert sum(hours.values()) == data["total_seconds"]

    empty = await client.get(
        "/api/v1/analytics/hourly-focus",
        headers=auth_header(token),
        params={"day": (today - timedelta(days=1)).isoformat()},
    )
    assert empty.status_code == 200
    assert empty.json()["total_seconds"] == 0


async def test_task_daily_series_buckets_seconds_per_task_and_day(
    client: AsyncClient,
) -> None:
    from zoneinfo import ZoneInfo

    token, _ = await register_user(client, "gantt")
    today = profile_today()
    yesterday = today - timedelta(days=1)
    task_id = await create_task(client, token, "Gantt lesson")

    # New profiles default to Asia/Shanghai; build sessions on local days.
    local_tz = ZoneInfo("Asia/Shanghai")
    for day, hour, duration in ((yesterday, 10, 900), (today, 15, 600)):
        started = datetime.combine(day, time(hour, 0), tzinfo=local_tz).astimezone(UTC)
        response = await client.put(
            f"/api/v1/sessions/{uuid4()}",
            headers=auth_header(token),
            json=snapshot(
                task_id,
                str(uuid4()),
                "COMPLETED",
                started,
                started + timedelta(seconds=duration),
                duration,
                ended_at=started + timedelta(seconds=duration),
            ),
        )
        assert response.status_code == 200

    series_response = await client.get(
        "/api/v1/analytics/task-daily",
        headers=auth_header(token),
        params={
            "date_from": (today - timedelta(days=6)).isoformat(),
            "date_to": today.isoformat(),
        },
    )
    assert series_response.status_code == 200
    data = series_response.json()
    assert data["tasks"] != []
    series = data["tasks"][0]
    assert series["task_id"] == task_id
    assert series["title"] == "Gantt lesson"
    assert series["total_seconds"] == 1_500
    daily = {point["date"]: point["seconds"] for point in series["daily"]}
    assert daily == {
        yesterday.isoformat(): 900,
        today.isoformat(): 600,
    }

    other_token, _ = await register_user(client, "ganttsecond")
    isolated = await client.get(
        "/api/v1/analytics/task-daily",
        headers=auth_header(other_token),
        params={"date_from": (today - timedelta(days=6)).isoformat(), "date_to": today.isoformat()},
    )
    assert isolated.status_code == 200
    assert isolated.json()["tasks"] == []

    reversed_range = await client.get(
        "/api/v1/analytics/task-daily",
        headers=auth_header(token),
        params={"date_from": today.isoformat(), "date_to": yesterday.isoformat()},
    )
    assert reversed_range.status_code == 422


async def test_today_overview_matches_the_separate_endpoints(client: AsyncClient) -> None:
    """One bundled request returns exactly what three requests returned."""

    from zoneinfo import ZoneInfo

    token, _ = await register_user(client, "today_overview")
    today = profile_today()
    yesterday = today - timedelta(days=1)
    task_id = await create_task(client, token, "Overview lesson")
    plan = await create_plan(client, token, today)
    item = await add_item(client, token, plan["id"], task_id=task_id)
    done = await client.patch(
        f"/api/v1/daily-plan-items/{item['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert done.status_code == 200

    local_tz = ZoneInfo("Asia/Shanghai")
    for day, hour, duration in ((yesterday, 10, 900), (today, 15, 600)):
        started = datetime.combine(day, time(hour, 0), tzinfo=local_tz).astimezone(UTC)
        response = await client.put(
            f"/api/v1/sessions/{uuid4()}",
            headers=auth_header(token),
            json=snapshot(
                task_id,
                str(uuid4()),
                "COMPLETED",
                started,
                started + timedelta(seconds=duration),
                duration,
                ended_at=started + timedelta(seconds=duration),
            ),
        )
        assert response.status_code == 200

    calendar_from = today.replace(day=1)
    gantt_from = today - timedelta(days=30)
    overview = await client.get(
        "/api/v1/analytics/today-overview",
        headers=auth_header(token),
        params={
            "calendar_from": calendar_from.isoformat(),
            "calendar_to": today.isoformat(),
            "focus_day": today.isoformat(),
            "gantt_from": gantt_from.isoformat(),
            "gantt_to": today.isoformat(),
        },
    )
    assert overview.status_code == 200
    body = overview.json()

    summary = await client.get(
        "/api/v1/analytics/summary",
        headers=auth_header(token),
        params={"date_from": calendar_from.isoformat(), "date_to": today.isoformat()},
    )
    hourly = await client.get(
        "/api/v1/analytics/hourly-focus",
        headers=auth_header(token),
        params={"day": today.isoformat()},
    )
    task_daily = await client.get(
        "/api/v1/analytics/task-daily",
        headers=auth_header(token),
        params={"date_from": gantt_from.isoformat(), "date_to": today.isoformat()},
    )
    assert body["calendar_trend"] == summary.json()["daily_trend"]
    assert body["hourly_focus"] == hourly.json()
    assert body["task_daily"] == task_daily.json()


async def test_today_overview_rejects_reversed_ranges(client: AsyncClient) -> None:
    token, _ = await register_user(client, "today_overview_range")
    today = profile_today()

    response = await client.get(
        "/api/v1/analytics/today-overview",
        headers=auth_header(token),
        params={
            "calendar_from": today.isoformat(),
            "calendar_to": (today - timedelta(days=1)).isoformat(),
            "focus_day": today.isoformat(),
            "gantt_from": (today - timedelta(days=7)).isoformat(),
            "gantt_to": today.isoformat(),
        },
    )
    assert response.status_code == 422
