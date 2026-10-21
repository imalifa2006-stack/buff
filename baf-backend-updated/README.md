# Baf API (FastAPI + PostgreSQL)

Python 3.9 or newer.

## Run locally
```bash
docker compose up -d                     # PostgreSQL 16 on port 5433, schema.sql is applied automatically on first start
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                     # put the NEW bot token (after /revoke in BotFather)
# Only for REGISTRATION_MODE=list: python -m scripts.add_students students.txt
uvicorn app.main:app --reload            # docs at http://localhost:8000/docs
python -m unittest discover tests        # initData verification tests
```

## How login works
1. The Mini App opens and sends Telegram's signed `initData` to `POST /api/auth/telegram`.
2. Known user: the server returns a session token (opaque, 90 days, sliding). The app stores it and sends `Authorization: Bearer <token>`.
3. Unknown user: if registration is allowed (`can_register: true`) the app shows the registration form and calls `POST /api/auth/register`. Who may register is set by `REGISTRATION_MODE`: `open` (anyone, default), `code` (needs the shared `INVITE_CODE`), `list` (only usernames in `allowed_students`).
4. Next time the app opens, step 1 runs silently, so nobody types a username or password again.
Password is optional and only used by `POST /api/auth/login` (outside Telegram).

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/telegram | silent login, or "needs registration" |
| POST | /api/auth/register | first-time registration |
| POST | /api/auth/login | username and password (web only) |
| POST | /api/auth/logout | revoke this session |
| GET | /api/me, /api/subjects | profile, subjects of the student's field |
| GET | /api/reports?start=&end= | reports with their entries (default: last 60 days) |
| PUT | /api/reports/{YYYY-MM-DD} | create or replace a day (today up to 7 days back) |
| DELETE | /api/reports/{YYYY-MM-DD} | delete a day |

## Before production
- Run behind HTTPS (Nginx + Let's Encrypt). Set `ALLOWED_ORIGINS` to the Mini App origin.
- Add rate limiting on `/api/auth/*`.
- Back up the database (pg_dump daily).

## Mini App
The Mini App lives in `web/index.html` and is served by this backend at `/` (same origin as `/api`).

### Test in a normal browser (no Telegram)
Set `DEV_MODE=true` in `.env`, start the server and open `http://localhost:8000/?dev=1`.
`?dev=2`, `?dev=3` ... act as different fake Telegram users. **Never set DEV_MODE=true on a real server.**

### Check what was saved
```bash
docker compose exec db psql -U baf -d baf -c "select id, telegram_id, username, field, grade from users;"
docker compose exec db psql -U baf -d baf -c "select * from study_reports;"
```

### Test inside Telegram
Telegram opens HTTPS URLs only. Use a server with a domain, or a temporary tunnel (for example cloudflared) that points to `http://localhost:8000`, then set that URL as the Mini App URL in @BotFather.
