"""Apply + record one or more migration files against live, per schema.md v1.3 §5.

Generic companion to apply_and_record.py (which applies a fixed historical set).
Use this for migrations authored AFTER 0029. Reuses the same connection kwargs,
statement splitter, and schema_migrations ledger discipline: a migration counts as
applied only once a row (filename, sha256 checksum, applied_at) exists.

Every migration file MUST be idempotent (IF NOT EXISTS / DROP ... IF EXISTS), so a
re-run changes nothing. SQL is applied first, then the ledger row is recorded in the
same transaction; ON CONFLICT (filename) DO NOTHING makes recording idempotent too.

Usage:
    python scripts/db/apply_migration.py 0030_config_review_support.sql [more.sql ...]
    python scripts/db/apply_migration.py --plan 0030_config_review_support.sql   # checksums only, no DB
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "db" / "migrations"

_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)


def run(names: list[str]) -> int:
    import psycopg

    kw, label = _ar._conn_kwargs()
    print(f"connecting via {label}")
    applied = []
    with psycopg.connect(autocommit=False, **kw) as conn:
        with conn.cursor() as cur:
            for name in names:
                if not (MIG / name).exists():
                    raise FileNotFoundError(f"migration not found: {name}")
                for stmt in _ar.statements(name):
                    cur.execute(stmt)
                cur.execute(
                    "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s) "
                    "ON CONFLICT (filename) DO NOTHING",
                    (name, _ar.checksum(name)),
                )
                applied.append(name)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT filename, checksum, applied_at FROM schema_migrations "
                        "WHERE filename = ANY(%s) ORDER BY filename", (names,))
            rows = cur.fetchall()
    print(f"applied + recorded: {applied}")
    for f, c, ts in rows:
        print(f"  {f}  {c[:12]}…  {ts}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+", help="migration filename(s) under db/migrations/")
    ap.add_argument("--plan", action="store_true", help="print checksums only, no DB")
    args = ap.parse_args()
    if args.plan:
        for name in args.names:
            print(f"{name}  {_ar.checksum(name)}")
        return 0
    try:
        return run(args.names)
    except Exception as e:  # noqa: BLE001 — surface the real reason, never fake success
        print(f"apply_migration: FAILED: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
        print("Nothing was applied or recorded.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
