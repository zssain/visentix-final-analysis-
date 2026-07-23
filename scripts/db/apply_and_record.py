"""Apply + record migrations against live, per schema.md v1.3 §5 governance.

Governance rule: no migration counts as applied unless a row exists in
`schema_migrations` (filename, checksum sha256, applied_at).

Order (schema.md v1.3 §5 / F02 task STEP A→C):
  STEP A  create schema_migrations (0020) + record it, then BACKFILL one row
          per already-applied HISTORICAL migration (checksum from the file;
          SQL is NOT re-run — they are already applied).
  STEP B  apply 0017 (report_snapshot immutable-report cols) then 0014
          (organization / org-profile cols); record each.
  STEP C  apply 0021 (ingestion tables); record it.

Idempotent: all migration SQL uses IF NOT EXISTS; every record uses
ON CONFLICT DO NOTHING. A second run changes nothing.

The 0011_local_users migration is deliberately NOT backfilled — its live
status is ambiguous (see logs/audits/2026-07-data-layer-audit.md). It gets a
real row only if/when it is actually applied.

Usage:
    python scripts/db/apply_and_record.py --plan     # local, no DB: print checksums + intended ledger
    python scripts/db/apply_and_record.py            # connect to DATABASE_URL, apply + record
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "db" / "migrations"

# Already applied to live BEFORE this task (audit 2026-07-20). Backfill-only:
# record them, do NOT re-run their SQL.
HISTORICAL_APPLIED = [
    "0001_phase1_new_tables.sql",
    "0002_phase1_alter_existing.sql",
    "0003_phase1_seed_stubs.sql",
    "0004_phase2_profiles_rls.sql",
    "0005_phase2_rls_fix.sql",
    "0006_phase2_rls_fix_recursion.sql",
    "0007_phase3_vector_indexes.sql",
    "0008_phase7_training_label.sql",
    "0009_obligation_embedding.sql",
    "0010_category_v2.sql",
    "0011_live_assessment_isolation.sql",
    "0011_reference_corpus.sql",
    "0012_finding_content.sql",
    "0012_versioning_metadata.sql",
    "0013_clause_taxonomy_v2.sql",
    "0013_enforcement_extra_cols.sql",
    "0015_explainability_reference.sql",
    "0016_legal_reference.sql",
    "0018_intake_columns.sql",
    "0019_versioning_columns.sql",
]

# Newly applied by this task, in this exact order. SQL is run, then recorded.
APPLY_NOW = [
    "0020_schema_migrations.sql",   # STEP A — must exist before any record
    "0017_snapshot_rendered_report.sql",  # STEP B — Hard Rule 6 physical backing
    "0014_org_profile_fields.sql",        # STEP B — profiling cols (NOT populated)
    "0021_ingestion_tables.sql",          # STEP C — five ingestion tables
    "0024_source_version.sql",            # F02 — source_version (change-detection history)
    "0025_sic_industry_map.sql",          # F02 EDGAR — DRAFT SIC→industry map (expert-approval gated)
]

# NOT tracked: paste bundles + the ambiguous local_users migration.
UNTRACKED = {"APPLY_0009_0010.sql", "APPLY_ALL_PHASE1.sql", "APPLY_PHASE2_AUTH.sql",
             "0011_local_users.sql"}


def checksum(name: str) -> str:
    return hashlib.sha256((MIG / name).read_bytes()).hexdigest()


def statements(name: str) -> list[str]:
    """Split a DDL file into executable statements (strip -- comments to EOL,
    split on ';'). Safe for these files: pure DDL, no $$ blocks, no ';' in
    string literals."""
    raw = (MIG / name).read_text(encoding="utf-8")
    nocomments = re.sub(r"--[^\n]*", "", raw)
    return [s.strip() for s in nocomments.split(";") if s.strip()]


def plan() -> dict:
    ledger = {}
    for name in HISTORICAL_APPLIED:
        ledger[name] = {"checksum": checksum(name), "how": "backfill (already applied)"}
    for name in APPLY_NOW:
        ledger[name] = {"checksum": checksum(name), "how": "applied by this run"}
    return ledger


def _conn_kwargs() -> tuple[dict, str]:
    """Prefer the IPv4 session pooler (DDL-capable) when present; fall back to the
    direct (IPv6-only) host. Parse the URL by hand and return psycopg keyword args
    — the pooler password can contain URL-hostile characters that break urlparse
    and libpq's own URL parser. Never returns/prints the secret."""
    from dotenv import dotenv_values
    cfg = dotenv_values(ROOT / ".env")
    raw = cfg.get("DATABASE_POOLER_URL")
    label = "pooler (IPv4 session)"
    if not raw:
        raw, label = cfg["DATABASE_URL"], "direct (IPv6)"
    # postgresql://<user>:<password>@<host>:<port>/<db>?<params>
    body = raw.split("://", 1)[1]
    auth, hostpart = body.rsplit("@", 1)              # last @ = real separator (host has none)
    user, password = auth.split(":", 1)               # first : = user/password split
    hostportdb, _, params = hostpart.partition("?")
    hostport, _, dbname = hostportdb.partition("/")
    host, _, port = hostport.rpartition(":")
    kw = {"host": host, "port": int(port or 5432), "user": user, "password": password,
          "dbname": dbname or "postgres", "connect_timeout": 20, "sslmode": "require"}
    if "sslmode=" in params:
        kw["sslmode"] = params.split("sslmode=", 1)[1].split("&", 1)[0]
    return kw, f"{label} host={host}"


