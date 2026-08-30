"""FastAPI application factory and process entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine

# The managed database lives behind a remote connection pooler that reaps idle
# server connections after a few minutes. With local dev traffic the pooled
# connection is almost always dead by the next request, so every analytics
# page load paid a full remote TLS handshake (~0.7s) before its first query.
# A periodic cheap ping keeps the two pooled connections warm instead — the
# analytics dashboard checks out a second connection to overlap its range
# summaries with the check-in queries.
KEEPALIVE_INTERVAL_SECONDS = 45


async def _ping_connections(count: int) -> None:
    connections = []
    try:
        for _ in range(count):
            connections.append(await engine.connect())
        for connection in connections:
            await connection.execute(text("SELECT 1"))
    finally:
        for connection in connections:
            await connection.close()


async def _database_keepalive() -> None:
    while True:
        await asyncio.sleep(KEEPALIVE_INTERVAL_SECONDS)
        try:
            await _ping_connections(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A failed ping is harmless: pool_pre_ping rebuilds the connection
            # on the next real checkout.
            continue


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Keep warm pooled connections and dispose pools cleanly on stop."""

    keepalive_task = asyncio.create_task(_database_keepalive())
    yield
    keepalive_task.cancel()
    await asyncio.gather(keepalive_task, return_exceptions=True)
    await engine.dispose()


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Report readiness only after the configured application schema responds."""

    async with engine.connect() as connection:
        await connection.execute(text("SELECT node_type FROM tasks LIMIT 1"))
    return {"status": "ok", "database": "ok"}
