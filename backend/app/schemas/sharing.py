"""Plan sharing, encouragement and notification API schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.daily_plan import DailyPlanItemStatus
from app.models.sharing import EncouragementType, NotificationType
from app.schemas.partnership import PublicProfile


class PlanShareCreate(BaseModel):
    """Share one owned daily plan with one accepted partner."""

    daily_plan_id: UUID
    partner_id: UUID
    share_duration: bool = False


class SentPlanShare(BaseModel):
    """Share settings visible to the plan owner."""

    id: UUID
    daily_plan_id: UUID
    plan_date: date
    partner: PublicProfile
    share_duration: bool
    created_at: datetime


class SharedPlanItem(BaseModel):
    """Progress visible to a partner; duration fields honor owner consent."""

    id: UUID
    title: str
    status: DailyPlanItemStatus
    estimated_seconds: int | None
    actual_seconds: int | None


class ReceivedSharedPlan(BaseModel):
    """A partner-facing, read-only daily plan."""

    share_id: UUID
    daily_plan_id: UUID
    plan_date: date
    owner: PublicProfile
    share_duration: bool
    total_items: int
    completed_items: int
    items: list[SharedPlanItem]
    created_at: datetime


class EncouragementCreate(BaseModel):
    """Send one value from the fixed encouragement list."""

    encouragement_type: EncouragementType


class EncouragementResponse(BaseModel):
    """Persisted fixed encouragement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    share_id: UUID
    sender_id: UUID
    receiver_id: UUID
    encouragement_type: EncouragementType
    created_at: datetime


class NotificationResponse(BaseModel):
    """One notification center entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    actor_id: UUID | None
    notification_type: NotificationType
    payload: dict[str, str]
    read_at: datetime | None
    created_at: datetime


class UnreadCount(BaseModel):
    """Unread notification badge value."""

    count: int
