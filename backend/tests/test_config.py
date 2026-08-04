"""Configuration path stability tests."""

from app.core.config import BACKEND_DIR, resolve_database_url


def test_relative_sqlite_database_is_anchored_to_backend() -> None:
    resolved = resolve_database_url("sqlite+aiosqlite:///./stable.db")

    assert resolved == (
        "sqlite+aiosqlite:///"
        f"{(BACKEND_DIR / 'stable.db').resolve().as_posix()}"
    )


def test_non_sqlite_database_url_is_unchanged() -> None:
    url = "postgresql+asyncpg://app:secret@localhost:5432/tracker"

    assert resolve_database_url(url) == url
