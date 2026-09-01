"""Inspect who is holding connections on the configured database."""

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import text

from app.db.session import SessionFactory, engine, set_service_context


async def main() -> None:
    async with SessionFactory() as db:
        await set_service_context(db)
        rows = (
            await db.execute(
                text(
                    """
                    SELECT count(*) AS total,
                           count(*) FILTER (WHERE state = 'idle') AS idle,
                           count(*) FILTER (WHERE state = 'active') AS active
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    """
                )
            )
        ).one()
        print("connections total/idle/active:", rows)
        detail = (
            await db.execute(
                text(
                    """
                    SELECT state, count(*), string_agg(DISTINCT coalesce(application_name, '?'), ', ')
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY state
                    """
                )
            )
        ).all()
        for row in detail:
            print("  state:", row)
    print("pool size:", engine.pool.size())
    print("checked out:", engine.pool.checkedout())


asyncio.run(main())
