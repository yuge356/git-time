"""Reproduce the analytics summary build against the configured database."""

import asyncio
import sys
import traceback
from datetime import date, timedelta

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.session import SessionFactory, set_request_identity, set_service_context
from app.models.profile import Profile
from app.models.user import User
from app.services.analytics import (
    build_analytics_summary,
    build_dashboard_summaries,
    build_hourly_focus,
    build_task_daily_series,
)


async def main() -> None:
    async with SessionFactory() as db:
        await set_service_context(db)
        users = list((await db.scalars(select(User).options(joinedload(User.profile)).limit(5))).all())
        print("users:", [(str(u.id), u.email) for u in users])
        if not users:
            return
        user = users[0]
        tz = user.profile.timezone
        print("user:", user.id, "timezone:", tz)

    async with SessionFactory() as db:
        await set_request_identity(db, user.id)
        today = date.today()
        date_from = today - timedelta(days=9)
        for label, coro in [
            ("summary", build_analytics_summary(db, user.id, tz, date_from, today)),
            ("hourly", build_hourly_focus(db, user.id, tz, today)),
            ("task-daily", build_task_daily_series(db, user.id, tz, date_from, today)),
            ("dashboard", build_dashboard_summaries(db, user.id, tz, date_from, today, today)),
            ("checkin-like", build_dashboard_summaries(db, user.id, tz, date_from, today, today)),
        ]:
            try:
                result = await coro
                if label == "dashboard":
                    print("dashboard OK range:", result[0].total_learning_seconds, "today:", result[1].total_learning_seconds)
                elif label == "summary":
                    print("summary OK total:", result.total_learning_seconds, "trend points:", len(result.daily_trend), "dist:", len(result.task_distribution))
                else:
                    print(f"{label} OK")
            except Exception:
                print(f"--- {label} FAILED ---")
                traceback.print_exc()


asyncio.run(main())
