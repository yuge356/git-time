"""Shared in-memory API test fixtures."""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db, get_service_db
from app.main import app


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
async def client() -> AsyncIterator[AsyncClient]:
    """Run API tests against a fresh SQLite database.

    PostgreSQL-specific RLS is defined and reviewed in the Alembic migration;
    API behavior uses SQLite here so the fast test suite has no external service.
    """

    test_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

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
    await test_engine.dispose()
