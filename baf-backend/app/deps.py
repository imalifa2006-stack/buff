from typing import Optional
from fastapi import Header, HTTPException, Request

from . import db
from .config import settings
from .security import hash_token, new_token


async def create_session(conn, user_id: int, request: Request) -> str:
    token = new_token()
    await conn.execute(
        "INSERT INTO sessions (user_id, token_hash, user_agent, expires_at) "
        "VALUES ($1, $2, $3, now() + make_interval(days => $4))",
        user_id, hash_token(token), request.headers.get("user-agent", "")[:200], settings.session_days,
    )
    return token


async def current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "unauthorized")
    th = hash_token(authorization[7:].strip())
    async with db.pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT u.id, u.username, u.field, u.grade, u.first_name, s.id AS sid, "
            "       (s.last_used_at < now() - interval '1 hour') AS stale "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = $1 AND s.revoked_at IS NULL AND s.expires_at > now() AND u.status = 'approved'",
            th,
        )
        if not row:
            raise HTTPException(401, "unauthorized")
        if row["stale"]:  # sliding expiry: extend at most once per hour
            await c.execute(
                "UPDATE sessions SET last_used_at = now(), expires_at = now() + make_interval(days => $2) WHERE id = $1",
                row["sid"], settings.session_days,
            )
    return dict(row)
