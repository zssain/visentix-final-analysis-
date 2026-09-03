#!/usr/bin/env bash
# Export the Visentix data (public schema — your 1.3 GB: disclosure_clause,
# notice_section, …) out of the restricted Supabase Cloud project.
#
# This is READ-ONLY (pg_dump), so it works even while the project is in the
# over-quota "restricted" state — reads are still allowed, only writes are blocked.
#
# Get the DIRECT connection string from the Supabase dashboard:
#   Project → Settings → Database → Connection string → URI  (port 5432, NOT the
#   6543 pooler — pg_dump needs a direct session).
#
# Usage:
#   export CLOUD_DB_URL='postgresql://postgres:PASSWORD@db.jhzkyfitrdxmzyyvqfak.supabase.co:5432/postgres'
#   ./export-from-cloud.sh              # -> visentix_public.dump
set -euo pipefail

: "${CLOUD_DB_URL:?Set CLOUD_DB_URL to the Supabase DIRECT connection string (port 5432)}"
OUT="${1:-visentix_public.dump}"

command -v pg_dump >/dev/null || { echo "pg_dump not found — install postgresql-client (v15+)"; exit 1; }

echo "→ Dumping the public schema from Cloud (custom format, compressed)…"
echo "  This is read-only and safe while the project is restricted."
pg_dump "$CLOUD_DB_URL" \
  --schema=public \
  --no-owner \
  --format=custom \
  --verbose \
  --file="$OUT"

echo "✓ Wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo "  Privileges (GRANTs to anon/authenticated/service_role) are KEPT so PostgREST"
echo "  can read the tables after restore. Ownership is stripped (--no-owner)."
echo
echo "Next: copy $OUT to the VM and run  ./import-to-selfhost.sh $OUT"
