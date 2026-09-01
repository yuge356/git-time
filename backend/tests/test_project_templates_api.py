"""Project-template CRUD and validation tests."""

from uuid import uuid4

from httpx import AsyncClient

from tests.test_tasks_api import auth_header, register_user

STUDY_TEMPLATE = {
    "name": "学习课程",
    "description": "预习、听课、复习、练习四个阶段",
    "icon": "📚",
    "preset_key": "study",
    "default_estimated_seconds": 1_800,
    "structure": [
        {
            "node_type": "MODULE",
            "title": "预习",
            "children": [
                {"node_type": "TASK", "title": "阅读教材", "estimated_seconds": 1_800},
            ],
        },
        {"node_type": "TASK", "title": "课后练习", "estimated_seconds": 2_700},
    ],
}


async def test_template_round_trip(client: AsyncClient) -> None:
    """A saved template returns with its outline intact."""

    token, _ = await register_user(client, "template_owner")
    created = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json=STUDY_TEMPLATE,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "学习课程"
    assert body["preset_key"] == "study"
    assert [node["title"] for node in body["structure"]] == ["预习", "课后练习"]
    assert body["structure"][0]["children"][0]["title"] == "阅读教材"

    listed = await client.get("/api/v1/project-templates", headers=auth_header(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]


async def test_client_generated_template_id_is_idempotent(client: AsyncClient) -> None:
    """Replaying an offline create updates the same row instead of failing."""

    token, _ = await register_user(client, "template_replay")
    template_id = str(uuid4())
    payload = {**STUDY_TEMPLATE, "id": template_id}

    first = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json=payload,
    )
    second = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json={**payload, "name": "改名后的模板"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == template_id
    assert second.json()["name"] == "改名后的模板"

    listed = await client.get("/api/v1/project-templates", headers=auth_header(token))
    assert len(listed.json()) == 1


async def test_template_edit_and_delete(client: AsyncClient) -> None:
    """Owners can rename, restructure and remove their own templates."""

    token, _ = await register_user(client, "template_editor")
    created = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json=STUDY_TEMPLATE,
    )
    template_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/project-templates/{template_id}",
        headers=auth_header(token),
        json={
            "name": "期末考试",
            "structure": [{"node_type": "TASK", "title": "刷真题", "estimated_seconds": 3_600}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "期末考试"
    assert len(updated.json()["structure"]) == 1

    removed = await client.delete(
        f"/api/v1/project-templates/{template_id}",
        headers=auth_header(token),
    )
    assert removed.status_code == 204

    listed = await client.get("/api/v1/project-templates", headers=auth_header(token))
    assert listed.json() == []


async def test_templates_are_owner_scoped(client: AsyncClient) -> None:
    """One user can never read or edit another user's templates."""

    owner_token, _ = await register_user(client, "template_owner_a")
    other_token, _ = await register_user(client, "template_owner_b")
    created = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(owner_token),
        json=STUDY_TEMPLATE,
    )
    template_id = created.json()["id"]

    listed = await client.get("/api/v1/project-templates", headers=auth_header(other_token))
    assert listed.json() == []

    forbidden = await client.patch(
        f"/api/v1/project-templates/{template_id}",
        headers=auth_header(other_token),
        json={"name": "偷来的模板"},
    )
    assert forbidden.status_code == 404


async def test_template_outline_rejects_impossible_hierarchies(client: AsyncClient) -> None:
    """A blueprint may only describe trees the task API would accept."""

    token, _ = await register_user(client, "template_validation")
    nested_module = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json={
            "name": "非法模板",
            "structure": [
                {
                    "node_type": "MODULE",
                    "title": "模块",
                    "children": [{"node_type": "MODULE", "title": "子模块"}],
                }
            ],
        },
    )
    assert nested_module.status_code == 422

    too_deep = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json={
            "name": "太深的模板",
            "structure": [
                {
                    "node_type": "MODULE",
                    "title": "模块",
                    "children": [
                        {
                            "node_type": "TASK",
                            "title": "任务",
                            "children": [
                                {
                                    "node_type": "TASK",
                                    "title": "子任务",
                                    "children": [
                                        {"node_type": "TASK", "title": "孙任务"},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert too_deep.status_code == 422

    nested_project = await client.post(
        "/api/v1/project-templates",
        headers=auth_header(token),
        json={"name": "项目套项目", "structure": [{"node_type": "PROJECT", "title": "项目"}]},
    )
    assert nested_project.status_code == 422
