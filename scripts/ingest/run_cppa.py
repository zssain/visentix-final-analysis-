"""CPPA newsroom connector driver (F02, family cppa).

    PYTHONPATH=. python scripts/ingest/run_cppa.py --dry-run       # preview, no writes
    PYTHONPATH=. python scripts/ingest/run_cppa.py                 # live newsroom
    PYTHONPATH=. python scripts/ingest/run_cppa.py --archive-pass  # + one legacy-archive pass

Enforcement items → enforcement_record (regulator CPPA); non-enforcement news →
source_record only (source_type='regulator_announcement'). Verbatim CPPA categories.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.services.ingestion.registry import run_one_by_family

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.cppa")


def _report(conn, result, dry):
    m = conn.metrics
    print("\n" + "=" * 72)
    print(f"CPPA newsroom {'(DRY RUN — no writes)' if dry else ''}  outcome={result.outcome}")
    print(f"  announcement pages seen: {len(conn.parsed_records)}")
    print(f"  enforcement_record written: {m['enforcement_written']}   "
          f"announcement-only source_records: {m['announcements_only']}")
    print(f"  order PDFs stored: {m['pdfs_stored']}   orgs resolved: {m['orgs_resolved']}")
    print("-" * 72)
    print("Sample items (up to 6):")
    for r in conn.parsed_records[:6]:
        kind = "ENFORCEMENT" if r["is_enforcement"] else "announcement"
        pen = f"${r['penalty_usd']:,.0f}" if r["penalty_usd"] else "-"
        print(f"  [{kind:<11}] {r['date'] or '-':<11} {(r['title'] or '')[:60]}")
        if r["is_enforcement"]:
            print(f"      company={r['company']!r} penalty={pen} categories(verbatim)={r['categories']}")
    print("=" * 72 + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CPPA newsroom connector.")
    ap.add_argument("--dry-run", action="store_true", help="fetch+parse+counts; write nothing")
    ap.add_argument("--limit", type=int, default=None, help="cap announcement pages")
    ap.add_argument("--archive-pass", action="store_true",
                    help="also crawl the legacy cppa.ca.gov/announcements once")
    args = ap.parse_args(argv)

    ckwargs: dict = {"force_archive": args.archive_pass}
    if args.limit is not None:
        ckwargs["limit"] = args.limit
    try:
        result, conn = run_one_by_family("cppa", dry_run=args.dry_run,
                                         connector_kwargs=ckwargs, return_connector=True)
    except ValueError as e:
        log.error("%s", e)
        return 2
    _report(conn, result, args.dry_run)
    return 0 if result.outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
