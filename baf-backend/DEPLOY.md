# Deploy on an Ubuntu server

You need: a server (Ubuntu 22.04/24.04, 1 GB RAM or more, root access) and a domain whose A record points to the server IP.

1. From your computer: `scp baf-backend.zip root@SERVER_IP:~`
2. `ssh root@SERVER_IP`
3. `apt-get update && apt-get install -y unzip && unzip -o baf-backend.zip && cd baf-backend`
4. `bash deploy/setup_server.sh`
5. `cp .env.prod.example .env`, then fill DOMAIN, BOT_TOKEN and POSTGRES_PASSWORD (`nano .env`).
6. `docker compose -f docker-compose.prod.yml up -d --build`
7. Check: `docker compose -f docker-compose.prod.yml ps` (3 services running), then open `https://YOUR_DOMAIN/api/health`.
8. In @BotFather: `/setmenubutton`, pick the bot, send `https://YOUR_DOMAIN`.

Useful commands (run in the project folder):
- Logs: `docker compose -f docker-compose.prod.yml logs -f api`
- Users: `docker compose -f docker-compose.prod.yml exec db psql -U baf -d baf -c "select id, username, field, grade, created_at from users;"`
- Update after new files: unzip again, then `docker compose -f docker-compose.prod.yml up -d --build`
- Backup: `bash scripts/backup.sh` (add to cron for daily backups)
