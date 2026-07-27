"""Princeton-Leuven curated-corpus import driver (F02, family princeton_leuven).

    PYTHONPATH=. python scripts/ingest/run_princeton.py --dry-run
    PYTHONPATH=. python scripts/ingest/run_princeton.py --limit 200   # pilot across sectors
    PYTHONPATH=. python scripts/ingest/run_princeton.py               # full import

Reads per-sector CSVs (domain,category,last_updated,policy_text) from
PRINCETON_EXTRACT_DIR. Each notice is decomposed/classified via the EXISTING
intake pipeline. Writes NO benchmark_membership rows (F03 owns cohorts). See the
connectors/README.md licensing note.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.services.ingestion.registry import run_one_by_family

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.princeton")


def _report(conn, result, dry):
    m = conn.metrics
    print("\n" + "=" * 72)
    print(f"Princeton-Leuven import {'(DRY RUN — no writes)' if dry else ''}  outcome={result.outcome}")
    print(f"  notices imported: {m['notices']}   clauses: {m['clauses']}")
    print(f"  orgs matched (existing): {m['orgs_matched']}   benchmark-only orgs created: {m['orgs_created']}")
    print("-" * 72)
    print("Per-sector counts:")
    for sec in sorted(m["sector_counts"]):
        print(f"  {sec or '(blank)':<16} {m['sector_counts'][sec]:>6}")
    print("-" * 72)
    print("Clause classification confidence distribution:")
    dist = m["confidence_distribution"]
    for b in ("<0.5", "0.5-0.7", "0.7-0.9", ">=0.9"):
        print(f"  {b:<10} {dist.get(b, 0):>6}")
    print("=" * 72)
    print("Freshness set truthfully (≈0 for ~2019 snapshots) → CQS gating excludes from")
    print("ACTIVE benchmarks. NO benchmark_membership rows written (F03 owns cohorts).")
    print("⚠️  Research-use licensing pending legal verdict — see connectors/README.md.")
    print("=" * 72 + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Princeton-Leuven curated-corpus import.")
    ap.add_argument("--dry-run", action="store_true", help="read+decompose+counts; write nothing")
    ap.add_argument("--limit", type=int, default=None, help="cap notices (pilot)")
    args = ap.parse_args(argv)

    ckwargs: dict = {}
    if args.limit is not None:
        ckwargs["limit"] = args.limit
    try:
        result, conn = run_one_by_family("princeton_leuven", dry_run=args.dry_run,
                                         connector_kwargs=ckwargs, return_connector=True)
    except (ValueError, FileNotFoundError) as e:
        log.error("%s", e)
        return 2
    _report(conn, result, args.dry_run)
    return 0 if result.outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
