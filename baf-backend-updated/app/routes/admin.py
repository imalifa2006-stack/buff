from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .. import db
from ..deps import approved_user

router = APIRouter(prefix="/api/admin")

class Username(BaseModel):
    username: str = Field(min_length=3, max_length=24)

class StudentCreate(Username):
    advisor_username: str
    first_name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    field: str = 'r'
    grade: str = '12'

def require_admin(u):
    if u['role'] not in ('admin','super_admin'): raise HTTPException(403, 'admin_only')

@router.get('/users')
async def users(u=Depends(approved_user)):
    require_admin(u)
    async with db.pool.acquire() as c:
        return [dict(r) for r in await c.fetch("SELECT u.id,u.username,u.first_name,u.role,u.status,a.username AS advisor_username FROM users u LEFT JOIN users a ON a.id=u.advisor_id WHERE u.role NOT IN ('admin','super_admin') ORDER BY u.role,u.id")]

@router.get('/verified-advisors')
async def verified_advisors(u=Depends(approved_user)):
    require_admin(u)
    async with db.pool.acquire() as c:
        return [dict(r) for r in await c.fetch("SELECT v.username,v.active,u.status AS account_status FROM verified_advisors v LEFT JOIN users u ON u.username=v.username AND u.role='advisor' ORDER BY v.username")]

@router.post('/advisors')
async def add_advisor(b: Username, u=Depends(approved_user)):
    require_admin(u)
    async with db.pool.acquire() as c:
        await c.execute('INSERT INTO verified_advisors(username,active) VALUES($1,true) ON CONFLICT(username) DO UPDATE SET active=true',b.username.strip())
        await c.execute("UPDATE users SET status='approved' WHERE username=$1 AND role='advisor'", b.username.strip())
    return {'ok':True}

@router.delete('/advisors/{username}')
async def remove_advisor(username:str,u=Depends(approved_user)):
    require_admin(u)
    async with db.pool.acquire() as c:
        async with c.transaction():
            aid=await c.fetchval("SELECT id FROM users WHERE username=$1 AND role='advisor'",username)
            if aid and await c.fetchval("SELECT 1 FROM users WHERE advisor_id=$1 AND role='student' AND status='approved' LIMIT 1",aid):
                raise HTTPException(409,'reassign_students_first')
            await c.execute('UPDATE verified_advisors SET active=false WHERE username=$1',username)
            await c.execute("UPDATE users SET status='blocked' WHERE username=$1 AND role='advisor'",username)
    return {'ok':True}

@router.post('/students')
async def add_student(b:StudentCreate,u=Depends(approved_user)):
    require_admin(u)
    from ..security import hash_password
    if b.field not in ('r','t','e') or b.grade not in ('10','11','12','grad'):
        raise HTTPException(422,'invalid_field_or_grade')
    async with db.pool.acquire() as c:
        aid=await c.fetchval("SELECT u.id FROM users u JOIN verified_advisors v ON v.username=u.username AND v.active=true WHERE u.username=$1 AND u.role='advisor' AND u.status='approved'",b.advisor_username)
        if not aid: raise HTTPException(422,'invalid_advisor')
        if await c.fetchval('SELECT 1 FROM users WHERE username=$1',b.username):raise HTTPException(409,'username_taken')
        await c.execute("INSERT INTO users(username,first_name,password_hash,field,grade,role,status,advisor_id) VALUES($1,$2,$3,$4,$5,'student','approved',$6)",b.username,b.first_name,hash_password(b.password),b.field,b.grade,aid)
    return {'ok':True}

@router.put('/students/{username}/advisor')
async def move_student(username:str,b:Username,u=Depends(approved_user)):
    require_admin(u)
    async with db.pool.acquire() as c:
        aid=await c.fetchval("SELECT u.id FROM users u JOIN verified_advisors v ON v.username=u.username AND v.active=true WHERE u.username=$1 AND u.role='advisor' AND u.status='approved'",b.username)
        if not aid:raise HTTPException(422,'invalid_advisor')
        result=await c.execute("UPDATE users SET advisor_id=$1,status='approved' WHERE username=$2 AND role='student'",aid,username)
        if result=='UPDATE 0':raise HTTPException(404,'student_not_found')
    return {'ok':True}

@router.delete('/students/{username}')
async def disable_student(username:str,u=Depends(approved_user)):
    require_admin(u)
    async with db.pool.acquire() as c:
        await c.execute("UPDATE users SET status='blocked' WHERE username=$1 AND role='student'",username)
    return {'ok':True}
