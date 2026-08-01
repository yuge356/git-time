"""Search, partnership invitation and user-block endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.partnership import Partnership, PartnershipStatus, UserBlock
from app.models.profile import Profile
from app.models.sharing import DailyPlanShare, NotificationType
from app.schemas.partnership import (
    PartnershipDecision,
    PartnershipInvite,
    PartnershipResponse,
    PublicProfile,
    RelationshipDirection,
    UserBlockResponse,
    UserSearchResult,
)
from app.services.notifications import create_notification, notification_manager
from app.services.partnerships import (
    close_partnership,
    get_owned_partnership,
    get_public_profile,
    partnership_pair_key,
    to_partnership_response,
    users_are_blocked,
)

router = APIRouter(tags=["partnerships"])


@router.get("/users/search", response_model=list[UserSearchResult])
async def search_users(
    db: DatabaseSession,
    current_user: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=80)],
) -> list[UserSearchResult]:
    """Search discoverable profiles while excluding mutual blocks."""

    normalized = q.strip()
    if not normalized:
        return []
    profiles = list(
        (
            await db.scalars(
                select(Profile)
                .where(
                    Profile.id != current_user.id,
                    Profile.is_searchable.is_(True),
                    or_(
                        Profile.username.ilike(f"%{normalized}%"),
                        Profile.display_name.ilike(f"%{normalized}%"),
                    ),
                )
                .order_by(Profile.username)
                .limit(20)
            )
        ).all()
    )
    results: list[UserSearchResult] = []
    for profile in profiles:
        if await users_are_blocked(db, current_user.id, profile.id):
            continue
        relationship = await db.scalar(
            select(Partnership).where(
                Partnership.pair_key
                == partnership_pair_key(current_user.id, profile.id),
                Partnership.deleted_at.is_(None),
            )
        )
        direction = None
        if relationship is not None:
            direction = (
                RelationshipDirection.PARTNER
                if relationship.status == PartnershipStatus.ACCEPTED
                else RelationshipDirection.OUTGOING
                if relationship.requester_id == current_user.id
                else RelationshipDirection.INCOMING
            )
        results.append(
            UserSearchResult(
                **PublicProfile.model_validate(profile).model_dump(),
                partnership_id=relationship.id if relationship else None,
                partnership_status=relationship.status if relationship else None,
                direction=direction,
            )
        )
    return results


@router.get("/partnerships", response_model=list[PartnershipResponse])
async def list_partnerships(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> list[PartnershipResponse]:
    """Return pending invitations and accepted partners."""

    relationships = list(
        (
            await db.scalars(
                select(Partnership)
                .where(
                    or_(
                        Partnership.requester_id == current_user.id,
                        Partnership.addressee_id == current_user.id,
                    ),
                    Partnership.deleted_at.is_(None),
                )
                .order_by(Partnership.created_at.desc())
            )
        ).all()
    )
    return [
        await to_partnership_response(db, relationship, current_user.id)
        for relationship in relationships
    ]


@router.post(
    "/partnerships/invitations",
    response_model=PartnershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_partner(
    payload: PartnershipInvite,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> PartnershipResponse:
    """Send one pending invitation to a searchable, unblocked user."""

    if payload.addressee_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot invite yourself",
        )
    profile = await get_public_profile(db, payload.addressee_id)
    if not profile.is_searchable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if await users_are_blocked(db, current_user.id, payload.addressee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user is unavailable",
        )
    relationship = Partnership(
        requester_id=current_user.id,
        addressee_id=payload.addressee_id,
        pair_key=partnership_pair_key(current_user.id, payload.addressee_id),
    )
    db.add(relationship)
    try:
        await db.flush()
        await db.refresh(relationship)
        notification = await create_notification(
            db,
            user_id=payload.addressee_id,
            actor_id=current_user.id,
            notification_type=NotificationType.PARTNER_INVITE,
            payload={"partnership_id": str(relationship.id)},
        )
        response = await to_partnership_response(db, relationship, current_user.id)
        await db.commit()
        await notification_manager.publish(notification)
        return response
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A partnership or invitation already exists",
        ) from exc


@router.patch(
    "/partnerships/{partnership_id}",
    response_model=PartnershipResponse,
)
async def decide_partnership(
    partnership_id: UUID,
    payload: PartnershipDecision,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> PartnershipResponse:
    """Accept or decline an incoming pending invitation."""

    relationship = await get_owned_partnership(db, current_user.id, partnership_id)
    if relationship.addressee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the invitation recipient can respond",
        )
    if relationship.status != PartnershipStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invitation has already been answered",
        )
    if await users_are_blocked(
        db,
        relationship.requester_id,
        relationship.addressee_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user is unavailable",
        )

    relationship.status = (
        PartnershipStatus.ACCEPTED if payload.accept else PartnershipStatus.DECLINED
    )
    relationship.responded_at = datetime.now(UTC)
    notification = None
    if payload.accept:
        notification = await create_notification(
            db,
            user_id=relationship.requester_id,
            actor_id=current_user.id,
            notification_type=NotificationType.PARTNER_ACCEPTED,
            payload={"partnership_id": str(relationship.id)},
        )
    response = await to_partnership_response(db, relationship, current_user.id)
    if not payload.accept:
        close_partnership(relationship)
    await db.commit()
    if notification is not None:
        await notification_manager.publish(notification)
    return response


@router.delete(
    "/partnerships/{partnership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_partnership(
    partnership_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Cancel a pending invitation or remove an accepted partner."""

    relationship = await get_owned_partnership(db, current_user.id, partnership_id)
    close_partnership(relationship)
    shares = list(
        (
            await db.scalars(
                select(DailyPlanShare).where(
                    or_(
                        (DailyPlanShare.owner_id == relationship.requester_id)
                        & (DailyPlanShare.partner_id == relationship.addressee_id),
                        (DailyPlanShare.owner_id == relationship.addressee_id)
                        & (DailyPlanShare.partner_id == relationship.requester_id),
                    ),
                    DailyPlanShare.deleted_at.is_(None),
                )
            )
        ).all()
    )
    closed_at = datetime.now(UTC)
    for share in shares:
        share.deleted_at = closed_at
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/blocks", response_model=list[UserBlockResponse])
async def list_blocks(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> list[UserBlockResponse]:
    """Return users blocked by the authenticated user."""

    blocks = list(
        (
            await db.scalars(
                select(UserBlock)
                .where(UserBlock.blocker_id == current_user.id)
                .order_by(UserBlock.created_at.desc())
            )
        ).all()
    )
    return [
        UserBlockResponse(
            id=block.id,
            blocked_user=PublicProfile.model_validate(
                await get_public_profile(db, block.blocked_id)
            ),
            created_at=block.created_at,
        )
        for block in blocks
    ]


@router.post(
    "/blocks/{blocked_id}",
    response_model=UserBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def block_user(
    blocked_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> UserBlockResponse:
    """Block a user and close every active relationship between the pair."""

    if blocked_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot block yourself",
        )
    profile = await get_public_profile(db, blocked_id)
    block = UserBlock(blocker_id=current_user.id, blocked_id=blocked_id)
    db.add(block)
    relationships = list(
        (
            await db.scalars(
                select(Partnership).where(
                    Partnership.pair_key == partnership_pair_key(current_user.id, blocked_id),
                    Partnership.deleted_at.is_(None),
                )
            )
        ).all()
    )
    for relationship in relationships:
        close_partnership(relationship)
    shares = list(
        (
            await db.scalars(
                select(DailyPlanShare).where(
                    or_(
                        (DailyPlanShare.owner_id == current_user.id)
                        & (DailyPlanShare.partner_id == blocked_id),
                        (DailyPlanShare.owner_id == blocked_id)
                        & (DailyPlanShare.partner_id == current_user.id),
                    ),
                    DailyPlanShare.deleted_at.is_(None),
                )
            )
        ).all()
    )
    closed_at = datetime.now(UTC)
    for share in shares:
        share.deleted_at = closed_at
    try:
        await db.flush()
        await db.refresh(block)
        response = UserBlockResponse(
            id=block.id,
            blocked_user=PublicProfile.model_validate(profile),
            created_at=block.created_at,
        )
        await db.commit()
        return response
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is already blocked",
        ) from exc


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    block_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Remove one block created by the authenticated user."""

    block = await db.scalar(
        select(UserBlock).where(
            UserBlock.id == block_id,
            UserBlock.blocker_id == current_user.id,
        )
    )
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block not found")
    await db.delete(block)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
