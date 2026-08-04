#!/bin/sh
# Automated Postgres backup for the `db` docker-compose service.
#
# Cron (host crontab, outside the container — runs nightly at 02:00):
#   0 2 * * * cd /path/to/FaizanMart && ./deploy/backup_db.sh >> /var/log/faizanmart-backup.log 2>&1
#
# Restores with:
#   gunzip -c backups/faizanmart_YYYYMMDD_HHMMSS.sql.gz | docker compose exec -T db \
#     psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
set -eu

cd "$(dirname "$0")/.."
[ -f .env ] && . ./.env

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT_FILE="$BACKUP_DIR/faizanmart_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] Backing up $POSTGRES_DB -> $OUT_FILE"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$OUT_FILE"

echo "[$(date -Iseconds)] Pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name 'faizanmart_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete

echo "[$(date -Iseconds)] Done: $(du -h "$OUT_FILE" | cut -f1)"
