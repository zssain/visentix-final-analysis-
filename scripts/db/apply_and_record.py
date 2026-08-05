#!/usr/bin/env python3
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
    "0022_persistence_hardening.sql",     # F06 — review/training persistence + approve_and_freeze
    "0024_source_version.sql",            # F02 — source_version (change-detection history)
    "0025_sic_industry_map.sql",          # F02 EDGAR — DRAFT SIC→industry map (expert-approval gated)
    "0026_ftc_topic_domain_map.sql",      # F02 FTC — empty topic→domain scaffold + enforcement id cols
    "0027_enforcement_org_resolution.sql",# F02 FTC — enforcement_record org resolution columns
    "0028_organization_origin.sql",       # F02 Princeton — organization.origin provenance flag
    "0029_crawl_target.sql",              # F02 open_web — crawl_target work-list
    "0030_config_review_support.sql",     # Phase 1 — config-review support (ai_reviewed state + reviewed_by/at)
    "0031_formula_version_description.sql", # Phase 5 — formula_version.description (M-10)
    "0032_disclosure_clause_exemplar.sql",  # Phase 5 — disclosure_clause.is_exemplar/exemplar_status (M-03)
    "0033_intake_provenance.sql",           # F01 — privacy_notice intake_method + upload provenance (upload intake mode)
    "0034_decompose_noise_filter.sql",      # F01 — disclosure_clause.is_noise/noise_reason + privacy_notice.decompose_version (noise filter)
    "0035_embeddings_and_obligation_match.sql",  # Embeddings backfill RPC + clause_obligation.matched_terms/model_version
    "0036_gold_label.sql",                       # F17 — gold_label (human gold-standard labels for eval harness)
    "0037_f07_scheduler_alerts.sql",             # F07 — job_run/alert_delivery/org_notification_setting + monitoring_event org/payload + litigation
    "0038_f19_bulk_screening.sql",               # F19 — bulk_job/bulk_job_row + user_role 'analyst' (bulk screening on the reassessment kernel)
    "0039_f20_partner_portal.sql",               # F20 — partner/partner_workspace/partner_api_key/feed_access_log + user_role 'partner_admin' + profiles.partner_id + report_snapshot.branding_applied
    "0040_f21_quarterly.sql",                    # F21 — quarterly_snapshot/quarterly_metric + approved-snapshot immutability trigger (DIR-010)
    "0041_f05_f18_evidence_rewrite.sql",         # F05 addendum (recommendation_evidence) + F18 (clause_rewrite)
    "0042_enable_rls_all_public.sql",            # SECURITY — ENABLE RLS + REVOKE anon/authenticated on every public table (incident 2026-07-29)
    "0043_assessment_job.sql",                   # QA-011 — async intake job/progress table (additive, RLS-on); prod apply = external step
    "0044_org_industry_source.sql",              # ARCH-001A — organization.industry_source provenance column (additive nullable); prod apply = external step
    "0045_org_notice_fks.sql",                   # DATA-004 — org/notice FKs (NOT VALID, data-safe); prod apply = external step (then audit + VALIDATE)
    "0046_reapply_notice_rls_policies.sql",      # SEC-008 — re-apply 0011's notice-table RLS policies absent in live schema (ledger drift); prod apply = external step
    "0047_assessment_id_uuid_check.sql",         # DB-002 — CHECK assessment_id is UUID-shaped (NOT VALID, data-safe); type→uuid+FK is a staged external step
]

# ── DB-001: migration numbering & ordering (documented) ──────────────────────
# Apply order is THIS manifest (HISTORICAL_APPLIED + APPLY_NOW), NOT filename sort —
# so the historical duplicate prefixes (three 0011_*, two each 0012_/0013_) and the
# 0023 gap are harmless: order is explicit here, and each file's checksum is recorded
# in `schema_migrations`. Applied files are NEVER renamed (that would break the
# checksum ledger + deployed environments). Historical aliases:
#   0011_live_assessment_isolation / 0011_local_users (UNTRACKED) / 0011_reference_corpus
#   0012_finding_content / 0012_versioning_metadata ; 0013_clause_taxonomy_v2 / 0013_enforcement_extra_cols
# RULE FOR NEW MIGRATIONS: use the next strictly-increasing zero-padded integer with
# NO collision against any existing prefix (next free is 0048), append to APPLY_NOW.
# A clean monotonic renumber is only safe on a fresh, never-deployed DB.

# NOT tracked: paste bundles, the ambiguous local_users migration, and the
# authoring template (not a real migration — never applied/recorded).
UNTRACKED = {"APPLY_0009_0010.sql", "APPLY_ALL_PHASE1.sql", "APPLY_PHASE2_AUTH.sql",
             "0011_local_users.sql", "_TEMPLATE.sql"}


