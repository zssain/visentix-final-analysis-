#!/usr/bin/env bash
# =============================================================================
# backup.sh — nightly logical backup of the prod Supabase Postgres.
#   pg_dump (schema + data, public) → gzip → S3-compatible off-VM via rclone.
#   Retains BACKUP_RETAIN_DAYS (default 14). Creds come from .env (never git).
#
#   ./deploy/backup.sh              # run a backup now
#
# Installed as a nightly cron by deploy/backup.cron. RPO target: 24h.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
STAMP="${BACKUP_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"   # override for reproducible testing
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# shellcheck disable=SC1090
set -a; [[ -f "${ENV_FILE}" ]] && . "${ENV_FILE}"; set +a

: "${DATABASE_URL:?DATABASE_URL required}"
: "${BACKUP_RCLONE_REMOTE:?BACKUP_RCLONE_REMOTE required}"
: "${BACKUP_BUCKET:?BACKUP_BUCKET required}"
BACKUP_PREFIX="${BACKUP_PREFIX:-prod}"
BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-14}"
DEST="${BACKUP_RCLONE_REMOTE}:${BACKUP_BUCKET}/${BACKUP_PREFIX}"

command -v pg_dump >/dev/null || { echo "pg_dump missing — apt-get install -y postgresql-client" >&2; exit 1; }
command -v rclone  >/dev/null || { echo "rclone missing — see deploy/FIREWALL.md install note" >&2; exit 1; }

# Materialize the rclone config from the base64 blob in .env (keeps creds out of files at rest).
export RCLONE_CONFIG="${WORK}/rclone.conf"
if [[ -n "${RCLONE_CONFIG_BASE64:-}" ]]; then
  echo "${RCLONE_CONFIG_BASE64}" | base64 -d > "${RCLONE_CONFIG}"
  chmod 600 "${RCLONE_CONFIG}"
fi

FILE="visentix-${BACKUP_PREFIX}-${STAMP}.sql.gz"
OUT="${WORK}/${FILE}"

echo "[backup] pg_dump → ${FILE}"
# --no-owner/--no-privileges keep the dump portable (restore-drill loads into a
# different schema); public schema holds the app tables.
pg_dump "${DATABASE_URL}" \
  --schema=public --no-owner --no-privileges \
  --format=plain \
  | gzip -9 > "${OUT}"

SIZE="$(du -h "${OUT}" | cut -f1)"
echo "[backup] wrote ${SIZE}"

echo "[backup] upload → ${DEST}/${FILE}"
rclone copyto "${OUT}" "${DEST}/${FILE}" --s3-no-check-bucket

echo "[backup] prune backups older than ${BACKUP_RETAIN_DAYS}d"
rclone delete --min-age "${BACKUP_RETAIN_DAYS}d" "${DEST}" --include "visentix-${BACKUP_PREFIX}-*.sql.gz"

echo "[backup] OK ${FILE} (${SIZE}) — remaining:"
rclone lsl "${DEST}" --include "visentix-${BACKUP_PREFIX}-*.sql.gz" | sort -k4
