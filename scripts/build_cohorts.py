"""Phase-3 cohort rebuild (F03) over the freshly-profiled, CQS-eligible population.

Builds a NEW benchmark population (benchmark_version=2, refresh 2026-07-27) — one
cluster per demo industry — from organizations that BOTH have a 7-dimension profile
AND a fresh open_web notice (so they pass CQS freshness; the CQS-excluded 2019 Princeton
`dataset` notices are not what qualifies them). The v1 clusters are left untouched
(Rule 4 — never rewrite history).

Confidence bands (OD-05 / intelligence-logic §5, LOW_CONFIDENCE_COHORT_N=10):
    n >= 20        full cohort
    10 <= n < 20   low-confidence cohort (kept, labelled)
    n < 10         NOT built (insufficient)

Cohort `n` is always live-queryable from benchmark_membership (M-12); peer_count on the
cluster is a build-time cache set to the live membership count, never a hand-typed value.

Run:  PYTHONPATH=. python scripts/build_cohorts.py [--dry-run]
Then: PYTHONPATH=. python scripts/compute_normalization.py --population-version 2
"""
from __future__ import annotations

import argparse
import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)

LOW_CONFIDENCE_COHORT_N = 10   # OD-05 (Decided 2026-07-27)
TARGET_N = 20                  # full-confidence floor (intelligence-logic §5)
BENCHMARK_VERSION = 2
REFRESH = date(2026, 7, 27)
DEMO_INDUSTRIES = ["retail", "healthcare", "fintech"]


def band(n: int) -> tuple[str, str]:
    if n >= TARGET_N:
        return "full", f"full cohort (n={n} >= {TARGET_N})"
    if n >= LOW_CONFIDENCE_COHORT_N:
        return "low_confidence", f"low-confidence cohort (10 <= n={n} < {TARGET_N}) — labelled per OD-05"
    return "insufficient", f"insufficient (n={n} < {LOW_CONFIDENCE_COHORT_N})"


def main() -> int:
    import psycopg
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    kw = _ar._conn_kwargs()[0]
    with psycopg.connect(**kw) as conn:
        conn.autocommit = False
        summary = []
        with conn.cursor() as cur:
            for industry in DEMO_INDUSTRIES:
                cur.execute(
                    "SELECT DISTINCT o.organization_id FROM organization o "
                    "JOIN organization_intelligence_profile p ON p.organization_id = o.organization_id "
                    "JOIN privacy_notice pn ON pn.organization_id = o.organization_id AND pn.notice_type='open_web' "
                    "WHERE o.industry = %s", (industry,))
                org_ids = [r[0] for r in cur.fetchall()]
                n = len(org_ids)
                conf, reason = band(n)
                if conf == "insufficient":
                    summary.append((industry, n, conf, "skipped — not built"))
                    continue
                cluster_id = f"{industry}-2026Q3-v2"
                if not args.dry_run:
                    cur.execute(
                        "INSERT INTO benchmark_cluster (cluster_id, industry, geography, size, risk_profile, peer_count, refresh_date, benchmark_version) "
                        "VALUES (%s,%s,'mixed','mixed',NULL,%s,%s,%s) "
                        "ON CONFLICT (cluster_id) DO UPDATE SET peer_count=EXCLUDED.peer_count, refresh_date=EXCLUDED.refresh_date, benchmark_version=EXCLUDED.benchmark_version",
                        (cluster_id, industry, n, REFRESH, BENCHMARK_VERSION))
                    for oid in org_ids:
                        cur.execute(
                            "INSERT INTO benchmark_membership (cluster_id, organization_id, inclusion_reason, population_version) "
                            "VALUES (%s,%s,%s,%s) "
                            "ON CONFLICT (cluster_id, organization_id) DO UPDATE SET inclusion_reason=EXCLUDED.inclusion_reason, population_version=EXCLUDED.population_version",
                            (cluster_id, oid, reason, BENCHMARK_VERSION))
                summary.append((industry, n, conf, cluster_id))
            if not args.dry_run:
                conn.commit()
        print("\n=== cohort rebuild (benchmark_version=2, 2026-07-27) ===")
        for industry, n, conf, note in summary:
            print(f"  {industry:<12} n={n:<3} {conf:<15} {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
