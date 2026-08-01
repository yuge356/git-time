"""Access checks and response builders for partner plan sharing."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partnership import Partnership, PartnershipStatus
from app.models.sharing import DailyPlanShare
from app.schemas.partnership import PublicProfile
from app.schemas.sharing import ReceivedSharedPlan, SharedPlanItem
from app.services.daily_plans import build_daily_plan_response
from app.services.partnerships import (
    get_public_profile,
    partnership_pair_key,
    users_are_blocked,
)


async def require_active_partnership(
    db: AsyncSession,
    first_id: UUID,
    second_id: UUID,
) -> Partnership:
    """Require an accepted relationship with no block in either direction."""

    if await users_are_blocked(db, first_id, second_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This partner is unavailable",
        )
    partnership = await db.scalar(
        select(Partnership).where(
            Partnership.pair_key == partnership_pair_key(first_id, second_id),
            Partnership.status == PartnershipStatus.ACCEPTED,
            Partnership.deleted_at.is_(None),
        )
    )
    if partnership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An accepted partnership is required",
        )
    return partnership


async def get_received_share(
    db: AsyncSession,
    partner_id: UUID,
    share_id: UUID,
) -> DailyPlanShare:
    """Return one active share received by the authenticated partner."""

    share = await db.scalar(
        select(DailyPlanShare).where(
            DailyPlanShare.id == share_id,
            DailyPlanShare.partner_id == partner_id,
            DailyPlanShare.deleted_at.is_(None),
        )
    )
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    await require_active_partnership(db, share.owner_id, partner_id)
    return share


async def build_received_shared_plan(
    db: AsyncSession,
    share: DailyPlanShare,
) -> ReceivedSharedPlan:
    """Build a privacy-filtered plan response for its recipient."""

    from app.services.daily_plans import get_owned_daily_plan

    plan = await get_owned_daily_plan(db, share.owner_id, share.daily_plan_id)
    full = await build_daily_plan_response(db, plan)
    owner = await get_public_profile(db, share.owner_id)
    return ReceivedSharedPlan(
        share_id=share.id,
        daily_plan_id=plan.id,
        plan_date=plan.plan_date,
        owner=PublicProfile.model_validate(owner),
        share_duration=share.share_duration,
        total_items=full.total_items,
        completed_items=full.completed_items,
        items=[
            SharedPlanItem(
                id=item.id,
                title=item.title,
                status=item.status,
                estimated_seconds=(
                    item.estimated_seconds if share.share_duration else None
                ),
                actual_seconds=item.actual_seconds if share.share_duration else None,
            )
            for item in full.items
        ],
        created_at=share.created_at,
    )
