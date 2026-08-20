"""Supabase identity normalization and validation fallback tests."""

from typing import Any

import pytest
from jwt.exceptions import MissingCryptographyError

from app.core import supabase_auth
from app.core.config import settings
from app.core.supabase_auth import identity_contacts_from_payload


def test_phone_password_alias_becomes_e164_phone() -> None:
    email, phone = identity_contacts_from_payload(
        {"email": "phone.8613800138000@phone.dayflow.invalid", "phone": None}
    )

    assert email is None
    assert phone == "+8613800138000"


def test_regular_email_stays_an_email() -> None:
    email, phone = identity_contacts_from_payload(
        {"email": "Person@Example.com", "phone": None}
    )

    assert email == "person@example.com"
    assert phone is None


def test_native_phone_claim_remains_supported() -> None:
    email, phone = identity_contacts_from_payload(
        {"email": None, "phone": "+8613800138000"}
    )

    assert email is None
    assert phone == "+8613800138000"


@pytest.mark.asyncio
async def test_missing_crypto_falls_back_to_supabase_user_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingCryptoJwks:
        def get_signing_key_from_jwt(self, _: str) -> None:
            raise MissingCryptographyError("crypto extra is unavailable")

    class Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {
                "id": "9f3c10f1-1f9e-4ce2-92be-4fdd14e673ac",
                "email": "person@example.com",
                "user_metadata": {},
            }

    class Client:
        async def get(self, *_: Any, **__: Any) -> Response:
            return Response()

    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_publishable_key", "sb_publishable_test")
    monkeypatch.setattr(supabase_auth, "_jwks_client", lambda: MissingCryptoJwks())
    monkeypatch.setattr(supabase_auth, "_shared_http_client", lambda: Client())

    token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImsifQ.e30.c2ln"
    identity = await supabase_auth.verify_supabase_access_token(token)

    assert identity.email == "person@example.com"
