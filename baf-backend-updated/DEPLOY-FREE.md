# Free hosting: Render (app) + Neon (database)

1. Neon: create a free project, open SQL Editor, paste the whole `schema.sql`, run it.
   Copy the connection string. Keep only `?sslmode=require` at the end (remove `&channel_binding=require` if present).
2. GitHub: create a private repository and upload the contents of this folder (never upload `.env` or `.venv`).
3. Render: New > Web Service > pick the repo > Runtime: Docker > Instance type: Free.
   Environment variables:
   - `BOT_TOKEN` = the bot token
   - `DATABASE_URL` = the Neon connection string
   - `DEV_MODE` = false
   - `REGISTRATION_MODE` = open (or `code` + `INVITE_CODE`)
   Health check path: `/api/health`
4. Open `https://YOUR-SERVICE.onrender.com/api/health` (expect `{"ok":true}`), then set the menu button in @BotFather to `https://YOUR-SERVICE.onrender.com`.

Free-tier notes: the app sleeps after 15 minutes without traffic and takes about a minute to wake up.
