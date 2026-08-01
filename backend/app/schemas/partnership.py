"""Public profile, partnership and block API schemas."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.partnership import PartnershipStatus


class PublicProfile(BaseModel):
    """Profile fields visible during search and to partners."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    avatar_url: str | None
    bio: str | None


class RelationshipDirection(StrEnum):
    """The authenticated user's role in an invitation."""

    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    PARTNER = "PARTNER"


class UserSearchResult(PublicProfile):
    """Search result with the current active relationship, if any."""

    partnership_id: UUID | None = None
    partnership_status: PartnershipStatus | None = None
    direction: RelationshipDirection | None = None


class PartnershipInvite(BaseModel):
    """Invite one searchable, unblocked user."""

    addressee_id: UUID


class PartnershipDecision(BaseModel):
    """Accept or decline an incoming request."""

    accept: bool


class PartnershipResponse(BaseModel):
    """Relationship row normalized around the authenticated user."""

    id: UUID
    status: PartnershipStatus
    direction: RelationshipDirection
    partner: PublicProfile
    created_at: datetime
    responded_at: datetime | None


class UserBlockResponse(BaseModel):
    """A user blocked by the authenticated user."""

    id: UUID
    blocked_user: PublicProfile
    created_at: datetime
