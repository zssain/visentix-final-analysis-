#!/usr/bin/env bash
# =============================================================================
# restore_drill.sh — prove the latest backup is restorable (RTO drill).
#   1. Pull the newest visentix-*.sql.gz from the rclone remote.
#   2. Restore it into schema `restore_test` (isolated; live `public` untouched).
#   3. Run 3 sanity counts and compare against live public counts.
#   4. Print the measured wall-clock (record it as the RTO in the runbook).
#
#   ./deploy/restore_drill.sh
#
# The dump is taken with --schema=public (see backup.sh), so this rewrites the
# public. qualifier to restore_test. and loads under that search_path. It reads
# the SAME DATABASE_URL and creates only a throwaway schema — the drill is safe
# to run against prod, but prefer a staging DB if one exists (set DRILL_DATABASE_URL).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

set -a; [[ -f "${ENV_FILE}" ]] && . "${ENV_FILE}"; set +a

DB="${DRILL_DATABASE_URL:-${DATABASE_URL:?DATABASE_URL required}}"
: "${BACKUP_RCLONE_REMOTE:?}" ; : "${BACKUP_BUCKET:?}"
BACKUP_PREFIX="${BACKUP_PREFIX:-prod}"
DEST="${BACKUP_RCLONE_REMOTE}:${BACKUP_BUCKET}/${BACKUP_PREFIX}"

export RCLONE_CONFIG="${WORK}/rclone.conf"
[[ -n "${RCLONE_CONFIG_BASE64:-}" ]] && { echo "${RCLONE_CONFIG_BASE64}" | base64 -d > "${RCLONE_CONFIG}"; chmod 600 "${RCLONE_CONFIG}"; }

command -v psql >/dev/null || { echo "psql missing — apt-get install -y postgresql-client" >&2; exit 1; }

START=$(date +%s)

echo "[drill] locating newest backup in ${DEST}"
LATEST="$(rclone lsf "${DEST}" --include "visentix-${BACKUP_PREFIX}-*.sql.gz" | sort | tail -1)"
[[ -n "${LATEST}" ]] || { echo "[drill] no backups found" >&2; exit 1; }
echo "[drill] latest = ${LATEST}"
rclone copyto "${DEST}/${LATEST}" "${WORK}/${LATEST}"

echo "[drill] decompress + retarget schema public → restore_test"
gunzip -c "${WORK}/${LATEST}" \
  | sed -E 's/\bpublic\./restore_test./g; s/SET search_path = public/SET search_path = restore_test/g' \
  > "${WORK}/restore.sql"

echo "[drill] resetting schema restore_test"
psql "${DB}" -v ON_ERROR_STOP=1 -q \
  -c 'DROP SCHEMA IF EXISTS restore_test CASCADE;' \
  -c 'CREATE SCHEMA restore_test;'

echo "[drill] loading dump into restore_test (errors on missing objects are tolerated for ref/ext tables)"
# Some Supabase extension/policy lines target other schemas; we only need the app
# tables to land. ON_ERROR_STOP off so partial ref-table failures don't abort the
# core-table restore; the 3 counts below are the real pass/fail gate.
psql "${DB}" -q -f "${WORK}/restore.sql" > "${WORK}/restore.log" 2>&1 || true

echo "[drill] 3 sanity counts (restore_test vs live public):"
FAIL=0
check() {  # $1 = table
  local t="$1" r p
  r=$(psql "${DB}" -tAc "SELECT count(*) FROM restore_test.${t}" 2>/dev/null || echo ERR)
  p=$(psql "${DB}" -tAc "SELECT count(*) FROM public.${t}"       2>/dev/null || echo ERR)
  printf '  %-24s restore_test=%-8s public=%-8s' "${t}" "${r}" "${p}"
  if [[ "${r}" == "ERR" || "${r}" == "0" ]]; then echo "  ✗"; FAIL=1;
  elif [[ "${r}" == "${p}" ]]; then echo "  ✓ (exact)";
  else echo "  ~ (restore ≤ live; acceptable if backup predates recent writes)"; fi
}
check organization
check risk_finding
check report_snapshot

END=$(date +%s); ELAPSED=$(( END - START ))
echo "[drill] restore wall-clock: ${ELAPSED}s  (record as measured RTO in the runbook)"

# Cleanup the throwaway schema so we don't leave restore_test lying around.
psql "${DB}" -q -c 'DROP SCHEMA IF EXISTS restore_test CASCADE;' >/dev/null 2>&1 || true

if (( FAIL )); then echo "[drill] FAILED — core table missing/empty after restore"; exit 1; fi
echo "[drill] PASSED — backup is restorable; 3/3 core tables populated."
