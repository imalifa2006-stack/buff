from typing import List, Optional
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..deps import current_user
from ..schemas import ReportIn

router = APIRouter(prefix="/api")
TEHRAN = ZoneInfo("Asia/Tehran")


_SUBJ = {}  # field -> (expires_at, rows); subjects almost never change


async def _subjects_for(c, field):
    hit = _SUBJ.get(field)
    if hit and hit[0] > time.time():
        return hit[1]
    rows = [dict(r) for r in await c.fetch("SELECT id, name FROM subjects WHERE $1 = ANY(fields) ORDER BY id", field)]
    _SUBJ[field] = (time.time() + 600, rows)
    return rows


async def _reports(c, user_id, start, end):
    rows = await c.fetch(
        "SELECT r.report_date, r.sleep_hours, r.mood, r.focus, r.note, "
        "  COALESCE(json_agg(json_build_object('subject_id', s.id, 'subject', s.name, 'minutes', e.minutes, "
        "    'tests', e.tests, 'correct', e.correct, 'wrong', e.wrong) ORDER BY s.id) "
        "    FILTER (WHERE e.id IS NOT NULL), '[]'::json) AS entries "
        "FROM study_reports r "
        "LEFT JOIN report_entries e ON e.report_id = r.id LEFT JOIN subjects s ON s.id = e.subject_id "
        "WHERE r.user_id = $1 AND r.report_date BETWEEN $2 AND $3 "
        "GROUP BY r.id ORDER BY r.report_date DESC",
        user_id, start, end,
    )
    return [dict(r) for r in rows]


def _range(start, end):
    end = end or datetime.now(TEHRAN).date()
    return (start or end - timedelta(days=60)), end


@router.get("/subjects")
async def subjects(user=Depends(current_user)):
    async with db.pool.acquire() as c:
        return await _subjects_for(c, user["field"])


@router.get("/reports")
async def list_reports(start: Optional[date] = None, end: Optional[date] = None, user=Depends(current_user)):
    start, end = _range(start, end)
    async with db.pool.acquire() as c:
        return await _reports(c, user["id"], start, end)


@router.get("/bootstrap")
async def bootstrap(start: Optional[date] = None, end: Optional[date] = None, user=Depends(current_user)):
    """Everything the Mini App needs on open, in a single request."""
    start, end = _range(start, end)
    async with db.pool.acquire() as c:
        subj = await _subjects_for(c, user["field"])
        reps = await _reports(c, user["id"], start, end)
        try:
            plan = await c.fetchval("SELECT plan FROM study_plans WHERE user_id = $1", user["id"])
        except asyncpg.UndefinedTableError:  # migration not run yet: the app keeps working without plans
            plan = None
    return {"user": {k: user[k] for k in ("username", "field", "grade", "first_name")}, "subjects": subj, "reports": reps, "plan": plan}


@router.put("/reports/{day}")
async def put_report(day: date, body: ReportIn, user=Depends(current_user)):
    """Create or replace the report for one day (today or up to 7 days back, Tehran time)."""
    today = datetime.now(TEHRAN).date()
    if not (today - timedelta(days=7) <= day <= today):
        raise HTTPException(422, "date_out_of_range")
    ids = [e.subject_id for e in body.entries]
    async with db.pool.acquire() as c:
        valid = await c.fetchval("SELECT count(*) FROM subjects WHERE id = ANY($1::int[]) AND $2 = ANY(fields)", ids, user["field"])
        if valid != len(ids):
            raise HTTPException(422, "invalid_subject")
        async with c.transaction():
            rid = await c.fetchval(
                "INSERT INTO study_reports (user_id, report_date, sleep_hours, mood, focus, note) VALUES ($1,$2,$3,$4,$5,$6) "
                "ON CONFLICT (user_id, report_date) DO UPDATE SET sleep_hours = EXCLUDED.sleep_hours, mood = EXCLUDED.mood, "
                "  focus = EXCLUDED.focus, note = EXCLUDED.note, updated_at = now() RETURNING id",
                user["id"], day, Decimal(str(round(body.sleep_hours, 1))), body.mood, body.focus, body.note.strip(),
            )
            await c.execute("DELETE FROM report_entries WHERE report_id = $1", rid)
            await c.executemany(
                "INSERT INTO report_entries (report_id, subject_id, minutes, tests, correct, wrong) VALUES ($1,$2,$3,$4,$5,$6)",
                [(rid, e.subject_id, e.minutes, e.tests, e.correct, e.wrong) for e in body.entries],
            )
    return {"ok": True}


@router.delete("/reports/{day}")
async def delete_report(day: date, user=Depends(current_user)):
    async with db.pool.acquire() as c:
        await c.execute("DELETE FROM study_reports WHERE user_id = $1 AND report_date = $2", user["id"], day)
    return {"ok": True}


class PlanItem(BaseModel):
    subject: str = Field(min_length=1, max_length=40)
    minutes: int = Field(ge=0, le=1440)
    topic: str = Field("", max_length=120)


class PlanDay(BaseModel):
    items: List[PlanItem] = Field(max_length=12)
    note: str = Field("", max_length=200)


class PlanIn(BaseModel):
    title: str = Field("برنامه‌ی مطالعه", max_length=80)
    start_date: date
    days: List[PlanDay] = Field(min_length=1, max_length=120)  # days[0] = start_date, days[1] = next day, ...


@router.put("/plan")
async def put_plan(body: PlanIn, user=Depends(current_user)):
    """Save (replace) the student's plan. It is only a guide: reports do not have to match it."""
    async with db.pool.acquire() as c:
        await c.execute(
            "INSERT INTO study_plans (user_id, plan) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET plan = EXCLUDED.plan, updated_at = now()",
            user["id"], body.model_dump(mode="json"),
        )
    return {"ok": True}


@router.delete("/plan")
async def delete_plan(user=Depends(current_user)):
    async with db.pool.acquire() as c:
        await c.execute("DELETE FROM study_plans WHERE user_id = $1", user["id"])
    return {"ok": True}
