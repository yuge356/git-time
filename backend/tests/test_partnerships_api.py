"""User discovery, partnership lifecycle and block API tests."""

from httpx import AsyncClient

from tests.test_tasks_api import auth_header, register_user


async def test_search_invite_accept_and_remove_partner(client: AsyncClient) -> None:
    first_token, first_id = await register_user(client, "first")
    second_token, second_id = await register_user(client, "second")

    search = await client.get(
        "/api/v1/users/search",
        headers=auth_header(first_token),
        params={"q": "learner_second"},
    )
    assert search.status_code == 200
    assert search.json()[0]["id"] == second_id

    invited = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(first_token),
        json={"addressee_id": second_id},
    )
    assert invited.status_code == 201
    assert invited.json()["direction"] == "OUTGOING"
    partnership_id = invited.json()["id"]

    duplicate = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(second_token),
        json={"addressee_id": first_id},
    )
    assert duplicate.status_code == 409

    incoming = await client.get(
        "/api/v1/partnerships",
        headers=auth_header(second_token),
    )
    assert incoming.json()[0]["direction"] == "INCOMING"

    accepted = await client.patch(
        f"/api/v1/partnerships/{partnership_id}",
        headers=auth_header(second_token),
        json={"accept": True},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    assert accepted.json()["direction"] == "PARTNER"

    removed = await client.delete(
        f"/api/v1/partnerships/{partnership_id}",
        headers=auth_header(first_token),
    )
    assert removed.status_code == 204
    relationships = await client.get(
        "/api/v1/partnerships",
        headers=auth_header(second_token),
    )
    assert relationships.json() == []


async def test_decline_closes_request_and_allows_new_invitation(
    client: AsyncClient,
) -> None:
    first_token, first_id = await register_user(client, "first")
    second_token, second_id = await register_user(client, "second")
    invited = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(first_token),
        json={"addressee_id": second_id},
    )
    declined = await client.patch(
        f"/api/v1/partnerships/{invited.json()['id']}",
        headers=auth_header(second_token),
        json={"accept": False},
    )
    reinvited = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(second_token),
        json={"addressee_id": first_id},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"
    assert reinvited.status_code == 201


async def test_block_hides_search_and_closes_partnership(client: AsyncClient) -> None:
    first_token, first_id = await register_user(client, "first")
    second_token, second_id = await register_user(client, "second")
    invited = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(first_token),
        json={"addressee_id": second_id},
    )
    await client.patch(
        f"/api/v1/partnerships/{invited.json()['id']}",
        headers=auth_header(second_token),
        json={"accept": True},
    )

    blocked = await client.post(
        f"/api/v1/blocks/{second_id}",
        headers=auth_header(first_token),
    )
    assert blocked.status_code == 201
    block_id = blocked.json()["id"]

    hidden = await client.get(
        "/api/v1/users/search",
        headers=auth_header(second_token),
        params={"q": "learner_first"},
    )
    relationships = await client.get(
        "/api/v1/partnerships",
        headers=auth_header(second_token),
    )
    blocked_invite = await client.post(
        "/api/v1/partnerships/invitations",
        headers=auth_header(second_token),
        json={"addressee_id": first_id},
    )
    assert hidden.json() == []
    assert relationships.json() == []
    assert blocked_invite.status_code == 403

    unblocked = await client.delete(
        f"/api/v1/blocks/{block_id}",
        headers=auth_header(first_token),
    )
    assert unblocked.status_code == 204
