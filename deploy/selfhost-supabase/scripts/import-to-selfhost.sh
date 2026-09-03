#!/usr/bin/env bash
# Restore the Cloud dump into the self-hosted Postgres. Run ON THE VM, after
# `docker compose --env-file .env up -d` reports the db healthy.
#
# The db container publishes 127.0.0.1:5432, so this connects to localhost.
#
# Usage:
#   export POSTGRES_PASSWORD='<same POSTGRES_PASSWORD as selfhost .env>'
#   ./import-to-selfhost.sh visentix_public.dump
set -euo pipefail

DUMP="${1:-visentix_public.dump}"
[[ -f "$DUMP" ]] || { echo "dump not found: $DUMP"; exit 1; }
: "${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD (same value as the selfhost .env)}"

HOST=127.0.0.1 PORT=5432 DB=postgres DBUSER=postgres
export PGPASSWORD="$POSTGRES_PASSWORD"

command -v psql >/dev/null || { echo "psql/pg_restore not found — install postgresql-client (v15+)"; exit 1; }

echo "→ Ensuring pgvector is available (embeddings need it)…"
psql -h $HOST -p $PORT -U $DBUSER -d $DB -c "CREATE EXTENSION IF NOT EXISTS vector;" || \
  psql -h $HOST -p $PORT -U $DBUSER -d $DB -c "CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;" || true

echo "→ Restoring public schema + data (grants preserved; non-fatal errors logged)…"
# --clean --if-exists → idempotent re-runs. Grant-to-missing-role warnings are
# harmless (supabase/postgres already has anon/authenticated/service_role).
pg_restore -h $HOST -p $PORT -U $DBUSER -d $DB \
  --no-owner \
  --clean --if-exists \
  --jobs=2 \
  --verbose \
  "$DUMP" 2> restore.log || true

echo "✓ Restore finished. Full log in ./restore.log"
echo
echo "→ Sanity row counts (should match Cloud):"
psql -h $HOST -p $PORT -U $DBUSER -d $DB -At -c "
  SELECT 'disclosure_clause '||count(*) FROM disclosure_clause
  UNION ALL SELECT 'notice_section '||count(*) FROM notice_section
  UNION ALL SELECT 'organization '||count(*) FROM organization
  UNION ALL SELECT 'privacy_notice '||count(*) FROM privacy_notice
  UNION ALL SELECT 'derived_data_item '||count(*) FROM derived_data_item;" \
  2>/dev/null || echo "  (could not count — check restore.log for schema errors)"

echo
echo "If a 'type \"vector\" does not exist' error appears in restore.log, run:"
echo "  psql ... -c 'CREATE EXTENSION vector;'  (or 'SCHEMA extensions') and re-run this script."
echo "Next: re-provision auth users, then re-point the app — see README §5–6."
