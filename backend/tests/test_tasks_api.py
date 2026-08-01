"""Hierarchical task API behavior tests."""

from uuid import uuid4

from httpx import AsyncClient


async def register_user(
    client: AsyncClient,
    suffix: str = "one",
) -> tuple[str, str]:
    """Register a test user and return bearer token and profile id."""

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"learner-{suffix}@example.com",
            "username": f"learner_{suffix}",
            "display_name": f"Learner {suffix}",
            "password": "strong-password",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["access_token"], body["user"]["profile"]["id"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_client_generated_task_id_is_idempotent(client: AsyncClient) -> None:
    token, _ = await register_user(client, "stable_task_id")
    task_id = str(uuid4())
    payload = {
        "id": task_id,
        "title": "Offline-created task",
        "parent_id": None,
        "estimated_seconds": 600,
    }
    first = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json=payload,
    )
    replay = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json=payload,
    )
    listed = await client.get("/api/v1/tasks", headers=auth_header(token))
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == task_id
    assert [item["id"] for item in listed.json()].count(task_id) == 1


async def test_create_and_list_task_tree(client: AsyncClient) -> None:
    token, owner_id = await register_user(client)
    root = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "Python 课程", "estimated_seconds": 72_000},
    )
    assert root.status_code == 201
    root_body = root.json()
    assert root_body["owner_id"] == owner_id
    assert root_body["parent_id"] is None
    assert root_body["budget_level"] == "NORMAL"
    assert root_body["direct_actual_seconds"] == 0
    assert root_body["actual_seconds"] == 0

    child = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "第一章",
            "parent_id": root_body["id"],
            "estimated_seconds": 7_200,
        },
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == root_body["id"]

    response = await client.get("/api/v1/tasks", headers=auth_header(token))
    assert response.status_code == 200
    assert {item["title"] for item in response.json()} == {"Python 课程", "第一章"}


async def test_task_status_controls_completed_timestamp(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    created = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "练习"},
    )
    task_id = created.json()["id"]

    completed = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None

    reopened = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=auth_header(token),
        json={"status": "IN_PROGRESS"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None


async def test_task_recurrence_and_daily_reminder_are_persisted(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "recurring")
    created = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "每日复习",
            "repeat_rule": "DAILY",
            "daily_reminder_time": "20:30",
        },
    )
    assert created.status_code == 201
    assert created.json()["repeat_rule"] == "DAILY"
    assert created.json()["daily_reminder_time"] == "20:30:00"

    updated = await client.patch(
        f"/api/v1/tasks/{created.json()['id']}",
        headers=auth_header(token),
        json={
            "repeat_rule": "WEEKDAYS",
            "daily_reminder_time": None,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["repeat_rule"] == "WEEKDAYS"
    assert updated.json()["daily_reminder_time"] is None


async def test_task_hierarchy_rejects_cycles(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    root = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "课程"},
    )
    child = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "章节", "parent_id": root.json()["id"]},
    )

    response = await client.patch(
        f"/api/v1/tasks/{root.json()['id']}",
        headers=auth_header(token),
        json={"parent_id": child.json()["id"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Task hierarchy cannot contain a cycle"


async def test_deleting_parent_soft_deletes_the_subtree(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    root = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "课程"},
    )
    await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "章节", "parent_id": root.json()["id"]},
    )

    deleted = await client.delete(
        f"/api/v1/tasks/{root.json()['id']}",
        headers=auth_header(token),
    )
    assert deleted.status_code == 204

    tasks = await client.get("/api/v1/tasks", headers=auth_header(token))
    assert tasks.json() == []


async def test_user_cannot_read_or_attach_to_another_users_task(
    client: AsyncClient,
) -> None:
    first_token, _ = await register_user(client, "first")
    second_token, _ = await register_user(client, "second")
    private_task = await client.post(
        "/api/v1/tasks",
        headers=auth_header(first_token),
        json={"title": "Private task"},
    )
    task_id = private_task.json()["id"]

    read = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_header(second_token))
    attach = await client.post(
        "/api/v1/tasks",
        headers=auth_header(second_token),
        json={"title": "Invalid child", "parent_id": task_id},
    )

    assert read.status_code == 404
    assert attach.status_code == 404


async def test_active_session_prevents_task_subtree_deletion(client: AsyncClient) -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    token, _ = await register_user(client)
    task = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "Active task"},
    )
    now = datetime.now(UTC).isoformat()
    session_id = str(uuid4())
    session = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json={
            "task_id": task.json()["id"],
            "client_id": str(uuid4()),
            "status": "RUNNING",
            "started_at": now,
            "ended_at": None,
            "duration_seconds": 0,
            "last_resumed_at": now,
            "client_updated_at": now,
        },
    )
    assert session.status_code == 200

    deleted = await client.delete(
        f"/api/v1/tasks/{task.json()['id']}",
        headers=auth_header(token),
    )
    assert deleted.status_code == 409
