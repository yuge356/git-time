"""Transient database failures must reach the client as retryable errors."""

from collections.abc import AsyncIterator

from httpx import AsyncClient
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.requests import Request

from app.db.session import get_db
from app.main import app, database_connection_handler
from tests.test_tasks_api import auth_header, register_user


def _failing_dependency(error: Exception):
    async def dependency() -> AsyncIterator[None]:
        raise error
        yield  # pragma: no cover - unreachable, keeps this a generator

    return dependency


async def test_pool_timeout_answers_with_retryable_503(client: AsyncClient) -> None:
    """A saturated pool is a capacity problem, not a broken request."""

    token, _ = await register_user(client, "pool_timeout")
    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = _failing_dependency(
        SQLAlchemyTimeoutError("QueuePool limit of size 2 overflow 2 reached")
    )
    try:
        response = await client.get("/api/v1/tasks", headers=auth_header(token))
    finally:
        app.dependency_overrides[get_db] = previous

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert "稍后重试" in response.json()["detail"]


async def test_invalidated_connection_answers_with_retryable_503(client: AsyncClient) -> None:
    """A connection the pooler reaped mid-request should be replayed."""

    token, _ = await register_user(client, "dropped_connection")
    dropped = OperationalError("SELECT 1", {}, Exception("connection was closed"))
    dropped.connection_invalidated = True
    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = _failing_dependency(dropped)
    try:
        response = await client.get("/api/v1/tasks", headers=auth_header(token))
    finally:
        app.dependency_overrides[get_db] = previous

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"


async def test_rejected_statement_still_answers_500() -> None:
    """A query the database understood and refused is a real server error.

    Only an invalidated connection is transient; everything else must keep
    its 500 so a genuine bug is not hidden behind an endless client retry.
    """

    rejected = DBAPIError("SELECT bad", {}, Exception("syntax error"))
    assert rejected.connection_invalidated is False

    response = await database_connection_handler(
        Request({"type": "http", "method": "GET", "path": "/", "headers": []}),
        rejected,
    )
    assert response.status_code == 500
    assert "Retry-After" not in response.headers
