"""FastAPI application factory and process entry point."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine

logger = logging.getLogger("app.request")

# The managed database lives behind a remote connection pooler that reaps idle
# server connections after a few minutes. A periodic cheap ping keeps the
# pooled connections warm so the first query of a page load does not pay a
# full remote TLS handshake. Only as many connections as the pool actually
# holds are warmed -- on Supabase's session-mode pooler every open connection
# occupies one of the project's handful of client slots.
KEEPALIVE_CONNECTIONS = max(1, min(2, settings.database_pool_size))


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
        await asyncio.sleep(settings.database_keepalive_interval_seconds)
        try:
            await _ping_connections(KEEPALIVE_CONNECTIONS)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A failed ping is harmless: pool_pre_ping rebuilds the connection
            # on the next real checkout.
            continue


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Keep warm pooled connections and dispose pools cleanly on stop."""

    keepalive_task: asyncio.Task[None] | None = None
    if settings.database_keepalive_enabled:
        keepalive_task = asyncio.create_task(_database_keepalive())
    try:
        yield
    finally:
        if keepalive_task is not None:
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Log the real cause and answer with an actionable message.

    Without this hook every unhandled failure reached the browser as FastAPI's
    bare "Internal Server Error", which the frontend rendered as "请检查后端
   数据库连接配置" and gave no clue about the actual fault.
    """

    logger.exception("Unhandled error while handling a request")
    reason = str(exc).strip().splitlines()[0][:160] if str(exc).strip() else exc.__class__.__name__
    if not any("\u4e00" <= char <= "\u9fff" for char in reason):
        reason = f"{exc.__class__.__name__}: {reason}"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"服务器处理请求时出错：{reason}"},
    )


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Report readiness only after the configured application schema responds.

    A database failure surfaces as 503 with a short diagnostic instead of an
    opaque 500, so the Vercel logs and the browser can tell at a glance
    that the backend cannot reach the database.
    """

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT node_type FROM tasks LIMIT 1"))
    except Exception as exc:  # noqa: BLE001 — health endpoint must surface any failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": "error",
                "detail": str(exc).strip()[:200] or exc.__class__.__name__,
            },
        ) from exc
    return {"status": "ok", "database": "ok"}
