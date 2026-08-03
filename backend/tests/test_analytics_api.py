"""Date-range learning analytics API tests."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient

from tests.test_daily_plans_api import add_item, create_plan
from tests.test_sessions_api import create_task, snapshot
from tests.test_tasks_api import auth_header, register_user


async def test_analytics_aggregates_time_completion_and_budget(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client)
    today = date.today()
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
    assert data["total_task_count"] == 1


async def test_analytics_validates_range_and_isolates_owners(
    client: AsyncClient,
) -> None:
    first_token, _ = await register_user(client, "first")
    second_token, _ = await register_user(client, "second")
    today = date.today()
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
    assert reversed_range.status_code == 422
