#!/usr/bin/env bash
# Set the internal Supabase role passwords to POSTGRES_PASSWORD.
# Required once after every FRESH db volume — supabase/postgres creates these
# roles but does not set their passwords, so PostgREST/GoTrue/Storage crash-loop
# with "password authentication failed" until this runs.
#
# Must run as `supabase_admin` (the true superuser); `postgres` cannot ALTER these
# "reserved" roles. supabase_admin's own password IS POSTGRES_PASSWORD.
#
# Run from deploy/selfhost-supabase after `docker compose up -d` shows db healthy:
#   ./scripts/fix-role-passwords.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
CID=$(docker compose ps -q db)
for role in authenticator supabase_auth_admin supabase_storage_admin; do
  printf "%s: " "$role"
  docker compose exec -e PGPASSWORD="$POSTGRES_PASSWORD" -T db \
    psql -U supabase_admin -d postgres -tAc "ALTER ROLE $role WITH PASSWORD '$POSTGRES_PASSWORD';"
done
echo "Restart the dependent services:  docker compose up -d rest auth storage"
