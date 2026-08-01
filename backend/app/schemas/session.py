"""Study-session synchronization schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.session import SessionStatus


class SessionStateUpsert(BaseModel):
    """Complete client snapshot used for online writes and offline replay."""

    task_id: UUID | None = None
    daily_plan_item_id: UUID | None = None
    client_id: UUID
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int = Field(ge=0, le=315_360_000)
    last_resumed_at: datetime | None = None
    client_updated_at: datetime

    @field_validator(
        "started_at",
        "ended_at",
        "last_resumed_at",
        "client_updated_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous local timestamps from custom or older clients."""

        if value is not None and value.tzinfo is None:
            raise ValueError("Session timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_state_timestamps(self) -> "SessionStateUpsert":
        """Require the timestamp shape implied by each timer state."""

        if self.task_id is None and self.daily_plan_item_id is None:
            raise ValueError("A session must reference a task or daily plan item")
        if self.status == SessionStatus.RUNNING:
            if self.last_resumed_at is None or self.ended_at is not None:
                raise ValueError("Running sessions require last_resumed_at and no ended_at")
        elif self.status == SessionStatus.PAUSED:
            if self.last_resumed_at is not None or self.ended_at is not None:
                raise ValueError("Paused sessions cannot have active or ending timestamps")
        elif self.status == SessionStatus.COMPLETED:
            if self.last_resumed_at is not None or self.ended_at is None:
                raise ValueError("Completed sessions require ended_at and no last_resumed_at")

        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("Session cannot end before it starts")
        if self.last_resumed_at is not None and self.last_resumed_at < self.started_at:
            raise ValueError("Session cannot resume before it starts")
        if self.client_updated_at < self.started_at:
            raise ValueError("Client update time cannot precede session start")
        return self


class SessionResponse(BaseModel):
    """Stored session state returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    task_id: UUID | None
    daily_plan_item_id: UUID | None
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    last_resumed_at: datetime | None
    client_id: UUID
    client_updated_at: datetime
    created_at: datetime
    updated_at: datetime
