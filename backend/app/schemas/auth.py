"""Authentication API schemas."""

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.profile import ProfileFields, ProfileResponse


class RegisterRequest(ProfileFields):
    """New account data."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(BaseModel):
    """Email and password credentials."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class AccountResponse(BaseModel):
    """Authenticated account representation."""

    email: EmailStr
    profile: ProfileResponse


class AuthResponse(BaseModel):
    """Bearer token and the authenticated account."""

    access_token: str
    token_type: str = "bearer"
    user: AccountResponse

