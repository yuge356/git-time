"""Shared in-memory API test fixtures."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db, get_service_db
from app.main import app

# New profiles default to this zone, and every date-scoped endpoint resolves
# "today" in the profile's zone. Tests must use the same clock: plain
# ``date.today()`` follows the machine timezone, so on a host west of the
# profile zone the suite started failing after ~16:00 UTC purely because the
# two disagreed about which day it was.
PROFILE_TIMEZONE = ZoneInfo("Asia/Shanghai")


def profile_today() -> date:
    """Return the date the API considers "today" for a default profile."""

    return datetime.now(UTC).astimezone(PROFILE_TIMEZONE).date()


@pytest_asyncio.fixture(autouse=True)
async def use_local_auth_in_tests() -> AsyncIterator[None]:
    """Keep the deterministic API suite independent from hosted Supabase Auth."""

    previous = settings.auth_provider
    settings.auth_provider = "local"
    try:
        yield
    finally:
        settings.auth_provider = previous


@pytest_asyncio.fixture
async def database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Create one fresh SQLite database and return its session factory."""

    test_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(test_engine, expire_on_commit=False)
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    database: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Open a session on the API's database, for staging rows no endpoint writes."""

    async with database() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    database: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """Run API tests against a fresh SQLite database.

    PostgreSQL-specific RLS is defined and reviewed in the Alembic migration;
    API behavior uses SQLite here so the fast test suite has no external service.
    """

    session_factory = database

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_session
    app.dependency_overrides[get_service_db] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()
