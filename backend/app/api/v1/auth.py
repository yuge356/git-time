"""Registration, login and current-account endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_service_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.auth import (
    AccountResponse,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
ServiceDatabase = Annotated[AsyncSession, Depends(get_service_db)]


def account_response(user: User, profile: Profile) -> AccountResponse:
    """Convert ORM objects to the stable public account schema."""

    return AccountResponse(email=user.email, profile=profile)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: ServiceDatabase) -> AuthResponse:
    """Create a private account and its one-to-one public profile."""

    existing = await db.scalar(
        select(User)
        .outerjoin(User.profile)
        .where(or_(User.email == payload.email, Profile.username == payload.username))
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username is already registered",
        )

    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
    )
    profile = Profile(
        id=user.id,
        username=payload.username,
        display_name=payload.display_name,
    )
    user.profile = profile
    db.add(user)
    await db.flush()
    await db.refresh(user)
    await db.refresh(profile)

    response = AuthResponse(
        access_token=create_access_token(user.id),
        user=account_response(user, profile),
    )
    await db.commit()
    return response


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: ServiceDatabase) -> AuthResponse:
    """Authenticate an active account without revealing which field failed."""

    user = await db.scalar(
        select(User)
        .options(selectinload(User.profile))
        .where(User.email == str(payload.email))
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return AuthResponse(
        access_token=create_access_token(user.id),
        user=account_response(user, user.profile),
    )


@router.get("/me", response_model=AccountResponse)
async def read_current_account(current_user: CurrentUser) -> AccountResponse:
    """Return the account represented by the bearer token."""

    return account_response(current_user, current_user.profile)

