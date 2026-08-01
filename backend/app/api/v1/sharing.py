"""Controlled partner plan sharing and fixed encouragement endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.daily_plan import DailyPlan
from app.models.sharing import (
    DailyPlanShare,
    Encouragement,
    NotificationType,
)
from app.schemas.partnership import PublicProfile
from app.schemas.sharing import (
    EncouragementCreate,
    EncouragementResponse,
    PlanShareCreate,
    ReceivedSharedPlan,
    SentPlanShare,
)
from app.services.daily_plans import get_owned_daily_plan
from app.services.notifications import (
    create_notification,
    notification_manager,
)
from app.services.partnerships import get_public_profile
from app.services.sharing import (
    build_received_shared_plan,
    get_received_share,
    require_active_partnership,
)

router = APIRouter(tags=["sharing"])


async def build_sent_share(
    db: DatabaseSession,
    share: DailyPlanShare,
) -> SentPlanShare:
    """Build one owner-facing share row."""

    plan = await get_owned_daily_plan(db, share.owner_id, share.daily_plan_id)
    partner = await get_public_profile(db, share.partner_id)
    return SentPlanShare(
        id=share.id,
        daily_plan_id=share.daily_plan_id,
        plan_date=plan.plan_date,
        partner=PublicProfile.model_validate(partner),
        share_duration=share.share_duration,
        created_at=share.created_at,
    )


@router.post(
    "/plan-shares",
    response_model=SentPlanShare,
    status_code=status.HTTP_201_CREATED,
)
async def share_daily_plan(
    payload: PlanShareCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> SentPlanShare:
    """Share an owned daily plan with one accepted, unblocked partner."""

    await get_owned_daily_plan(db, current_user.id, payload.daily_plan_id)
    await require_active_partnership(db, current_user.id, payload.partner_id)
    share = DailyPlanShare(
        daily_plan_id=payload.daily_plan_id,
        owner_id=current_user.id,
        partner_id=payload.partner_id,
        share_duration=payload.share_duration,
    )
    db.add(share)
    try:
        await db.flush()
        await db.refresh(share)
        notification = await create_notification(
            db,
            user_id=payload.partner_id,
            actor_id=current_user.id,
            notification_type=NotificationType.PLAN_SHARED,
            payload={
                "share_id": str(share.id),
                "daily_plan_id": str(share.daily_plan_id),
            },
        )
        response = await build_sent_share(db, share)
        await db.commit()
        await notification_manager.publish(notification)
        return response
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This plan is already shared with the partner",
        ) from exc


@router.get("/plan-shares/sent", response_model=list[SentPlanShare])
async def list_sent_plan_shares(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> list[SentPlanShare]:
    """Return active shares created by the current user."""

    shares = list(
        (
            await db.scalars(
                select(DailyPlanShare)
                .where(
                    DailyPlanShare.owner_id == current_user.id,
                    DailyPlanShare.deleted_at.is_(None),
                )
                .order_by(DailyPlanShare.created_at.desc())
            )
        ).all()
    )
    return [await build_sent_share(db, share) for share in shares]


@router.delete("/plan-shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_plan_share(
    share_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Revoke one active share created by the current user."""

    share = await db.scalar(
        select(DailyPlanShare).where(
            DailyPlanShare.id == share_id,
            DailyPlanShare.owner_id == current_user.id,
            DailyPlanShare.deleted_at.is_(None),
        )
    )
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    share.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/shared-plans", response_model=list[ReceivedSharedPlan])
async def list_received_shared_plans(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> list[ReceivedSharedPlan]:
    """Return plans currently shared with the authenticated partner."""

    shares = list(
        (
            await db.scalars(
                select(DailyPlanShare)
                .join(DailyPlan, DailyPlan.id == DailyPlanShare.daily_plan_id)
                .where(
                    DailyPlanShare.partner_id == current_user.id,
                    DailyPlanShare.deleted_at.is_(None),
                    DailyPlan.deleted_at.is_(None),
                )
                .order_by(DailyPlan.plan_date.desc())
            )
        ).all()
    )
    visible: list[ReceivedSharedPlan] = []
    for share in shares:
        try:
            await require_active_partnership(db, share.owner_id, current_user.id)
        except HTTPException:
            continue
        visible.append(await build_received_shared_plan(db, share))
    return visible


@router.post(
    "/plan-shares/{share_id}/encouragements",
    response_model=EncouragementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_encouragement(
    share_id: UUID,
    payload: EncouragementCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Encouragement:
    """Send a fixed-form encouragement to the owner of a received plan."""

    share = await get_received_share(db, current_user.id, share_id)
    encouragement = Encouragement(
        share_id=share.id,
        sender_id=current_user.id,
        receiver_id=share.owner_id,
        encouragement_type=payload.encouragement_type,
    )
    db.add(encouragement)
    await db.flush()
    await db.refresh(encouragement)
    notification = await create_notification(
        db,
        user_id=share.owner_id,
        actor_id=current_user.id,
        notification_type=NotificationType.ENCOURAGEMENT,
        payload={
            "share_id": str(share.id),
            "encouragement_type": payload.encouragement_type.value,
        },
    )
    await db.commit()
    await notification_manager.publish(notification)
    return encouragement
