"""Exercise the analytics HTTP endpoints with the auth dependency stubbed out."""

import asyncio
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

import httpx
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.dependencies import get_current_user
from app.db.session import SessionFactory, set_service_context
from app.main import app
from app.models.user import User


async def main() -> None:
    async with SessionFactory() as db:
        await set_service_context(db)
        user = (
            await db.scalars(
                select(User).options(joinedload(User.profile)).where(User.email == "3425438241@qq.com")
            )
        ).one()

    app.dependency_overrides[get_current_user] = lambda: user
    today = date.today()
    date_from = today - timedelta(days=9)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for label, params in [
            (
                "dashboard",
                {"date_from": str(date_from), "date_to": str(today), "today": str(today)},
            ),
            ("summary", {"date_from": str(date_from), "date_to": str(today)}),
            ("hourly-focus", {"day": str(today)}),
            ("task-daily", {"date_from": str(date_from), "date_to": str(today)}),
        ]:
            response = await client.get(f"/api/v1/analytics/{label}", params=params)
            body = response.text
            print(f"{label}: HTTP {response.status_code} {body[:220]}")
    app.dependency_overrides.clear()


asyncio.run(main())
