"""CLI: python -m app.services.ingestion.run --family hhs_ocr [--dry-run]

--dry-run does fetch + hash + diff counts but writes nothing.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.services.ingestion.registry import run_one_by_family

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.run")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a source-ingestion connector by family.")
    ap.add_argument("--family", required=True, help="source_registry family (e.g. hhs_ocr, sec_edgar)")
    ap.add_argument("--dry-run", action="store_true", help="fetch + hash + diff counts; write nothing")
    ap.add_argument("--limit", type=int, default=None,
                    help="batch connectors (sec_edgar): cap the number of companies imported (pilot)")
    ap.add_argument("--industries", default=None,
                    help="sec_edgar: comma-separated industry_ids to scope to (default: all mapped)")
    args = ap.parse_args(argv)

    connector_kwargs: dict = {}
    if args.limit is not None:
        connector_kwargs["limit"] = args.limit
    if args.industries:
        connector_kwargs["industries"] = [s.strip() for s in args.industries.split(",") if s.strip()]

    try:
        result = run_one_by_family(args.family, dry_run=args.dry_run,
                                   connector_kwargs=connector_kwargs)
    except ValueError as e:
        log.error("%s", e)
        return 2

    log.info("family=%s dry_run=%s outcome=%s seen=%d new=%d changed=%d skipped=%d errors=%d",
             args.family, args.dry_run, result.outcome, result.seen, result.new,
             result.changed, result.skipped, len(result.errors))
    return 0 if result.outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