def run() -> int:
    import psycopg

    kw, label = _conn_kwargs()
    print(f"connecting via {label}")
    applied, recorded = [], []
    with psycopg.connect(autocommit=False, **kw) as conn:
        with conn.cursor() as cur:
            # STEP A — schema_migrations must exist first
            for stmt in statements("0020_schema_migrations.sql"):
                cur.execute(stmt)
            applied.append("0020_schema_migrations.sql")

            def record(name: str):
                cur.execute(
                    "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s) "
                    "ON CONFLICT (filename) DO NOTHING",
                    (name, checksum(name)),
                )
                recorded.append(name)

            record("0020_schema_migrations.sql")
            # STEP A backfill — record only, SQL already applied historically
            for name in HISTORICAL_APPLIED:
                record(name)
            # STEP B + C — apply then record, in order
            for name in APPLY_NOW[1:]:
                for stmt in statements(name):
                    cur.execute(stmt)
                applied.append(name)
                record(name)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT filename, checksum, applied_at FROM schema_migrations ORDER BY filename")
            rows = cur.fetchall()

    print(f"applied SQL for: {applied}")
    print(f"recorded rows:   {len(recorded)}")
    print("schema_migrations contents:")
    for f, c, ts in rows:
        print(f"  {f}  {c[:12]}…  {ts}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="local only: print checksums + intended ledger, no DB")
    args = ap.parse_args()
    if args.plan:
        print(json.dumps(plan(), indent=2))
        print(f"\n{len(HISTORICAL_APPLIED)} historical (backfill) + {len(APPLY_NOW)} applied-now "
              f"= {len(HISTORICAL_APPLIED) + len(APPLY_NOW)} tracked rows.")
        print(f"NOT tracked: {sorted(UNTRACKED)}")
        return 0
    try:
        return run()
    except Exception as e:  # noqa: BLE001 — surface the real reason, never fake success
        print(f"apply_and_record: FAILED to reach/apply live DB: {type(e).__name__}: "
              f"{str(e)[:160]}", file=sys.stderr)
        print("Nothing was applied or recorded. (Direct DB host is IPv6-only; if this "
              "machine has no IPv6 route, run from an IPv6-capable host or paste the SQL "
              "files into the Supabase SQL editor in the order in APPLY_NOW, then run "
              "this script to record.)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
