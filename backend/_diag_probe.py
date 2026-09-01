"""临时诊断脚本：统计 Supabase 数据总量。用完即删。"""

import asyncio

from sqlalchemy import text

from app.db.session import SessionFactory, engine, set_service_context

TABLES = [
    "users",
    "profiles",
    "tasks",
    "sessions",
    "daily_plans",
    "daily_plan_items",
]


async def main() -> None:
    async with SessionFactory() as session:
        await set_service_context(session)
        for table in TABLES:
            count = (await session.execute(text(f"select count(*) from {table}"))).scalar()
            print(f"{table}: {count}")
        rows = (
            await session.execute(
                text(
                    "select owner_id, count(*), min(started_at), max(started_at) "
                    "from sessions group by owner_id order by 2 desc"
                )
            )
        ).all()
        print("--- sessions per owner ---")
        for row in rows:
            print(row)
    await engine.dispose()


asyncio.run(main())
