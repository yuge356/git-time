"""Environment-based application configuration."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "Time Budget Learning Tracker API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "development-secret-key-change-before-production"
    access_token_expire_minutes: int = Field(default=720, ge=5, le=10_080)
    jwt_algorithm: str = "HS256"
    database_url: str = (
        "postgresql+asyncpg://time_budget_app:time_budget_dev_password"
        "@localhost:5432/time_budget_tracker"
    )
    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        """Reject short signing keys that make JWT signatures weak."""

        if len(value) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""

    return Settings()


settings = get_settings()

