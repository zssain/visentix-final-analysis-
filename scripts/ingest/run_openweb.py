"""Open-web privacy-notice crawler driver (F02, family open_web).

    PYTHONPATH=. python scripts/ingest/run_openweb.py --sector retail --limit 25

Crawls crawl_target rows (Playwright render + SSRF-safe validation), captures each
company's CURRENT privacy notice through the existing intake path, and records honest
per-domain outcomes on crawl_target. Requires Playwright + Chromium
(`pip install playwright && playwright install chromium`).
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.services.ingestion.registry import run_one_by_family

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion.openweb")


def _report(conn, result):
    m = conn.metrics
    print("\n" + "=" * 72)
    print(f"Open-web crawl  outcome={result.outcome}")
    print(f"  targets crawled: {m['crawled']}   notices captured: {m['captured']}")
    print("-" * 72)
    print("Success / failure breakdown (with reasons):")
    for status in sorted(m["status_counts"]):
        print(f"  {status:<14} {m['status_counts'][status]:>5}")
    print("-" * 72)
    print("Sample captured notices (up to 3):")
    for s in m["samples"][:3]:
        print(f"  {s['domain']:<26} clauses={s['clauses']:<4} {s['notice_url']}")
    print("=" * 72 + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Open-web notice crawler.")
    ap.add_argument("--sector", default=None, help="crawl only this sector's targets")
    ap.add_argument("--limit", type=int, default=None, help="cap targets (pilot, e.g. 25)")
    args = ap.parse_args(argv)

    ckwargs = {"sector": args.sector, "limit": args.limit}
    try:
        result, conn = run_one_by_family("open_web", connector_kwargs=ckwargs, return_connector=True)
    except ValueError as e:
        log.error("%s", e)
        return 2
    _report(conn, result)
    return 0 if result.outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
