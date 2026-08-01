"""Password hashing and signed access-token utilities."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


class InvalidTokenError(ValueError):
    """Raised when an access token is invalid, expired or malformed."""


def hash_password(password: str) -> str:
    """Create an Argon2 password hash."""

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Safely compare a plain password with its stored hash."""

    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: UUID) -> str:
    """Create a short-lived JWT whose subject is the authenticated user."""

    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    """Validate a JWT and return its user identifier."""

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Token type is not supported")
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Access token is invalid or expired") from exc

