#!/usr/bin/env python3
"""Dump live Postgres column types for the ingestion-write tables into
tests/fixtures/pg_column_types.json — the pinned snapshot the schema-typed test
fakes validate against.

Migration-defined tables (source_version, ingestion_run, security_event,
organization_alias) are ALSO derived from the migration files at test time and
cross-checked against this snapshot (drift guard). `source_record` predates
db/migrations (no DDL there), so this snapshot is its only offline source of truth
— regenerate here if the live table ever changes.

Usage: python scripts/db/dump_column_types.py
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "fixtures" / "pg_column_types.json"
TABLES = ["source_record", "source_version", "ingestion_run", "security_event", "organization_alias"]

# information_schema.data_type → the token used by the fakes' type map.
_NORM = {
    "timestamp with time zone": "timestamptz",
    "character varying": "varchar",
    "double precision": "double precision",
}


def _dsn_kwargs():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._conn_kwargs()[0]


def main():
    kw = _dsn_kwargs()
    out: dict[str, dict[str, str]] = {}
    with psycopg.connect(**kw) as c:
        c.read_only = True
        with c.cursor() as cur:
            for t in TABLES:
                cur.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (t,))
                out[t] = {col: _NORM.get(dt, dt) for col, dt in cur.fetchall()}
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({sum(len(v) for v in out.values())} columns across {len(out)} tables)")


if __name__ == "__main__":
    main()
