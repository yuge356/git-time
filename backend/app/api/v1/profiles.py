"""Current user's profile-management endpoint."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas.profile import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.patch("/me", response_model=ProfileResponse)
async def update_current_profile(
    payload: ProfileUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ProfileResponse:
    """Update only fields explicitly supplied by the profile owner."""

    profile = current_user.profile
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    try:
        # Refresh before commit because the PostgreSQL RLS identity is transaction-local.
        await db.flush()
        await db.refresh(profile)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use",
        ) from exc

    return ProfileResponse.model_validate(profile)
