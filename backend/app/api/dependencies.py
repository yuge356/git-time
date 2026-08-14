"""Reusable authentication and database dependencies."""

import re
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import InvalidTokenError, decode_access_token
from app.core.supabase_auth import SupabaseIdentity, verify_supabase_access_token
from app.db.session import get_db, set_request_identity
from app.models.profile import Profile
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
USERNAME_PATTERN = re.compile(r"^[a-z0-9_]{3,30}$")


def _profile_seed(identity: SupabaseIdentity) -> tuple[str, str]:
    """Create safe defaults from trusted Supabase user metadata."""

    raw_username = str(identity.user_metadata.get("username") or "").strip().lower()
    username = raw_username if USERNAME_PATTERN.fullmatch(raw_username) else ""
    if not username:
        username = f"user_{identity.id.hex[:10]}"
    raw_display_name = str(identity.user_metadata.get("display_name") or "").strip()
    return username, (raw_display_name[:80] or username)


async def _load_or_create_supabase_user(
    db: AsyncSession,
    identity: SupabaseIdentity,
) -> User:
    """Mirror a verified Supabase account into application-owned profile tables."""

    await set_request_identity(db, identity.id)
    user = await db.scalar(
        select(User).options(selectinload(User.profile)).where(User.id == identity.id)
    )
    if user is not None:
        changed = user.email != identity.email or user.phone != identity.phone
        if changed:
            user.email = identity.email
            user.phone = identity.phone
            await db.commit()
            await set_request_identity(db, identity.id)
        return user

    username, display_name = _profile_seed(identity)
    occupied = await db.scalar(select(Profile.id).where(Profile.username == username))
    if occupied is not None:
        username = f"{username[:23]}_{identity.id.hex[:6]}"

    user = User(
        id=identity.id,
        email=identity.email,
        phone=identity.phone,
        password_hash=None,
    )
    user.profile = Profile(
        id=identity.id,
        username=username,
        display_name=display_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent first request or the Supabase database trigger may have
        # inserted the mirror between our SELECT and INSERT.
        await db.rollback()
    await set_request_identity(db, identity.id)
    mirrored = await db.scalar(
        select(User).options(selectinload(User.profile)).where(User.id == identity.id)
    )
    if mirrored is None:
        raise InvalidTokenError("Supabase account profile could not be initialized")
    return mirrored


async def get_current_user(
    db: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Authenticate a bearer token and establish the transaction RLS identity."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        user = await authenticate_access_token(db, credentials.credentials)
    except InvalidTokenError as exc:
        raise unauthorized from exc

    return user


async def authenticate_access_token(db: AsyncSession, token: str) -> User:
    """Validate either configured token type and establish its RLS identity."""

    if settings.auth_provider == "supabase":
        identity = await verify_supabase_access_token(token)
        user = await _load_or_create_supabase_user(db, identity)
    else:
        user_id = decode_access_token(token)
        await set_request_identity(db, user_id)
        user = await db.scalar(
            select(User).options(selectinload(User.profile)).where(User.id == user_id)
        )
    if user is None or not user.is_active:
        raise InvalidTokenError("Account is unavailable")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
