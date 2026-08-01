"""Persistent notification creation and in-process WebSocket delivery."""

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharing import Notification, NotificationType
from app.schemas.sharing import NotificationResponse


class NotificationConnectionManager:
    """Track live notification sockets by authenticated user."""

    def __init__(self) -> None:
        self.connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[user_id].add(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        sockets = self.connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self.connections.pop(user_id, None)

    async def publish(self, notification: Notification) -> None:
        """Best-effort delivery; the database remains the source of truth."""

        message = NotificationResponse.model_validate(notification).model_dump(
            mode="json"
        )
        stale: list[WebSocket] = []
        for websocket in tuple(self.connections.get(notification.user_id, set())):
            try:
                await websocket.send_json(message)
            except Exception:  # pragma: no cover - depends on socket timing
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(notification.user_id, websocket)


notification_manager = NotificationConnectionManager()


async def create_notification(
    db: AsyncSession,
    *,
    user_id: UUID,
    actor_id: UUID | None,
    notification_type: NotificationType,
    payload: dict[str, str],
) -> Notification:
    """Stage and flush one durable notification in the caller's transaction."""

    notification = Notification(
        user_id=user_id,
        actor_id=actor_id,
        notification_type=notification_type,
        payload=payload,
    )
    db.add(notification)
    await db.flush()
    return notification
