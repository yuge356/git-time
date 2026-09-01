import asyncio, ssl
import asyncpg

URL = "postgresql://postgres.cdaingelaivvffgpejjy:UNs6a6dS3St89Ms7@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

async def main():
    conn = await asyncpg.connect(URL, statement_cache_size=0, timeout=15)
    print("connected tx mode")
    await conn.execute('SET ROLE "dayflow_app"')
    print("role ok", await conn.fetchval("select current_user"))
    import uuid
    uid = "9932b20f-5609-49ce-818b-3ea2a9f9258c"
    await conn.execute("SELECT set_config('app.current_user_id', $1, true)", uid)
    rows = await conn.fetch("select count(*) from tasks")
    print("tasks visible with rls:", rows[0][0])
    await conn.close()

asyncio.run(main())
