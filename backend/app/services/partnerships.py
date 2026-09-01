"""Partnership lookup and mutual-block enforcement."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partnership import Partnership, UserBlock
from app.models.profile import Profile
from app.schemas.partnership import (
    PartnershipResponse,
    PublicProfile,
    RelationshipDirection,
)


def partnership_pair_key(first_id: UUID, second_id: UUID) -> str:
    """Return the canonical key used to prevent opposite-direction duplicates."""

    return ":".join(sorted((str(first_id), str(second_id))))


async def users_are_blocked(
    db: AsyncSession,
    first_id: UUID,
    second_id: UUID,
) -> bool:
    """Return true when either user has blocked the other."""

    block_id = await db.scalar(
        select(UserBlock.id).where(
            or_(
                (UserBlock.blocker_id == first_id) & (UserBlock.blocked_id == second_id),
                (UserBlock.blocker_id == second_id) & (UserBlock.blocked_id == first_id),
            )
        )
    )
    return block_id is not None


async def get_owned_partnership(
    db: AsyncSession,
    user_id: UUID,
    partnership_id: UUID,
) -> Partnership:
    """Return a live relationship involving the authenticated user."""

    partnership = await db.scalar(
        select(Partnership).where(
            Partnership.id == partnership_id,
            or_(
                Partnership.requester_id == user_id,
                Partnership.addressee_id == user_id,
            ),
            Partnership.deleted_at.is_(None),
        )
    )
    if partnership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partnership not found",
        )
    return partnership


async def get_public_profile(
    db: AsyncSession,
    user_id: UUID,
) -> Profile:
    """Return a profile or a non-disclosing not-found response."""

    profile = await db.scalar(select(Profile).where(Profile.id == user_id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return profile


def _hidden_partner_profile(user_id: UUID) -> PublicProfile:
    """Describe a partner whose profile row the reader may not select.

    Row-level security can hide the other participant -- a requester who
    turned discovery off, or a database that has not run the pending-
    invitation policy migration yet. Dropping the relationship in that case
    made incoming invitations impossible to see or answer, so the invitation
    is still returned with a neutral placeholder identity.
    """

    return PublicProfile(
        id=user_id,
        username="unavailable",
        display_name="未公开用户",
        avatar_url=None,
        bio=None,
    )


async def to_partnership_response(
    db: AsyncSession,
    partnership: Partnership,
    user_id: UUID,
) -> PartnershipResponse:
    """Normalize an invitation around the current user's perspective."""

    if partnership.requester_id == user_id:
        partner_id = partnership.addressee_id
        direction = (
            RelationshipDirection.PARTNER
            if partnership.status.value == "ACCEPTED"
            else RelationshipDirection.OUTGOING
        )
    else:
        partner_id = partnership.requester_id
        direction = (
            RelationshipDirection.PARTNER
            if partnership.status.value == "ACCEPTED"
            else RelationshipDirection.INCOMING
        )
    profile = await db.scalar(select(Profile).where(Profile.id == partner_id))
    partner = (
        PublicProfile.model_validate(profile)
        if profile is not None
        else _hidden_partner_profile(partner_id)
    )
    return PartnershipResponse(
        id=partnership.id,
        status=partnership.status,
        direction=direction,
        partner=partner,
        created_at=partnership.created_at,
        responded_at=partnership.responded_at,
    )


def close_partnership(partnership: Partnership) -> None:
    """Soft-delete a relationship while preserving its audit timestamps."""

    partnership.deleted_at = datetime.now(UTC)
