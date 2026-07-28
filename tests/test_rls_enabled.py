"""Standing security guard — every public base table MUST have RLS enabled.

Closes the class of gap found on 2026-07-29 (incident: RLS disabled on 38 public
tables → anon-key exposure via PostgREST; fixed by migration 0042). If a future
migration creates a table without `ENABLE ROW LEVEL SECURITY`, this test fails.

Live-DB test: connects via the migration tooling's connection kwargs (direct
Postgres / session pooler). Auto-skips in CI (no live Supabase) via conftest's
_LIVE_DB_MODULES set; runs locally before merge.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _conn_kwargs():
    spec = importlib.util.spec_from_file_location(
        "_ar", ROOT / "scripts" / "db" / "apply_and_record.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._conn_kwargs()


def _public_tables_without_rls() -> list[str]:
    import psycopg

    kw, _ = _conn_kwargs()
    with psycopg.connect(autocommit=True, **kw) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relkind = 'r'
               AND c.relrowsecurity = false
             ORDER BY c.relname;
            """
        )
        return [r[0] for r in cur.fetchall()]


def test_all_public_tables_have_rls_enabled():
    """No public base table may have rowsecurity=false. A new one means a
    migration forgot `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` (+ REVOKE
    anon/authenticated). See db/migrations/0042 and the migration template."""
    try:
        offenders = _public_tables_without_rls()
    except Exception as exc:  # pragma: no cover - environment/skip guard
        pytest.skip(f"live DB unavailable ({type(exc).__name__}); runs locally")
    assert offenders == [], (
        "Public tables with RLS DISABLED (PostgREST-exposed to the anon key): "
        f"{offenders}. Add `ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;` "
        "and `REVOKE ALL ON public.<t> FROM anon, authenticated;` in a migration "
        "(see 0042_enable_rls_all_public.sql)."
    )
