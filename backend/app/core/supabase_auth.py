"""Trusted validation for access tokens issued by Supabase Auth."""

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt
from jwt import InvalidTokenError as PyJwtInvalidTokenError
from jwt import PyJWKClient, PyJWKClientConnectionError

from app.core.config import settings
from app.core.security import InvalidTokenError

PHONE_PASSWORD_EMAIL_PATTERN = re.compile(
    r"^phone\.([1-9]\d{7,14})@phone\.dayflow\.invalid$",
    re.IGNORECASE,
)
_jwks_clients: dict[str, PyJWKClient] = {}
_http_client: httpx.AsyncClient | None = None


def _jwks_client() -> PyJWKClient:
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url, cache_keys=True, lifespan=600, timeout=5)
        _jwks_clients[url] = client
    return client


def _shared_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


@dataclass(frozen=True, slots=True)
class SupabaseIdentity:
    """Small verified identity surface consumed by the DayFlow API."""

    id: UUID
    email: str | None
    phone: str | None
    user_metadata: dict[str, Any]


def identity_contacts_from_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Hide DayFlow's internal phone alias and expose the E.164 identifier."""

    raw_email = payload.get("email")
    email = str(raw_email).strip().lower() if raw_email else None
    raw_phone = payload.get("phone")
    phone = str(raw_phone).strip() if raw_phone else None
    if phone or not email:
        return email, phone

    alias = PHONE_PASSWORD_EMAIL_PATTERN.fullmatch(email)
    if alias:
        return None, f"+{alias.group(1)}"
    return email, None


async def verify_supabase_access_token(token: str) -> SupabaseIdentity:
    """Ask Supabase Auth to validate a user JWT and return trusted claims.

    Calling ``/auth/v1/user`` supports both legacy HS256 projects and the new
    asymmetric signing-key system without placing a private JWT secret in the
    DayFlow application.
    """

    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise InvalidTokenError("Supabase authentication is not configured")

    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") in {"ES256", "RS256"} and header.get("kid"):
            signing_key = await asyncio.to_thread(_jwks_client().get_signing_key_from_jwt, token)
            payload = jwt.decode(
                token, signing_key.key, algorithms=[header["alg"]],
                audience="authenticated",
                issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            )
            user_id = UUID(str(payload["sub"]))
            metadata = payload.get("user_metadata")
            email, phone = identity_contacts_from_payload(payload)
            return SupabaseIdentity(
                user_id,
                email,
                phone,
                metadata if isinstance(metadata, dict) else {},
            )
    except PyJWKClientConnectionError:
        pass
    except (PyJwtInvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Supabase access token is invalid or expired") from exc

    try:
        response = await _shared_http_client().get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as exc:
        raise InvalidTokenError("Supabase Auth is temporarily unavailable") from exc

    if response.status_code != 200:
        raise InvalidTokenError("Supabase access token is invalid or expired")

    try:
        payload = response.json()
        user_id = UUID(payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Supabase Auth returned an invalid identity") from exc

    metadata = payload.get("user_metadata")
    email, phone = identity_contacts_from_payload(payload)
    return SupabaseIdentity(
        id=user_id,
        email=email,
        phone=phone,
        user_metadata=metadata if isinstance(metadata, dict) else {},
    )
