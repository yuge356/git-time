"""Environment-based application configuration."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
DATABASE_ROLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def escape_alembic_config_value(value: str) -> str:
    """Escape percent signs before storing a value in Alembic's ConfigParser."""

    return value.replace("%", "%%")


def resolve_database_url(value: str) -> str:
    """Anchor relative SQLite files to ``backend/`` instead of the shell cwd."""

    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if not value.startswith(prefix):
            continue
        raw_path = value.removeprefix(prefix)
        if raw_path == ":memory:":
            return value
        database_path = Path(raw_path)
        if database_path.is_absolute():
            return value
        return f"{prefix}{(BACKEND_DIR / database_path).resolve().as_posix()}"
    return value


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "DayFlow API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "development-secret-key-change-before-production"
    access_token_expire_minutes: int = Field(default=720, ge=5, le=10_080)
    jwt_algorithm: str = "HS256"
    auth_provider: Literal["local", "supabase"] = "local"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    database_url: str = (
        "postgresql+asyncpg://time_budget_app:time_budget_dev_password"
        "@localhost:5432/time_budget_tracker"
    )
    database_role: str | None = None
    cors_origins: list[str] = ["http://localhost:5174"]

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Prevent different launch directories from creating different databases."""

        return resolve_database_url(value)

    @field_validator("database_role")
    @classmethod
    def validate_database_role(cls, value: str | None) -> str | None:
        """Allow safe PostgreSQL identifiers in the runtime SET ROLE hook."""

        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not DATABASE_ROLE_PATTERN.fullmatch(normalized):
            raise ValueError("APP_DATABASE_ROLE must be a simple PostgreSQL role name")
        return normalized

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Reject short signing keys that make JWT signatures weak."""

        if len(value) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_supabase_settings(self) -> "Settings":
        """Require public Supabase credentials when hosted auth is enabled."""

        if self.auth_provider == "supabase":
            if not self.supabase_url or not self.supabase_publishable_key:
                raise ValueError(
                    "APP_SUPABASE_URL and APP_SUPABASE_PUBLISHABLE_KEY are required "
                    "when APP_AUTH_PROVIDER=supabase"
                )
            self.supabase_url = self.supabase_url.rstrip("/")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""

    return Settings()


settings = get_settings()
