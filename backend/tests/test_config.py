"""Configuration path stability and Alembic URL tests."""

from configparser import ConfigParser

from app.core.config import (
    BACKEND_DIR,
    escape_alembic_config_value,
    resolve_database_url,
)


def test_relative_sqlite_database_is_anchored_to_backend() -> None:
    resolved = resolve_database_url("sqlite+aiosqlite:///./stable.db")

    assert resolved == (
        "sqlite+aiosqlite:///"
        f"{(BACKEND_DIR / 'stable.db').resolve().as_posix()}"
    )


def test_non_sqlite_database_url_is_unchanged() -> None:
    url = "postgresql+asyncpg://app:secret@localhost:5432/tracker"

    assert resolve_database_url(url) == url


def test_alembic_config_accepts_percent_encoded_database_password() -> None:
    database_url = (
        "postgresql+asyncpg://postgres.project-ref:"
        "password%40with%25symbols@pooler.example.com:5432/postgres"
    )
    parser = ConfigParser()
    parser.add_section("alembic")

    parser.set(
        "alembic",
        "sqlalchemy.url",
        escape_alembic_config_value(database_url),
    )

    assert parser.get("alembic", "sqlalchemy.url") == database_url
