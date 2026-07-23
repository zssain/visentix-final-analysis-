"""FTC enforcement connector driver (F02, family ftc).

    # Preview (no writes) — counts only:
    PYTHONPATH=. python scripts/ingest/run_ftc.py --dry-run

    # Limited live run (newest N privacy cases), then STOP for review:
    PYTHONPATH=. python scripts/ingest/run_ftc.py --limit 50

    # Full historical crawl with resume (picks up after the last crawled page):
    PYTHONPATH=. python scripts/ingest/run_ftc.py --full

    # Incremental (RSS-driven):
    PYTHONPATH=. python scripts/ingest/run_ftc.py --incremental

Resume: the last crawled listing page is persisted to logs/ftc_crawl_cursor.json;
--full resumes from the next page unless --start-page is given. Respects FTC
robots.txt (Crawl-delay 5s) and identifies Visentix honestly.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.services.ingestion.registry import run_one_by_family

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.ftc")

CURSOR = Path("logs/ftc_crawl_cursor.json")


def _read_cursor() -> int:
    try:
        return int(json.loads(CURSOR.read_text()).get("last_page_crawled", -1))
    except Exception:
        return -1


def _write_cursor(page: int) -> None:
    try:
        CURSOR.parent.mkdir(parents=True, exist_ok=True)
        CURSOR.write_text(json.dumps({"last_page_crawled": page}))
    except OSError:
        log.warning("could not persist crawl cursor")


def _report(connector, result, dry_run):
    m = connector.metrics
    print("\n" + "=" * 74)
    print(f"FTC enforcement {'(DRY RUN — no writes)' if dry_run else ''}  outcome={result.outcome}")
    print(f"  privacy cases fetched: {len(connector.parsed_records)}")
    print(f"  enforcement_record written: {m['enforcement_written']}   "
          f"PDFs stored: {m['pdfs_stored']}   orgs resolved: {m['orgs_resolved']}")
    print(f"  last listing page crawled: {m['last_page_crawled']}")
    print("-" * 74)
    print("Sample cases (up to 5):")
    for r in connector.parsed_records[:5]:
        pen = f"${r['penalty_usd']:,.0f}" if r["penalty_usd"] else "-"
        print(f"  • {(r['title'] or '')[:46]:<48} matter={r['matter_number'] or '-':<9} "
              f"date={r['action_date'] or '-':<11} penalty={pen}")
        print(f"      respondent={r['respondents'][0] if r['respondents'] else '-'!r}  "
              f"civil={r['civil_action_number'] or '-'}  pdfs={len(r['pdf_links'])}")
        print(f"      FTC tags (verbatim): {r['topic_tags']}")
    print("=" * 74)
    print("issue_tags stored VERBATIM; FTC-topic→domain map (ftc_topic_domain_map) is an")
    print("EMPTY expert-owned scaffold. No obligation rows created (TODO: F02 v2 expert review).")
    print("=" * 74 + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FTC Legal Library enforcement connector.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="paginated historical crawl (resumable)")
    mode.add_argument("--incremental", action="store_true", help="RSS-driven incremental update")
    ap.add_argument("--limit", type=int, default=None, help="cap cases (e.g. 50 for the pilot)")
    ap.add_argument("--start-page", type=int, default=None, help="listing page to start at (overrides resume)")
    ap.add_argument("--search-term", default="privacy", help="listing search_api_fulltext term")
    ap.add_argument("--dry-run", action="store_true", help="fetch+parse+counts; write nothing")
    args = ap.parse_args(argv)

    ckwargs: dict = {"search_term": args.search_term}
    if args.limit is not None:
        ckwargs["limit"] = args.limit
    if args.incremental:
        ckwargs["mode"] = "incremental"
    if args.start_page is not None:
        ckwargs["start_page"] = args.start_page
    elif args.full:
        ckwargs["start_page"] = _read_cursor() + 1        # resume after last crawled page

    try:
        result, connector = run_one_by_family(
            "ftc", dry_run=args.dry_run, connector_kwargs=ckwargs, return_connector=True)
    except ValueError as e:
        log.error("%s", e)
        return 2

    if args.full and not args.dry_run and connector.metrics["last_page_crawled"] >= 0:
        _write_cursor(connector.metrics["last_page_crawled"])

    _report(connector, result, args.dry_run)
    return 0 if result.outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
