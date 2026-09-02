"""Reliable session state, idempotency and task aggregation API tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient

from tests.conftest import profile_today
from tests.test_tasks_api import auth_header, create_structured_task, register_user


async def create_task(
    client: AsyncClient,
    token: str,
    title: str,
) -> str:
    project = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": f"{title} project", "node_type": "PROJECT"},
    )
    assert project.status_code == 201
    module = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": f"{title} module",
            "node_type": "MODULE",
            "parent_id": project.json()["id"],
        },
    )
    assert module.status_code == 201
    task = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": title,
            "node_type": "TASK",
            "parent_id": module.json()["id"],
            "estimated_seconds": 3_600,
        },
    )
    assert task.status_code == 201
    return task.json()["id"]


def snapshot(
    task_id: str,
    client_id: str,
    status: str,
    started_at: datetime,
    updated_at: datetime,
    duration_seconds: int,
    *,
    last_resumed_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "client_id": client_id,
        "status": status,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat() if ended_at else None,
        "duration_seconds": duration_seconds,
        "last_resumed_at": last_resumed_at.isoformat() if last_resumed_at else None,
        "client_updated_at": updated_at.isoformat(),
    }


async def test_start_pause_resume_and_finish_session(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    task_id = await create_task(client, token, "计时任务")
    session_id = str(uuid4())
    client_id = str(uuid4())
    started = datetime.now(UTC)

    running = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=snapshot(
            task_id,
            client_id,
            "RUNNING",
            started,
            started,
            0,
            last_resumed_at=started,
        ),
    )
    assert running.status_code == 200
    assert running.json()["status"] == "RUNNING"

    paused_at = started + timedelta(minutes=10)
    paused = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=snapshot(
            task_id,
            client_id,
            "PAUSED",
            started,
            paused_at,
            600,
        ),
    )
    assert paused.status_code == 200
    assert paused.json()["duration_seconds"] == 600

    resumed_at = paused_at + timedelta(minutes=1)
    resumed = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=snapshot(
            task_id,
            client_id,
            "RUNNING",
            started,
            resumed_at,
            600,
            last_resumed_at=resumed_at,
        ),
    )
    assert resumed.status_code == 200

    ended_at = resumed_at + timedelta(minutes=10)
    completed = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=snapshot(
            task_id,
            client_id,
            "COMPLETED",
            started,
            ended_at,
            1_200,
            ended_at=ended_at,
        ),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"

    active = await client.get("/api/v1/sessions/active", headers=auth_header(token))
    history = await client.get("/api/v1/sessions", headers=auth_header(token))
    assert active.status_code == 200
    assert active.json() is None
    assert history.json()[0]["id"] == session_id


async def test_session_put_is_allowed_by_cors(client: AsyncClient) -> None:
    response = await client.options(
        f"/api/v1/sessions/{uuid4()}",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


async def test_stale_offline_snapshot_is_idempotently_ignored(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    task_id = await create_task(client, token, "离线任务")
    session_id = str(uuid4())
    client_id = str(uuid4())
    started = datetime.now(UTC)

    initial = snapshot(
        task_id,
        client_id,
        "RUNNING",
        started,
        started,
        0,
        last_resumed_at=started,
    )
    await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=initial,
    )
    paused_at = started + timedelta(minutes=5)
    await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=snapshot(task_id, client_id, "PAUSED", started, paused_at, 300),
    )

    replay = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=initial,
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "PAUSED"
    assert replay.json()["duration_seconds"] == 300


async def test_only_one_active_session_is_allowed(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    first_task = await create_task(client, token, "任务一")
    second_task = await create_task(client, token, "任务二")
    started = datetime.now(UTC)

    first = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json=snapshot(
            first_task,
            str(uuid4()),
            "RUNNING",
            started,
            started,
            0,
            last_resumed_at=started,
        ),
    )
    second = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json=snapshot(
            second_task,
            str(uuid4()),
            "RUNNING",
            started,
            started,
            0,
            last_resumed_at=started,
        ),
    )

    assert first.status_code == 200
    assert second.status_code == 409


async def test_switching_from_paused_timer_keeps_previous_daily_item_open(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "switch_paused")
    first_task = await create_task(client, token, "任务一")
    second_task = await create_task(client, token, "任务二")
    plan = await client.post(
        "/api/v1/daily-plans",
        headers=auth_header(token),
        json={"plan_date": profile_today().isoformat()},
    )
    assert plan.status_code == 201
    item = await client.post(
        f"/api/v1/daily-plans/{plan.json()['id']}/items",
        headers=auth_header(token),
        json={"task_id": first_task, "estimated_seconds": 1_800},
    )
    assert item.status_code == 201
    item_id = item.json()["id"]
    await client.patch(
        f"/api/v1/daily-plan-items/{item_id}",
        headers=auth_header(token),
        json={"status": "IN_PROGRESS"},
    )

    session_id = str(uuid4())
    client_id = str(uuid4())
    started = datetime.now(UTC)
    paused_at = started + timedelta(minutes=10)
    running_payload = snapshot(
        first_task,
        client_id,
        "RUNNING",
        started,
        started,
        0,
        last_resumed_at=started,
    )
    running_payload["daily_plan_item_id"] = item_id
    paused_payload = snapshot(
        first_task,
        client_id,
        "PAUSED",
        started,
        paused_at,
        600,
    )
    paused_payload["daily_plan_item_id"] = item_id
    completed_payload = snapshot(
        first_task,
        client_id,
        "COMPLETED",
        started,
        paused_at + timedelta(seconds=1),
        600,
        ended_at=paused_at + timedelta(seconds=1),
    )
    completed_payload.update(
        {"daily_plan_item_id": item_id, "complete_daily_item": False}
    )

    assert (
        await client.put(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header(token),
            json=running_payload,
        )
    ).status_code == 200
    assert (
        await client.put(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header(token),
            json=paused_payload,
        )
    ).status_code == 200
    assert (
        await client.put(
            f"/api/v1/sessions/{session_id}",
            headers=auth_header(token),
            json=completed_payload,
        )
    ).status_code == 200

    second_started = paused_at + timedelta(seconds=2)
    second = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json=snapshot(
            second_task,
            str(uuid4()),
            "RUNNING",
            second_started,
            second_started,
            0,
            last_resumed_at=second_started,
        ),
    )
    refreshed_plan = await client.get(
        f"/api/v1/daily-plans/by-date/{profile_today().isoformat()}",
        headers=auth_header(token),
    )
    refreshed_item = next(
        candidate for candidate in refreshed_plan.json()["items"] if candidate["id"] == item_id
    )

    assert second.status_code == 200
    assert refreshed_item["status"] == "PAUSED"
    assert refreshed_item["actual_seconds"] == 600


async def test_child_session_time_rolls_up_to_parent_budget(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    project = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "课程", "node_type": "PROJECT"},
    )
    module = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "章节",
            "node_type": "MODULE",
            "parent_id": project.json()["id"],
        },
    )
    child = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "练习",
            "node_type": "TASK",
            "parent_id": module.json()["id"],
            "estimated_seconds": 3_600,
        },
    )
    parent_id = project.json()["id"]
    module_id = module.json()["id"]
    child_id = child.json()["id"]
    started = datetime.now(UTC)
    ended = started + timedelta(minutes=30)

    completed = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json=snapshot(
            child_id,
            str(uuid4()),
            "COMPLETED",
            started,
            ended,
            1_800,
            ended_at=ended,
        ),
    )
    assert completed.status_code == 200

    tasks = await client.get("/api/v1/tasks", headers=auth_header(token))
    by_id = {task["id"]: task for task in tasks.json()}
    assert by_id[child_id]["direct_actual_seconds"] == 1_800
    assert by_id[child_id]["actual_seconds"] == 1_800
    assert by_id[module_id]["actual_seconds"] == 1_800
    assert by_id[parent_id]["direct_actual_seconds"] == 0
    assert by_id[parent_id]["actual_seconds"] == 1_800


async def test_session_cannot_use_another_users_task(client: AsyncClient) -> None:
    first_token, _ = await register_user(client, "first")
    second_token, _ = await register_user(client, "second")
    task_id = await create_task(client, first_token, "私有任务")
    started = datetime.now(UTC)

    response = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(second_token),
        json=snapshot(
            task_id,
            str(uuid4()),
            "RUNNING",
            started,
            started,
            0,
            last_resumed_at=started,
        ),
    )
    assert response.status_code == 404


async def test_session_rejects_project_and_module_containers(client: AsyncClient) -> None:
    token, _ = await register_user(client, "container_timer")
    project, _, _ = await create_structured_task(client, token, "可计时任务")
    started = datetime.now(UTC)
    response = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json=snapshot(
            project["id"],
            str(uuid4()),
            "RUNNING",
            started,
            started,
            0,
            last_resumed_at=started,
        ),
    )
    assert response.status_code == 409
    assert "Only executable tasks" in response.json()["detail"]


async def test_legacy_daily_item_snapshot_recovers_missing_task_id(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "legacy_daily_timer")
    task_id = await create_task(client, token, "旧版今日任务")
    plan = await client.post(
        "/api/v1/daily-plans",
        headers=auth_header(token),
        json={"plan_date": profile_today().isoformat()},
    )
    item = await client.post(
        f"/api/v1/daily-plans/{plan.json()['id']}/items",
        headers=auth_header(token),
        json={"task_id": task_id, "estimated_seconds": 600},
    )
    session_id = str(uuid4())
    started = datetime.now(UTC)
    ended = started + timedelta(minutes=5)
    payload = snapshot(
        task_id,
        str(uuid4()),
        "COMPLETED",
        started,
        ended,
        300,
        ended_at=ended,
    )
    payload["task_id"] = None
    payload["daily_plan_item_id"] = item.json()["id"]

    created = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=payload,
    )
    replay = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json=payload,
    )

    assert created.status_code == 200
    assert created.json()["task_id"] == task_id
    assert replay.status_code == 200
    assert replay.json()["task_id"] == task_id


async def test_completed_project_session_survives_later_children(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "history_project")
    project, _, _ = await create_structured_task(client, token, "已有子任务")
    started = datetime.now(UTC)
    ended = started + timedelta(minutes=7)

    response = await client.put(
        f"/api/v1/sessions/{uuid4()}",
        headers=auth_header(token),
        json=snapshot(
            project["id"],
            str(uuid4()),
            "COMPLETED",
            started,
            ended,
            420,
            ended_at=ended,
        ),
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == project["id"]


async def test_ending_a_timer_early_keeps_the_task_open_and_accumulates_time(
    client: AsyncClient,
) -> None:
    """Stopping before the planned time is up leaves the task startable.

    The second session continues the task's own clock: only time this app
    measured is recorded, and the item's total is the sum of both sessions.
    """

    token, _ = await register_user(client, "resume_after_early_end")
    task_id = await create_task(client, token, "提前结束的任务")
    plan = await client.post(
        "/api/v1/daily-plans",
        headers=auth_header(token),
        json={"plan_date": profile_today().isoformat()},
    )
    assert plan.status_code == 201
    plan_id = plan.json()["id"]
    item = await client.post(
        f"/api/v1/daily-plans/{plan_id}/items",
        headers=auth_header(token),
        json={"task_id": task_id, "estimated_seconds": 3_600},
    )
    assert item.status_code == 201
    item_id = item.json()["id"]

    async def run_session(
        start: datetime,
        seconds: int,
        *,
        complete: bool,
    ) -> None:
        session_id = str(uuid4())
        client_id = str(uuid4())
        running = snapshot(
            task_id,
            client_id,
            "RUNNING",
            start,
            start,
            0,
            last_resumed_at=start,
        )
        running["daily_plan_item_id"] = item_id
        assert (
            await client.put(
                f"/api/v1/sessions/{session_id}",
                headers=auth_header(token),
                json=running,
            )
        ).status_code == 200
        ended_at = start + timedelta(seconds=seconds)
        completed = snapshot(
            task_id,
            client_id,
            "COMPLETED",
            start,
            ended_at,
            seconds,
            ended_at=ended_at,
        )
        completed.update(
            {"daily_plan_item_id": item_id, "complete_daily_item": complete}
        )
        assert (
            await client.put(
                f"/api/v1/sessions/{session_id}",
                headers=auth_header(token),
                json=completed,
            )
        ).status_code == 200

    started = datetime.now(UTC) - timedelta(hours=1)
    await run_session(started, 600, complete=False)

    stopped = await client.get(
        f"/api/v1/daily-plans/by-date/{profile_today().isoformat()}",
        headers=auth_header(token),
    )
    assert stopped.status_code == 200
    stopped_item = next(
        entry for entry in stopped.json()["items"] if entry["id"] == item_id
    )
    assert stopped_item["status"] == "PAUSED"
    assert stopped_item["completed_at"] is None
    assert stopped_item["actual_seconds"] == 600

    # Starting the task again picks up where it stopped rather than replacing
    # the recorded time.
    await run_session(started + timedelta(minutes=20), 300, complete=True)

    finished = await client.get(
        f"/api/v1/daily-plans/by-date/{profile_today().isoformat()}",
        headers=auth_header(token),
    )
    finished_item = next(
        entry for entry in finished.json()["items"] if entry["id"] == item_id
    )
    assert finished_item["status"] == "DONE"
    assert finished_item["actual_seconds"] == 900

    task = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_header(token))
    assert task.status_code == 200
    assert task.json()["actual_seconds"] == 900


async def test_a_task_completed_without_a_timer_records_no_time(
    client: AsyncClient,
) -> None:
    """Marking a task done directly is allowed and adds no unmeasured time."""

    token, _ = await register_user(client, "complete_without_timer")
    task_id = await create_task(client, token, "直接标记完成")
    plan = await client.post(
        "/api/v1/daily-plans",
        headers=auth_header(token),
        json={"plan_date": profile_today().isoformat()},
    )
    assert plan.status_code == 201
    item = await client.post(
        f"/api/v1/daily-plans/{plan.json()['id']}/items",
        headers=auth_header(token),
        json={"task_id": task_id, "estimated_seconds": 3_600},
    )
    assert item.status_code == 201

    done = await client.patch(
        f"/api/v1/daily-plan-items/{item.json()['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "DONE"
    assert done.json()["actual_seconds"] == 0

    task = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_header(token))
    assert task.json()["actual_seconds"] == 0
