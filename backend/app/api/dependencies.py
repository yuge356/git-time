"""Reusable authentication and database dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db, set_request_identity
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


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
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise unauthorized from exc

    await set_request_identity(db, user_id)
    user = await db.scalar(
        select(User).options(selectinload(User.profile)).where(User.id == user_id)
    )
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

