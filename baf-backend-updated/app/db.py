from typing import Optional
import json

import asyncpg

pool: Optional[asyncpg.Pool] = None


async def _init(conn: asyncpg.Connection):
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def connect(dsn: str):
    global pool
    # Works with serverless Postgres (Neon): warm connection, idle ones closed before Neon suspends, PgBouncer safe
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, init=_init, statement_cache_size=0,
        max_inactive_connection_lifetime=240, timeout=30, command_timeout=30,
    )


async def close():
    if pool:
        await pool.close()
