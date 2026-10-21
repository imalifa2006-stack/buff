#!/usr/bin/env bash
# Daily database backup, keeps 14 days. Cron example (03:00 every day):
#   0 3 * * * /root/baf-backend/scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U baf baf | gzip > "backups/baf-$(date +%F).sql.gz"
find backups -name 'baf-*.sql.gz' -mtime +14 -delete
