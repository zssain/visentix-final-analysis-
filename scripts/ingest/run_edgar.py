"""SEC EDGAR bulk-import driver (F02, family sec_edgar).

Runs the EdgarBulkConnector against the LOCAL bulk download and prints the pilot
report the run-order asks for: per-industry counts + a sample of created org rows.

    # Pilot (500 companies, all mapped industries), then STOP and review:
    PYTHONPATH=. python scripts/ingest/run_edgar.py --limit 500

    # Full import (all mapped industries, no cap):
    PYTHONPATH=. python scripts/ingest/run_edgar.py --full

    # Dry run (fetch + parse + counts; writes nothing):
    PYTHONPATH=. python scripts/ingest/run_edgar.py --limit 500 --dry-run

⚠️ The SIC->industry map is a DRAFT (mapped_by='draft') and is NOT applied to
organization.industry_id. It requires expert approval before it feeds profiling.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.services.ingestion.connectors.edgar import SicIndustryMap
from app.services.ingestion.registry import run_one_by_family

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.edgar")


def _report(connector, result) -> None:
    names = connector._sic.industry_names if hasattr(connector, "_sic") else {}
    counts = connector.industry_counts
    print("\n" + "=" * 64)
    print(f"EDGAR bulk import — outcome={result.outcome}  "
          f"companies_seen={result.seen}  orgs_created={result.new}  "
          f"orgs_enriched={result.changed}  unchanged={result.skipped}")
    print(f"aliases_inserted={connector.metrics['aliases_inserted']}")
    print("-" * 64)
    print("Per-industry counts (companies in scope this run):")
    for iid in sorted(counts):
        print(f"  {iid}  {names.get(iid, ''):<28} {counts[iid]:>6}")
    if not counts:
        print("  (none matched the mapped SIC ranges)")
    print("-" * 64)
    print("Sample created org rows (up to 10):")
    print(f"  {'CIK':<12}{'name':<34}{'domain':<24}{'industry':<10}"
          f"{'industry_id':<12}{'sic_draft':<10}{'filer_category'}")
    for s in connector.samples:
        print(f"  {s['cik']:<12}{(s['name'] or '')[:32]:<34}{(s['domain'] or '-')[:22]:<24}"
              f"{s['industry']:<10}{str(s['industry_id'] or 'NULL'):<12}"
              f"{str(s['sic_industry_draft'] or '-'):<10}{s.get('filer_category') or '-'}")
    print("=" * 64)
    print("⚠️  SIC→industry mapping is DRAFT (mapped_by='draft'); industry_id left NULL.")
    print("    THE MAPPING REQUIRES EXPERT APPROVAL before it feeds profiling (F03).")
    print("=" * 64 + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SEC EDGAR bulk import driver.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--limit", type=int, help="cap companies imported (pilot batch, e.g. 500)")
    g.add_argument("--full", action="store_true", help="import all mapped-industry companies (no cap)")
    ap.add_argument("--industries", default=None,
                    help="comma-separated industry_ids to scope to (default: all mapped)")
    ap.add_argument("--all-industries", action="store_true",
                    help="alias-first mode: import EVERY roster company regardless of SIC "
                         "(industry_id stays NULL, benchmark-irrelevant until industries approved)")
    ap.add_argument("--dry-run", action="store_true", help="fetch+parse+counts; write nothing")
    args = ap.parse_args(argv)

    ckwargs: dict = {}
    if not args.full:
        ckwargs["limit"] = args.limit
    if args.industries:
        ckwargs["industries"] = [s.strip() for s in args.industries.split(",") if s.strip()]
    if args.all_industries:
        ckwargs["all_industries"] = True

    try:
        result, connector = run_one_by_family(
            "sec_edgar", dry_run=args.dry_run, connector_kwargs=ckwargs, return_connector=True)
    except ValueError as e:
        log.error("%s", e)
        return 2

    _report(connector, result)
    return 0 if result.outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
