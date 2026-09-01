"""Asynchronous database sessions and PostgreSQL RLS request context."""

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def build_engine_kwargs() -> dict[str, object]:
    """Size the pool for the configured backend.

    Queue-pool options are only applied to server databases: SQLite pools are
    managed internally (StaticPool/NullPool) and reject ``pool_size``.

    ``pool_pre_ping`` stays on. The remote session pooler reaps idle server
    connections, so a pooled handle can go stale between requests; without a
    ping that stale handle is handed to a request and every query fails with
    an opaque 500. The ping is a single cheap round trip on a warm connection.
    """

    url = make_url(settings.database_url)
    kwargs: dict[str, object] = {"pool_pre_ping": settings.database_pool_pre_ping}
    if url.get_backend_name() != "sqlite":
        kwargs.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle=settings.database_pool_recycle_seconds,
            pool_timeout=settings.database_pool_timeout_seconds,
        )
    return kwargs


engine = create_async_engine(settings.database_url, **build_engine_kwargs())
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


if settings.database_role and engine.url.get_backend_name() == "postgresql":

    @event.listens_for(engine.sync_engine, "connect")
    def use_runtime_database_role(dbapi_connection: object, _: object) -> None:
        """Drop pooled application connections to the RLS-enforced role."""

        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute(f'SET ROLE "{settings.database_role}"')
        finally:
            cursor.close()


async def set_request_identity(session: AsyncSession, user_id: UUID) -> None:
    """Set the transaction-local user identifier consumed by RLS policies."""

    if session.bind and session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(user_id)},
        )


async def set_service_context(session: AsyncSession) -> None:
    """Allow trusted authentication endpoints to create or locate accounts."""

    if session.bind and session.bind.dialect.name == "postgresql":
        await session.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))


async def get_db() -> AsyncIterator[AsyncSession]:
    """Provide a request-scoped database session."""

    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_service_db() -> AsyncIterator[AsyncSession]:
    """Provide a session for the small set of trusted auth operations."""

    async with SessionFactory() as session:
        try:
            await set_service_context(session)
            yield session
        except Exception:
            await session.rollback()
            raise
