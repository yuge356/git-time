"""User profile request and response schemas."""

import re
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")


class ProfileFields(BaseModel):
    """Fields shared by registration and profile editing."""

    username: str = Field(min_length=3, max_length=30)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """Keep usernames stable and safe for exact search."""

        normalized = value.strip().lower()
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("Username may only contain letters, numbers and underscores")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """Remove surrounding whitespace without changing the visible name."""

        return value.strip()


class ProfileUpdate(BaseModel):
    """Editable profile fields; omitted values remain unchanged."""

    username: str | None = Field(default=None, min_length=3, max_length=30)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=2048)
    bio: str | None = Field(default=None, max_length=300)
    timezone: str | None = Field(default=None, max_length=64)
    is_searchable: bool | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Username cannot be null")
        normalized = value.strip().lower()
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("Username may only contain letters, numbers and underscores")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Display name cannot be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name cannot be blank")
        return normalized

    @field_validator("avatar_url", "bio")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Timezone cannot be null")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone name") from exc
        return value


class ProfileResponse(BaseModel):
    """Complete profile returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    avatar_url: str | None
    bio: str | None
    timezone: str
    is_searchable: bool
    created_at: datetime
    updated_at: datetime
