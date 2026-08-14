"""Notification center HTTP endpoints and authenticated WebSocket."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DatabaseSession, authenticate_access_token
from app.core.config import settings
from app.core.security import InvalidTokenError
from app.models.sharing import Notification
from app.schemas.sharing import NotificationResponse, UnreadCount
from app.services.notifications import notification_manager

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    db: DatabaseSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Notification]:
    """Return the current user's most recent notifications."""

    return list(
        (
            await db.scalars(
                select(Notification)
                .where(Notification.user_id == current_user.id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
        ).all()
    )


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def unread_notification_count(
    db: DatabaseSession,
    current_user: CurrentUser,
) -> UnreadCount:
    """Return the notification badge count."""

    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    )
    return UnreadCount(count=count or 0)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Notification:
    """Mark one owned notification as read."""

    notification = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    if notification is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)
    return notification


@router.websocket("/ws/notifications")
async def notification_socket(
    websocket: WebSocket,
    db: DatabaseSession,
    token: Annotated[str, Query(min_length=1)],
) -> None:
    """Push durable notification rows to an authenticated browser."""

    origin = websocket.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        await websocket.close(code=1008)
        return
    try:
        user = await authenticate_access_token(db, token)
    except InvalidTokenError:
        await websocket.close(code=1008)
        return

    await notification_manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(user.id, websocket)
