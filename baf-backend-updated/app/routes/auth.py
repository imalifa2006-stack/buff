import hmac

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from .. import db
from ..config import settings
from ..deps import create_session, current_user
from ..schemas import LoginIn, RegisterIn, TgAuth
from ..security import hash_password, hash_token, verify_password
from ..telegram import InvalidInitData, verify_init_data

router = APIRouter(prefix="/api/auth")


def _tg(init_data: str) -> dict:
    if settings.dev_mode and init_data.startswith("dev:"):
        _, uid, uname, first = init_data.split(":", 3)
        return {"id": int(uid), "username": uname, "first_name": first}
    try:
        return verify_init_data(init_data, settings.bot_token, settings.init_data_max_age)
    except InvalidInitData:
        raise HTTPException(401, "invalid_init_data")


def _public(u) -> dict:
    return {"username": u["username"], "field": u["field"], "grade": u["grade"], "first_name": u["first_name"], "role": u["role"], "status": u["status"]}


@router.post("/telegram")
async def telegram_login(body: TgAuth, request: Request):
    """Called every time the Mini App opens. Known user -> session. Unknown -> tells the app to show registration."""
    tg = _tg(body.init_data)
    async with db.pool.acquire() as c:
        u = await c.fetchrow("SELECT * FROM users WHERE telegram_id = $1", tg["id"])
        if u:
            if u["status"] in ("blocked", "rejected"):
                raise HTTPException(403, "blocked")
            await c.execute(
                "UPDATE users SET tg_username = $2, first_name = $3, last_name = $4, last_seen_at = now() WHERE id = $1",
                u["id"], tg.get("username"), tg.get("first_name", u["first_name"]), tg.get("last_name"),
            )
            return {"registered": True, "token": await create_session(c, u["id"], request), "user": _public(u)}
        uname = tg.get("username")
        allowed = settings.registration_mode != "list" or (bool(uname) and bool(await c.fetchval(
            "SELECT 1 FROM allowed_students WHERE telegram_username = $1 AND used = false", uname)))
        return {"registered": False, "can_register": allowed, "needs_code": settings.registration_mode == "code"}


@router.post("/register")
async def register(body: RegisterIn, request: Request):
    tg = _tg(body.init_data)
    uname = tg.get("username")
    async with db.pool.acquire() as c:
        async with c.transaction():
            row = None
            if body.role == "advisor":
                if not uname or uname.casefold() != body.username.casefold():
                    raise HTTPException(403, "advisor_telegram_username_mismatch")
                verified = await c.fetchval("SELECT 1 FROM verified_advisors WHERE username=$1 AND active=true", body.username)
                if not verified:
                    raise HTTPException(403, "advisor_not_verified")
            if settings.registration_mode == "list" and body.role == "student":
                row = await c.fetchrow(
                    "SELECT id FROM allowed_students WHERE telegram_username = $1 AND used = false FOR UPDATE", uname
                ) if uname else None
                if not row:
                    raise HTTPException(403, "not_allowed")
            elif settings.registration_mode == "code":
                if not (settings.invite_code and hmac.compare_digest(body.invite_code or "", settings.invite_code)):
                    raise HTTPException(403, "bad_code")
            try:
                u = await c.fetchrow(
                    "INSERT INTO users (telegram_id, tg_username, first_name, last_name, username, password_hash, field, grade, role, last_seen_at) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, now()) RETURNING *",
                    tg["id"], uname, tg.get("first_name", ""), tg.get("last_name"), body.username,
                    hash_password(body.password) if body.password else None, body.field, body.grade, body.role,
                )
            except asyncpg.UniqueViolationError as e:
                raise HTTPException(409, "username_taken" if "username" in (e.constraint_name or "") else "already_registered")
            if body.role == "student":
                if not body.advisor_username:
                    raise HTTPException(422, "advisor_required")
                advisor = await c.fetchrow("SELECT id, status FROM users WHERE username=$1 AND role='advisor'", body.advisor_username)
                if not advisor or advisor["status"] != "approved" or not await c.fetchval("SELECT 1 FROM verified_advisors WHERE username=$1 AND active=true", body.advisor_username):
                    raise HTTPException(403, "invalid_advisor")
                await c.execute("UPDATE users SET advisor_id=$2, status='pending' WHERE id=$1", u["id"], advisor["id"])
                u = await c.fetchrow("SELECT * FROM users WHERE id=$1", u["id"])
            if row:
                await c.execute("UPDATE allowed_students SET used = true WHERE id = $1", row["id"])
            token = await create_session(c, u["id"], request)
    return {"registered": True, "token": token, "user": _public(u)}


@router.post("/login")
async def password_login(body: LoginIn, request: Request):
    """For logging in outside Telegram (regular website). TODO: add rate limiting (e.g. slowapi) before production."""
    if settings.admin_username and hmac.compare_digest(body.username.strip(), settings.admin_username):
        if not settings.admin_password or not hmac.compare_digest(body.password, settings.admin_password):
            raise HTTPException(401, "invalid_credentials")
        async with db.pool.acquire() as c:
            admin = await c.fetchrow("SELECT * FROM users WHERE username=$1 AND role='admin'", settings.admin_username)
            if not admin:
                raise HTTPException(503, "admin_not_initialized")
            return {"token": await create_session(c, admin["id"], request), "user": _public(admin)}
    async with db.pool.acquire() as c:
        u = await c.fetchrow("SELECT * FROM users WHERE username = $1", body.username.strip())
        if not verify_password(u["password_hash"] if u else None, body.password) or u["status"] in ("blocked", "rejected"):
            raise HTTPException(401, "invalid_credentials")
        return {"token": await create_session(c, u["id"], request), "user": _public(u)}


@router.post("/logout")
async def logout(request: Request, user=Depends(current_user)):
    async with db.pool.acquire() as c:
        await c.execute("UPDATE sessions SET revoked_at = now() WHERE id = $1", user["sid"])
    return {"ok": True}


@router.get("/me")
async def me(user=Depends(current_user)):
    return _public(user)