# Every migration this branch legitimately tracks (record-only may target these).
TRACKED = frozenset(HISTORICAL_APPLIED) | frozenset(APPLY_NOW)


def checksum(name: str) -> str:
    return hashlib.sha256((MIG / name).read_bytes()).hexdigest()


def statements(name: str) -> list[str]:
    """Split a DDL file into executable statements. Dollar-quote aware: text
    inside $$...$$ (e.g. a PL/pgSQL function body) is preserved verbatim —
    its semicolons and comments are NOT treated as statement boundaries.
    Outside dollar-quotes, -- comments are stripped and ';' ends a statement."""
    raw = (MIG / name).read_text(encoding="utf-8")
    stmts: list[str] = []
    buf: list[str] = []
    i, n, in_dollar = 0, len(raw), False
    while i < n:
        if raw[i:i + 2] == "$$":
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        if not in_dollar:
            if raw[i:i + 2] == "--":                 # line comment → skip to EOL
                nl = raw.find("\n", i)
                i = n if nl < 0 else nl
                continue
            if raw[i] == ";":
                s = "".join(buf).strip()
                if s:
                    stmts.append(s)
                buf = []
                i += 1
                continue
        buf.append(raw[i])
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


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


def record_only(filename: str, *, execute: bool = True) -> tuple[str, str]:
    """RECORD-ONLY reconciliation — insert a `schema_migrations` row for a
    migration whose DDL was ALREADY applied out-of-band (e.g. pasted into the
    Supabase SQL editor), WITHOUT running any DDL.

    This exists so a hand-applied migration is reconciled by the SAME checksum
    code the normal path uses — never by a hand-typed ledger row that could drift
    (the exact failure this whole preflight guards against).

    Guards (deliberately strict):
      * `filename` must be a SINGLE, explicit, TRACKED migration — no bulk
        auto-marking, no unknown/untracked files. Refuses otherwise.
      * Executes NO DDL. The only statement is the ledger INSERT
        (ON CONFLICT (filename) DO NOTHING) — identical to the normal record().
      * Refuses if `schema_migrations` does not yet exist (run the real apply first).

    With `execute=False` it validates + computes the checksum but touches no DB
    (unit-testable dry run). Returns (filename, checksum).
    """
    if filename not in TRACKED:
        raise ValueError(
            f"refusing record-only for '{filename}': not a tracked migration "
            "(must be in HISTORICAL_APPLIED or APPLY_NOW). No bulk / unknown files."
        )
    cs = checksum(filename)
    if not execute:
        return filename, cs

    import psycopg

    kw, label = _conn_kwargs()
    print("⚠️  RECORD-ONLY MODE — recording a migration as applied WITHOUT running its DDL.")
    print(f"    file   : {filename}")
    print(f"    reason : DDL already applied out-of-band; this reconciles the ledger only.")
    print(f"    effect : one INSERT into schema_migrations — NO schema change. via {label}")
    with psycopg.connect(autocommit=False, **kw) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            if cur.fetchone()[0] is None:
                raise RuntimeError(
                    "schema_migrations does not exist yet — run the normal apply "
                    "(which creates 0020) before recording anything."
                )
            cur.execute(
                "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s) "
                "ON CONFLICT (filename) DO NOTHING RETURNING filename",
                (filename, cs),
            )
            inserted = cur.fetchone() is not None
        conn.commit()
    if inserted:
        print(f"  ✓ recorded {filename}  {cs[:12]}…  (no DDL executed)")
    else:
        print(f"  = {filename} was ALREADY recorded — no change (checksum {cs[:12]}…)")
    return filename, cs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="local only: print checksums + intended ledger, no DB")
    ap.add_argument("--record-only", metavar="FILENAME", default=None,
                    help="reconcile the ledger for ONE already-applied migration (no DDL). "
                         "Requires an explicit tracked filename; refuses bulk/unknown.")
    ap.add_argument("--print-head", action="store_true",
                    help="print the latest recorded migration filename (deploy.sh smoke summary).")
    args = ap.parse_args()
    if args.print_head:
        try:
            import psycopg
            kw, _ = _conn_kwargs()
            with psycopg.connect(autocommit=True, **kw) as conn, conn.cursor() as cur:
                cur.execute("SELECT filename FROM schema_migrations ORDER BY filename DESC LIMIT 1")
                row = cur.fetchone()
            print(row[0] if row else "(no rows)")
            return 0
        except Exception as e:  # noqa: BLE001 — never fake a head
            print(f"print-head FAILED: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            return 1
    if args.record_only:
        try:
            record_only(args.record_only)
            return 0
        except Exception as e:  # noqa: BLE001 — surface the real reason, never fake success
            print(f"record-only FAILED: {type(e).__name__}: {str(e)[:180]}", file=sys.stderr)
            return 1
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
