from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .. import db
from ..deps import approved_user, current_user
from .reports import _reports

router = APIRouter(prefix="/api")

class StudentName(BaseModel):
    username: str = Field(min_length=3, max_length=24)

class AdvisorName(BaseModel):
    advisor_username: str = Field(min_length=3, max_length=24)

@router.get("/account/profile")
async def profile(user=Depends(approved_user)):
    async with db.pool.acquire() as c:
        a = await c.fetchval("SELECT username FROM users WHERE id=$1", user["advisor_id"]) if user["advisor_id"] else None
    return {"username": user["username"], "role": user["role"], "advisor_username": a}

@router.put("/account/advisor")
async def update_advisor(body: AdvisorName, user=Depends(approved_user)):
    if user["role"] != "student": raise HTTPException(403, "students_only")
    async with db.pool.acquire() as c:
        advisor = await c.fetchrow("SELECT u.id,u.username FROM users u JOIN verified_advisors v ON v.username=u.username AND v.active=true WHERE u.username=$1 AND u.role='advisor' AND u.status='approved'", body.advisor_username)
        if not advisor: raise HTTPException(403, "invalid_advisor")
        if user["advisor_id"] == advisor["id"]: return {"ok": True, "message": "already_connected"}
        await c.execute("INSERT INTO advisor_change_requests(student_id,advisor_id,status) VALUES($1,$2,'pending') ON CONFLICT (student_id) DO UPDATE SET advisor_id=EXCLUDED.advisor_id,status='pending',created_at=now()", user["id"], advisor["id"])
    return {"ok": True, "message": "pending_advisor_approval", "advisor_username": advisor["username"]}

@router.get("/advisor/students")
async def students(user=Depends(approved_user)):
    if user["role"] != "advisor": raise HTTPException(403, "advisors_only")
    async with db.pool.acquire() as c:
        rows = await c.fetch("SELECT username, (status='approved') AS connected FROM users WHERE advisor_id=$1 AND role='student' ORDER BY username", user["id"])
    return [dict(x) for x in rows]

@router.post("/advisor/students")
async def add_student(body: StudentName, user=Depends(approved_user)):
    if user["role"] != "advisor": raise HTTPException(403, "advisors_only")
    async with db.pool.acquire() as c:
        await c.execute("INSERT INTO advisor_allowlist(advisor_id,student_username) VALUES($1,$2) ON CONFLICT DO NOTHING", user["id"], body.username.strip())
    return {"ok": True}

@router.delete("/advisor/students/{username}")
async def remove_student(username: str, user=Depends(approved_user)):
    if user["role"] != "advisor": raise HTTPException(403, "advisors_only")
    async with db.pool.acquire() as c:
        async with c.transaction():
            await c.execute("DELETE FROM advisor_allowlist WHERE advisor_id=$1 AND student_username=$2", user["id"], username)
            await c.execute("UPDATE users SET status='blocked' WHERE advisor_id=$1 AND username=$2 AND role='student'", user["id"], username)
    return {"ok": True}

@router.get("/advisor/students/{username}/reports")
async def student_reports(username: str, user=Depends(approved_user)):
    if user["role"] != "advisor": raise HTTPException(403, "advisors_only")
    async with db.pool.acquire() as c:
        sid = await c.fetchval("SELECT id FROM users WHERE username=$2 AND advisor_id=$1 AND role='student' AND status='approved'", user["id"], username)
        if sid is None: raise HTTPException(404, "student_not_connected")
        today = date.today()
        return await _reports(c, sid, today-timedelta(days=90), today)

@router.get('/advisor/requests')
async def requests(user=Depends(approved_user)):
    if user['role'] != 'advisor':raise HTTPException(403,'advisors_only')
    async with db.pool.acquire() as c:
        initial = [dict(r) for r in await c.fetch("SELECT username,first_name,'new' AS kind FROM users WHERE advisor_id=$1 AND role='student' AND status='pending'",user['id'])]
        changes = [dict(r) for r in await c.fetch("SELECT u.username,u.first_name,'change' AS kind FROM advisor_change_requests q JOIN users u ON u.id=q.student_id WHERE q.advisor_id=$1 AND q.status='pending'",user['id'])]
        return initial + changes

@router.post('/advisor/requests/{username}/approve')
async def approve(username:str,user=Depends(approved_user)):
    if user['role'] != 'advisor':raise HTTPException(403,'advisors_only')
    async with db.pool.acquire() as c:
        result=await c.execute("UPDATE users SET status='approved' WHERE username=$1 AND advisor_id=$2 AND role='student' AND status='pending'",username,user['id'])
        if result=='UPDATE 0':
            result=await c.execute("UPDATE users SET advisor_id=$1 WHERE id=(SELECT student_id FROM advisor_change_requests WHERE advisor_id=$1 AND status='pending' AND student_id=(SELECT id FROM users WHERE username=$2 AND role='student'))",user['id'],username)
            if result=='UPDATE 0':raise HTTPException(404,'request_not_found')
            await c.execute("UPDATE advisor_change_requests SET status='approved' WHERE advisor_id=$1 AND student_id=(SELECT id FROM users WHERE username=$2)",user['id'],username)
    return {'ok':True}

@router.post('/advisor/requests/{username}/reject')
async def reject(username:str,user=Depends(approved_user)):
    if user['role'] != 'advisor':raise HTTPException(403,'advisors_only')
    async with db.pool.acquire() as c:
        result=await c.execute("UPDATE users SET status='rejected' WHERE username=$1 AND advisor_id=$2 AND role='student' AND status='pending'",username,user['id'])
        if result=='UPDATE 0':
            result=await c.execute("UPDATE advisor_change_requests SET status='rejected' WHERE advisor_id=$1 AND student_id=(SELECT id FROM users WHERE username=$2) AND status='pending'",user['id'],username)
            if result=='UPDATE 0':raise HTTPException(404,'request_not_found')
    return {'ok':True}
