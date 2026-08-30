"""Asynchronous database sessions and PostgreSQL RLS request context."""

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# pool_pre_ping is deliberately off: against the remote transaction-pooling
# endpoint every checkout re-opened a TLS connection (~0.5s), which dominated
# analytics page loads. The app-level keepalive in app.main pings the pool on
# a short interval instead, so idle connections stay healthy.
engine = create_async_engine(settings.database_url)
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
