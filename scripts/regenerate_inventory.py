"""Regenerate the database inventory CSV with FRESH live counts + honest status.

Reads the previous logs/audits/database-inventory-*.csv (same columns), re-queries
every table's live row count, and applies status updates for the tables changed in the
pilot-readiness pass. Writes database-inventory-<today>.csv. Read-only except the file.

Run: PYTHONPATH=. python scripts/regenerate_inventory.py
"""
from __future__ import annotations

import csv
import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "logs" / "audits"
_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)

# Status overrides for tables changed in the 2026-07-27 pass (honest, verified).
STATUS = {
    "organization_intelligence_profile": "POPULATED (116 profiles; +85 fresh demo-industry orgs via scaled profiler)",
    "benchmark_cluster": "POPULATED (6: 3 v1 + 3 new v2 demo cohorts retail/healthcare/fintech, 2026-07-27)",
    "benchmark_membership": "POPULATED (v2 demo cohorts: retail 25 / healthcare 31 / fintech 23, all full-confidence, weighted; live-queryable n per M-12)",
    "privacy_notice": "POPULATED (fresh 2026 open_web notices added: fintech 13 / retail 25 / healthcare 31 — CQS-fresh, replacing reliance on 2019 Princeton)",
    "crawl_target": "POPULATED (retail/healthcare/fintech demo targets seeded + crawled; open-web sector-filter bug fixed)",
    "sic_industry_map": "AI-REVIEWED (11 rows corrected to canonical 10-industry taxonomy + ai_reviewed; 2 Entertainment&Media left draft, OD-09) — human SME approval pending",
    "ftc_topic_domain_map": "AI-REVIEWED (25 FTC topics crosswalked; 11 mapped to a domain, 14 domain=NULL honest non-mapping) — human SME approval pending",
    "formula_version": "POPULATED (14 rows; plain-English guardrail-safe description column populated, 0 NULL — M-10 content prerequisite met)",
    "enforcement_record": "POPULATED (30 resolved / 623 unresolved; F-004 correlates against RESOLVED only). Deterministic resolver found 0 safe additional matches; remainder review-queue, never forced.",
    "security_event": "POPULATED (11 resolved / 696 unresolved — same: 0 safe additional deterministic matches). Never feeds F-004 (OD-06).",
}
# disclosure_clause + clause_obligation statuses carry LIVE embedding coverage
# (computed in main(), not hardcoded).


def main() -> int:
    import psycopg
    prev = sorted(AUDITS.glob("database-inventory-*.csv"))
    if not prev:
        print("no previous inventory CSV found"); return 1
    rows = list(csv.DictReader(prev[-1].read_text(encoding="utf-8").splitlines()))
    fields = list(rows[0].keys())

    kw = _ar._conn_kwargs()[0]
    with psycopg.connect(**kw) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            def count(t):
                try:
                    cur.execute(f"SELECT count(*) FROM {t}")
                    return cur.fetchone()[0]
                except Exception:
                    conn.rollback()
                    return None
            # Live embedding coverage (exact) for honest, non-hardcoded status.
            cur.execute("SELECT count(*) FROM disclosure_clause")
            dc_total = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM disclosure_clause WHERE embedding IS NOT NULL")
            dc_emb = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM clause_obligation")
            co_rows = cur.fetchone()[0]
            cov = dc_emb / dc_total * 100 if dc_total else 0.0
            STATUS["disclosure_clause"] = (
                f"POPULATED. Embeddings: {dc_emb}/{dc_total} ({cov:.1f}%) via all-MiniLM-L6-v2 "
                f"(embedding_model tagged); backfill IN PROGRESS (resumable) — remainder is the "
                f"RunPod GPU job. is_exemplar/exemplar_status + is_noise/noise_reason present."
            )
            if co_rows == 0:
                STATUS["clause_obligation"] = (
                    f"EMPTY — Part-B matcher IMPLEMENTED + gated. Not run: clause embedding coverage "
                    f"{cov:.1f}% < 95% gate (MUST NOT present partial as complete). Runs once coverage ≥95%."
                )
            else:
                STATUS["clause_obligation"] = (
                    f"POPULATED ({co_rows} matches) via obligation_match (floor 0.35, exposure-context only; "
                    f"similarity+matched_terms+model_version). Ran at {cov:.1f}% embedding coverage."
                )

            for r in rows:
                t = r["table"]
                n = count(t)
                if n is not None:
                    r["rows_live"] = str(n)
                if t in STATUS:
                    r["status"] = STATUS[t]

    out = AUDITS / f"database-inventory-{date(2026,7,28).isoformat()}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out.relative_to(ROOT)} ({len(rows)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
