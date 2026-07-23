"""F02 ingestion foundation — migration governance, ingestion tables, seed.

Two tiers:
  * LOCAL tests always run and assert real invariants (idempotent-by-construction,
    manifest coverage, checksum determinism, seed-row shape).
  * LIVE tests run against Supabase REST when the objects have been applied, and
    pytest.skip with a clear reason when they have not (the direct DB host is
    IPv6-only, so DDL may be applied out-of-band; these become real assertions
    the moment the migrations land). They never fail merely because live is
    not yet migrated.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "db" / "migrations"
CFG = dotenv_values(ROOT / ".env")
URL = CFG.get("SUPABASE_URL", "")
SVC = CFG.get("SUPABASE_SERVICE_ROLE_KEY", "")
ANON = CFG.get("SUPABASE_ANON_KEY", "")
SVC_H = {"apikey": SVC, "Authorization": f"Bearer {SVC}"}
ANON_H = {"apikey": ANON, "Authorization": f"Bearer {ANON}"}

INGESTION_TABLES = ["source_registry", "parser_version", "security_event",
                    "organization_alias", "ingestion_run"]


def _load(modname: str, relpath: str):
    spec = importlib.util.spec_from_file_location(modname, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


runner = _load("f02_apply_and_record", "scripts/db/apply_and_record.py")
seeder = _load("f02_seed_source_registry", "scripts/db/seed_source_registry.py")


# ══════════════════════════════════════════════════════════════════
# LOCAL — always run, real assertions
# ══════════════════════════════════════════════════════════════════

def test_new_migration_files_are_idempotent_by_construction():
    """Re-running any migration must be a no-op: every CREATE TABLE / ADD COLUMN /
    CREATE INDEX in the new files carries IF NOT EXISTS."""
    for name in ["0020_schema_migrations.sql", "0021_ingestion_tables.sql",
                 "0017_snapshot_rendered_report.sql", "0014_org_profile_fields.sql"]:
        sql = (MIG / name).read_text().lower()
        for kw in ["create table", "add column", "create index"]:
            for m in re.finditer(kw, sql):
                tail = sql[m.start():m.start() + 120]
                assert "if not exists" in tail, f"{name}: `{kw}` without IF NOT EXISTS -> not idempotent"


def test_schema_migrations_manifest_partitions_all_files():
    """Every .sql in db/migrations is tracked (historical or applied-now) or
    explicitly untracked — no file silently unclassified, no overlap."""
    on_disk = {p.name for p in MIG.glob("*.sql")}
    tracked = set(runner.HISTORICAL_APPLIED) | set(runner.APPLY_NOW)
    classified = tracked | runner.UNTRACKED
    assert on_disk == classified, f"unclassified/extra files: {on_disk ^ classified}"
    assert not (set(runner.HISTORICAL_APPLIED) & set(runner.APPLY_NOW)), "file both historical AND applied-now"
    assert not (tracked & runner.UNTRACKED), "file both tracked AND untracked"


def test_local_users_and_bundles_not_backfilled():
    """0011_local_users is ambiguous (audit) -> not recorded until really applied;
    APPLY_* bundles are not migrations."""
    assert "0011_local_users.sql" in runner.UNTRACKED
    assert "0011_local_users.sql" not in runner.HISTORICAL_APPLIED
    assert "0011_local_users.sql" not in runner.APPLY_NOW
    for b in ["APPLY_0009_0010.sql", "APPLY_ALL_PHASE1.sql", "APPLY_PHASE2_AUTH.sql"]:
        assert b in runner.UNTRACKED


def test_apply_now_order_and_step_a_first():
    """STEP order: schema_migrations (A) before 0017/0014 (B) before 0021 (C)."""
    assert runner.APPLY_NOW == [
        "0020_schema_migrations.sql",
        "0017_snapshot_rendered_report.sql",
        "0014_org_profile_fields.sql",
        "0021_ingestion_tables.sql",
        "0024_source_version.sql",
        "0025_sic_industry_map.sql",
    ]


def test_checksum_is_raw_file_sha256():
    for name in runner.APPLY_NOW:
        assert runner.checksum(name) == hashlib.sha256((MIG / name).read_bytes()).hexdigest()


def test_seed_rows_wellformed():
    rows = seeder.rows()
    fams = [r["family"] for r in rows]
    assert fams == ["hhs_ocr", "sec_edgar", "ftc", "cppa", "state_ag",
                    "princeton_leuven", "open_web"]
    # exactly hhs_ocr enabled
    assert [r["family"] for r in rows if r["enabled"]] == ["hhs_ocr"]
    # family -> folder mapping (STEP D item 8)
    folder = {r["family"]: r["config"]["raw_artifacts_folder"] for r in rows}
    assert folder == {
        "hhs_ocr": "hhs_ocr", "sec_edgar": "sec_edgar", "ftc": "ftc", "cppa": "cppa",
        "state_ag": "ag_actions", "princeton_leuven": "princeton_leuven", "open_web": "notices",
    }
    # cadence / tier within allowed domains
    for r in rows:
        assert r["cadence"] in {"manual", "daily", "weekly", "monthly"}
        assert r["reliability_tier"] in {1, 2, 3}
    # sec_edgar config reads EDGAR_BULK_PATH
    sec = next(r for r in rows if r["family"] == "sec_edgar")
    assert "edgar_bulk_path" in sec["config"]
    # cppa base_url + archive note
    cppa = next(r for r in rows if r["family"] == "cppa")
    assert cppa["base_url"] == "https://privacy.ca.gov/about-us/newsroom/"
    assert "2026-01-26" in cppa["config"]["note"]


def test_seed_is_idempotent_construction():
    """rows() is pure — two calls produce identical payloads (no time/rand)."""
    assert seeder.rows() == seeder.rows()


# ══════════════════════════════════════════════════════════════════
# LIVE — run when applied, skip (with reason) otherwise
# ══════════════════════════════════════════════════════════════════

def _reachable() -> bool:
    try:
        httpx.get(f"{URL}/rest/v1/organization?limit=0", headers=SVC_H, timeout=10)
        return True
    except Exception:
        return False


def _applied(table: str) -> bool:
    r = httpx.get(f"{URL}/rest/v1/{table}?select=*&limit=0", headers=SVC_H, timeout=15)
    return r.status_code in (200, 206)


def _require(table: str):
    if not _reachable():
        pytest.skip("Supabase REST unreachable from this host")
    if not _applied(table):
        pytest.skip(f"{table} not applied to live yet (DB is IPv6-only; apply out-of-band, then this runs)")


def _require_0021():
    """0021 creates source_registry AND adds RLS/columns to the pre-existing
    ingestion_run — so source_registry presence is the marker that 0021 landed.
    (ingestion_run/report_snapshot exist independently and would falsely pass a
    bare existence check.)"""
    if not _reachable():
        pytest.skip("Supabase REST unreachable from this host")
    if not _applied("source_registry"):
        pytest.skip("migration 0021 not applied to live yet (DB is IPv6-only; apply out-of-band, then this runs)")


def _require_column(table: str, column: str):
    if not _reachable():
        pytest.skip("Supabase REST unreachable from this host")
    r = httpx.get(f"{URL}/rest/v1/{table}?select={column}&limit=0", headers=SVC_H, timeout=15)
    if r.status_code not in (200, 206):
        pytest.skip(f"{table}.{column} not applied to live yet (DB is IPv6-only; apply out-of-band, then this runs)")


def test_schema_migrations_rows_match_file_checksums():
    _require("schema_migrations")
    r = httpx.get(f"{URL}/rest/v1/schema_migrations?select=filename,checksum",
                  headers=SVC_H, timeout=20)
    ledger = {row["filename"]: row["checksum"] for row in r.json()}
    # Every migration THIS branch tracks must be recorded with a matching checksum.
    # The live DB is shared across feature branches, so the ledger may also hold
    # sibling-branch migrations whose files aren't on this branch — ignore those.
    for name in runner.HISTORICAL_APPLIED + runner.APPLY_NOW:
        assert name in ledger, f"{name} applied but not recorded"
        assert ledger[name] == hashlib.sha256((MIG / name).read_bytes()).hexdigest(), \
            f"checksum drift for {name}"


@pytest.mark.parametrize("table", INGESTION_TABLES)
def test_rls_denies_anon(table):
    _require_0021()
    r = httpx.get(f"{URL}/rest/v1/{table}?select=*&limit=1", headers=ANON_H, timeout=15)
    # anon must NOT be able to read rows (RLS enabled + REVOKE -> permission denied)
    assert r.status_code not in (200, 206), \
        f"{table} readable by anon ({r.status_code}) — RLS/REVOKE not enforced"


def test_0017_columns_present_and_writable():
    _require_column("report_snapshot", "report_version")
    cols = {"rendered_report", "content_hash", "report_version",
            "glossary_version", "template_version"}
    # presence via per-column probe
    for c in cols:
        r = httpx.get(f"{URL}/rest/v1/report_snapshot?select={c}&limit=0", headers=SVC_H, timeout=15)
        assert r.status_code in (200, 206), f"report_snapshot.{c} missing"
    # writable server-side: no-op PATCH against a non-existent id (0 rows, but a
    # missing column would 400). Mutates nothing.
    body = {"rendered_report": {"_probe": True}, "content_hash": "probe",
            "report_version": 1, "glossary_version": "probe", "template_version": "probe"}
    r = httpx.patch(
        f"{URL}/rest/v1/report_snapshot?snapshot_id=eq.00000000-0000-0000-0000-000000000000",
        headers={**SVC_H, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json=body, timeout=15,
    )
    assert r.status_code in (200, 204), f"0017 columns not writable: {r.status_code} {r.text[:150]}"


def test_organization_alias_uniqueness_enforced():
    _require("organization_alias")
    # need a real organization_id (FK)
    org = httpx.get(f"{URL}/rest/v1/organization?select=organization_id&limit=1",
                    headers=SVC_H, timeout=15).json()
    if not org:
        pytest.skip("no organization rows to satisfy FK")
    oid = org[0]["organization_id"]
    val = "__f02_uniq_probe__.example"
    ins = {"organization_id": oid, "alias_type": "domain", "value": val}
    wh = {**SVC_H, "Content-Type": "application/json", "Prefer": "return=minimal"}
    try:
        r1 = httpx.post(f"{URL}/rest/v1/organization_alias", headers=wh, json=ins, timeout=15)
        assert r1.status_code in (200, 201, 204), f"first insert failed: {r1.status_code} {r1.text[:150]}"
        r2 = httpx.post(f"{URL}/rest/v1/organization_alias", headers=wh, json=ins, timeout=15)
        assert r2.status_code == 409, f"duplicate (alias_type,value) not rejected: {r2.status_code}"
    finally:
        httpx.delete(f"{URL}/rest/v1/organization_alias?alias_type=eq.domain&value=eq.{val}",
                     headers={**SVC_H, "Prefer": "return=minimal"}, timeout=15)


def test_seed_source_registry_idempotent():
    _require("source_registry")

    def snapshot():
        r = httpx.get(f"{URL}/rest/v1/source_registry?select=*&order=family", headers=SVC_H, timeout=20)
        return r.json()

    seeder.seed()          # ensure seeded
    before = snapshot()
    seeder.seed()          # second run must change nothing
    after = snapshot()
    assert before == after, "second seed run mutated source_registry — not idempotent"
    assert {r["family"] for r in after} == {
        "hhs_ocr", "sec_edgar", "ftc", "cppa", "state_ag", "princeton_leuven", "open_web"}
