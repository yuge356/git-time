"""Account and profile API behavior tests."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.api import dependencies
from app.core.config import settings
from app.core.supabase_auth import SupabaseIdentity

REGISTER_PAYLOAD = {
    "email": "learner@example.com",
    "username": "learner_01",
    "display_name": "学习者",
    "password": "strong-password",
}


async def test_registration_country_uses_proxy_header_and_china_fallback(
    client: AsyncClient,
) -> None:
    detected = await client.get(
        "/api/v1/auth/registration-country",
        headers={"x-vercel-ip-country": "JP"},
    )
    fallback = await client.get("/api/v1/auth/registration-country")

    assert detected.status_code == 200
    assert detected.json() == {"country_code": "JP"}
    assert fallback.json() == {"country_code": "CN"}


async def test_register_login_and_read_current_account(client: AsyncClient) -> None:
    register = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert register.status_code == 201
    body = register.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == REGISTER_PAYLOAD["email"]
    assert body["user"]["profile"]["username"] == REGISTER_PAYLOAD["username"]

    token = body["access_token"]
    current = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert current.status_code == 200
    assert current.json()["profile"]["display_name"] == "学习者"

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": REGISTER_PAYLOAD["email"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    assert login.status_code == 200
    assert login.json()["user"]["profile"]["username"] == "learner_01"


async def test_duplicate_account_is_rejected(client: AsyncClient) -> None:
    first = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    second = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert first.status_code == 201
    assert second.status_code == 409


async def test_invalid_password_does_not_disclose_account_state(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Email or password is incorrect"


async def test_profile_owner_can_update_profile(client: AsyncClient) -> None:
    register = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    token = register.json()["access_token"]

    response = await client.patch(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "display_name": "新的名称",
            "bio": "按预算学习。",
            "timezone": "Asia/Shanghai",
            "is_searchable": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "新的名称"
    assert body["bio"] == "按预算学习。"
    assert body["is_searchable"] is False


async def test_profile_requires_authentication(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/profiles/me", json={"display_name": "No access"})
    assert response.status_code == 401


async def test_supabase_identity_creates_application_profile(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified hosted identity is mirrored without storing its password."""

    identity = SupabaseIdentity(
        id=uuid4(),
        email=None,
        phone="+8613800138000",
        user_metadata={"username": "phone_user", "display_name": "手机用户"},
    )

    async def verified_identity(_: str) -> SupabaseIdentity:
        return identity

    settings.auth_provider = "supabase"
    monkeypatch.setattr(dependencies, "verify_supabase_access_token", verified_identity)

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer supabase-access-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["id"] == str(identity.id)
    assert body["email"] is None
    assert body["phone"] == identity.phone
    assert body["profile"]["username"] == "phone_user"
