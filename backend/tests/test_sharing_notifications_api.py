"""Controlled sharing, fixed encouragement and notification tests."""

from datetime import date

from httpx import AsyncClient

from tests.test_daily_plans_api import add_item, create_plan
from tests.test_tasks_api import auth_header, register_user


async def connect_partners(
    client: AsyncClient,
) -> tuple[str, str, str, str]:
    """Register and connect two users."""

    first_token, first_id = await register_user(client, "owner")
    second_token, second_id = await register_user(client, "partner")
    invite = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(first_token),
        json={"addressee_id": second_id},
    )
    assert invite.status_code == 201
    accepted = await client.patch(
        f"/api/v1/partnerships/{invite.json()['id']}",
        headers=auth_header(second_token),
        json={"accept": True},
    )
    assert accepted.status_code == 200
    return first_token, first_id, second_token, second_id


async def test_share_privacy_encouragement_completion_and_revoke(
    client: AsyncClient,
) -> None:
    owner_token, _, partner_token, partner_id = await connect_partners(client)
    plan = await create_plan(client, owner_token, date.today())
    item = await add_item(client, owner_token, plan["id"], title="Read chapter")

    shared = await client.post(
        "/api/v1/plan-shares",
        headers=auth_header(owner_token),
        json={
            "daily_plan_id": plan["id"],
            "partner_id": partner_id,
            "share_duration": False,
        },
    )
    assert shared.status_code == 201
    share_id = shared.json()["id"]

    received = await client.get(
        "/api/v1/shared-plans",
        headers=auth_header(partner_token),
    )
    assert received.status_code == 200
    shared_plan = received.json()[0]
    assert shared_plan["items"][0]["title"] == "Read chapter"
    assert shared_plan["items"][0]["estimated_seconds"] is None
    assert shared_plan["items"][0]["actual_seconds"] is None

    encouraged = await client.post(
        f"/api/v1/plan-shares/{share_id}/encouragements",
        headers=auth_header(partner_token),
        json={"encouragement_type": "KEEP_GOING"},
    )
    assert encouraged.status_code == 201

    completed = await client.patch(
        f"/api/v1/daily-plan-items/{item['id']}",
        headers=auth_header(owner_token),
        json={"status": "DONE"},
    )
    assert completed.status_code == 200

    owner_notifications = await client.get(
        "/api/v1/notifications",
        headers=auth_header(owner_token),
    )
    owner_types = {
        notification["notification_type"]
        for notification in owner_notifications.json()
    }
    assert "ENCOURAGEMENT" in owner_types

    partner_notifications = await client.get(
        "/api/v1/notifications",
        headers=auth_header(partner_token),
    )
    partner_types = {
        notification["notification_type"]
        for notification in partner_notifications.json()
    }
    assert {"PARTNER_INVITE", "PLAN_SHARED", "TASK_COMPLETED"} <= partner_types

    unread = await client.get(
        "/api/v1/notifications/unread-count",
        headers=auth_header(partner_token),
    )
    assert unread.json()["count"] >= 3
    notification_id = partner_notifications.json()[0]["id"]
    marked = await client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=auth_header(partner_token),
    )
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    revoked = await client.delete(
        f"/api/v1/plan-shares/{share_id}",
        headers=auth_header(owner_token),
    )
    after_revoke = await client.get(
        "/api/v1/shared-plans",
        headers=auth_header(partner_token),
    )
    assert revoked.status_code == 204
    assert after_revoke.json() == []


async def test_only_accepted_unblocked_partner_can_receive_share(
    client: AsyncClient,
) -> None:
    owner_token, _, stranger_token, stranger_id = await register_pair(client)
    plan = await create_plan(client, owner_token, date.today())
    denied = await client.post(
        "/api/v1/plan-shares",
        headers=auth_header(owner_token),
        json={
            "daily_plan_id": plan["id"],
            "partner_id": stranger_id,
            "share_duration": True,
        },
    )
    assert denied.status_code == 403

    hidden = await client.get(
        "/api/v1/shared-plans",
        headers=auth_header(stranger_token),
    )
    assert hidden.json() == []


async def register_pair(
    client: AsyncClient,
) -> tuple[str, str, str, str]:
    """Register two unrelated users."""

    first_token, first_id = await register_user(client, "unrelated_owner")
    second_token, second_id = await register_user(client, "unrelated_other")
    return first_token, first_id, second_token, second_id
