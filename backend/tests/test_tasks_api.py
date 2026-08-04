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


async def create_structured_task(
    client: AsyncClient,
    token: str,
    task_title: str,
) -> tuple[dict, dict, dict]:
    """Create one project/module/task branch and return all three responses."""

    project = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": f"{task_title} project", "node_type": "PROJECT"},
    )
    assert project.status_code == 201
    module = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": f"{task_title} module",
            "node_type": "MODULE",
            "parent_id": project.json()["id"],
        },
    )
    assert module.status_code == 201
    task = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": task_title,
            "node_type": "TASK",
            "parent_id": module.json()["id"],
            "estimated_seconds": 3_600,
        },
    )
    assert task.status_code == 201
    return project.json(), module.json(), task.json()


async def test_client_generated_task_id_is_idempotent(client: AsyncClient) -> None:
    token, _ = await register_user(client, "stable_task_id")
    task_id = str(uuid4())
    payload = {
        "id": task_id,
        "title": "Offline-created project",
        "node_type": "PROJECT",
        "parent_id": None,
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
        json={"title": "Python 课程", "node_type": "PROJECT"},
    )
    assert root.status_code == 201
    root_body = root.json()
    assert root_body["owner_id"] == owner_id
    assert root_body["parent_id"] is None
    assert root_body["node_type"] == "PROJECT"
    assert root_body["budget_level"] == "NOT_SET"
    assert root_body["direct_actual_seconds"] == 0
    assert root_body["actual_seconds"] == 0
    assert root_body["is_leaf"] is True

    module = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "第一章",
            "node_type": "MODULE",
            "parent_id": root_body["id"],
        },
    )
    assert module.status_code == 201
    task = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "练习 1",
            "node_type": "TASK",
            "parent_id": module.json()["id"],
            "estimated_seconds": 7_200,
        },
    )
    assert task.status_code == 201

    response = await client.get("/api/v1/tasks", headers=auth_header(token))
    assert response.status_code == 200
    by_title = {item["title"]: item for item in response.json()}
    assert set(by_title) == {"Python 课程", "第一章", "练习 1"}
    assert by_title["Python 课程"]["task_count"] == 1
    assert by_title["Python 课程"]["planned_seconds"] == 7_200
    assert by_title["Python 课程"]["is_leaf"] is False
    assert by_title["第一章"]["parent_id"] == root_body["id"]
    assert by_title["第一章"]["is_leaf"] is False
    assert by_title["练习 1"]["is_leaf"] is True


async def test_task_status_controls_completed_timestamp(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    _, _, created = await create_structured_task(client, token, "练习")
    task_id = created["id"]

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
    _, module, _ = await create_structured_task(client, token, "占位任务")
    created = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "每日复习",
            "node_type": "TASK",
            "parent_id": module["id"],
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
        json={"title": "课程", "node_type": "PROJECT"},
    )
    child = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "章节",
            "node_type": "MODULE",
            "parent_id": root.json()["id"],
        },
    )

    response = await client.patch(
        f"/api/v1/tasks/{child.json()['id']}",
        headers=auth_header(token),
        json={"parent_id": child.json()["id"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "A task cannot be its own parent"


async def test_deleting_parent_soft_deletes_the_subtree(client: AsyncClient) -> None:
    token, _ = await register_user(client)
    root = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={"title": "课程", "node_type": "PROJECT"},
    )
    await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "章节",
            "node_type": "MODULE",
            "parent_id": root.json()["id"],
        },
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
        json={"title": "Private project", "node_type": "PROJECT"},
    )
    task_id = private_task.json()["id"]

    read = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_header(second_token))
    attach = await client.post(
        "/api/v1/tasks",
        headers=auth_header(second_token),
        json={"title": "Invalid module", "node_type": "MODULE", "parent_id": task_id},
    )

    assert read.status_code == 404
    assert attach.status_code == 404


async def test_container_defaults_inherit_and_bulk_apply_safely(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client, "defaults")
    project = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "技术信息学",
            "node_type": "PROJECT",
            "default_estimated_seconds": 1_800,
            "default_repeat_rule": "WEEKDAYS",
            "default_daily_reminder_time": "09:00",
        },
    )
    module = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "练习",
            "node_type": "MODULE",
            "parent_id": project.json()["id"],
        },
    )
    inherited = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "练习 1",
            "node_type": "TASK",
            "parent_id": module.json()["id"],
        },
    )
    assert inherited.status_code == 201
    assert inherited.json()["estimated_seconds"] == 1_800
    assert inherited.json()["repeat_rule"] == "WEEKDAYS"
    assert inherited.json()["daily_reminder_time"] == "09:00:00"

    empty = await client.post(
        "/api/v1/tasks",
        headers=auth_header(token),
        json={
            "title": "练习 2",
            "node_type": "TASK",
            "parent_id": module.json()["id"],
            "estimated_seconds": 0,
            "repeat_rule": "NONE",
            "daily_reminder_time": None,
        },
    )
    applied = await client.post(
        f"/api/v1/tasks/{project.json()['id']}/apply-defaults",
        headers=auth_header(token),
        json={"overwrite": False},
    )
    assert applied.status_code == 200
    refreshed = {task["id"]: task for task in applied.json()["tasks"]}
    assert refreshed[empty.json()["id"]]["estimated_seconds"] == 1_800
    assert refreshed[empty.json()["id"]]["repeat_rule"] == "WEEKDAYS"


async def test_container_progress_and_fixed_budget_are_derived(client: AsyncClient) -> None:
    token, _ = await register_user(client, "summary")
    project, module, first = await create_structured_task(client, token, "练习 1")
    fixed = await client.patch(
        f"/api/v1/tasks/{project['id']}",
        headers=auth_header(token),
        json={"budget_mode": "FIXED_CAP", "fixed_budget_seconds": 1_800},
    )
    assert fixed.status_code == 200
    assert fixed.json()["planned_seconds"] == 1_800
    assert fixed.json()["children_estimated_seconds"] == 3_600

    completed = await client.patch(
        f"/api/v1/tasks/{first['id']}",
        headers=auth_header(token),
        json={"status": "DONE"},
    )
    assert completed.status_code == 200
    listed = await client.get("/api/v1/tasks", headers=auth_header(token))
    by_id = {task["id"]: task for task in listed.json()}
    assert by_id[module["id"]]["progress_ratio"] == 1
    assert by_id[project["id"]]["completed_task_count"] == 1
    assert by_id[project["id"]]["task_count"] == 1


async def test_active_session_prevents_task_subtree_deletion(client: AsyncClient) -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    token, _ = await register_user(client)
    project, _, task = await create_structured_task(client, token, "Active task")
    now = datetime.now(UTC).isoformat()
    session_id = str(uuid4())
    session = await client.put(
        f"/api/v1/sessions/{session_id}",
        headers=auth_header(token),
        json={
            "task_id": task["id"],
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
        f"/api/v1/tasks/{project['id']}",
        headers=auth_header(token),
    )
    assert deleted.status_code == 409
