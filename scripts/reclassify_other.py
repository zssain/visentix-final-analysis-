"""Reclassify corpus 'other' clauses via local Qwen3 8B — ADDITIVE ONLY.

Writes ONLY to category_v2, nlp_confidence_v2, classifier_version columns.
NEVER overwrites the original category or nlp_confidence.
Idempotent + resumable: only processes rows where category_v2 IS NULL.

REQUIRES APPROVAL before running. See docs/RECLASSIFY_PLAN.md.

Usage:
    PYTHONPATH=. python scripts/reclassify_other.py --dry-run
    PYTHONPATH=. python scripts/reclassify_other.py
"""

import argparse
import asyncio
import json
import logging
import time

import httpx
from dotenv import dotenv_values

from app.services.llm import get_llm_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reclassify_other")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

TAXONOMY = [
    "data_sharing", "tracking_cookies", "consumer_rights", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions", "other",
]
CLASSIFIER_VERSION = "qwen3-8b-local-v1"


def fetch_other_clauses(limit=1000, offset=0):
    """Fetch clauses where category='other' AND category_v2 IS NULL."""
    r = httpx.get(
        f"{URL}/rest/v1/disclosure_clause"
        f"?select=clause_id,normalized_text"
        f"&category=eq.other&category_v2=is.null"
        f"&offset={offset}&limit={limit}",
        headers=H, timeout=30,
    )
    return r.json()


def update_clause_v2(clause_id, category_v2, confidence_v2):
    """UPDATE only the v2 columns — never touches original category."""
    for attempt in range(3):
        try:
            r = httpx.patch(
                f"{URL}/rest/v1/disclosure_clause?clause_id=eq.{clause_id}",
                headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json={
                    "category_v2": category_v2,
                    "nlp_confidence_v2": confidence_v2,
                    "classifier_version": CLASSIFIER_VERSION,
                },
                timeout=15,
            )
            if r.status_code < 300:
                return True
        except (httpx.ReadTimeout, httpx.RemoteProtocolError):
            if attempt < 2:
                time.sleep(2 ** attempt)
    return False


async def classify_clause(llm, text):
    """Classify a single clause via LLM."""
    try:
        result = await llm.classify(text, TAXONOMY)
        cat = result.get("category", "other")
        conf = result.get("confidence", 0.5)
        if cat not in TAXONOMY:
            cat = "other"
        return cat, min(conf, 0.95)
    except Exception:
        return "other", 0.3


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()

    llm = get_llm_client()
    # Force local backend for batch work (hosted is for live only)
    llm._backend = "local"
    log.info("LLM backend: %s (forced local for batch)", llm._backend)

    total_processed = 0
    total_reclassified = 0
    offset = 0

    while True:
        limit = 10 if args.dry_run else args.batch_size
        clauses = fetch_other_clauses(limit=limit, offset=offset)

        if not clauses:
            break

        for clause in clauses:
            text = clause.get("normalized_text", "")
            if len(text) < 20:
                continue

            cat, conf = await classify_clause(llm, text)
            total_processed += 1

            if args.dry_run:
                log.info(
                    "[DRY-RUN] %s → %s (conf=%.2f) text=%d chars (not logged)",
                    clause["clause_id"][:12], cat, conf, len(text),
                )
            else:
                if update_clause_v2(clause["clause_id"], cat, conf):
                    if cat != "other":
                        total_reclassified += 1

            if total_processed % 50 == 0:
                log.info("Progress: %d processed, %d reclassified", total_processed, total_reclassified)

        if args.dry_run:
            log.info("[DRY-RUN] Would process %d+ clauses. Stopping.", len(clauses))
            break

        if len(clauses) < args.batch_size:
            break

    log.info("=== Done: %d processed, %d reclassified from 'other' ===",
             total_processed, total_reclassified)


if __name__ == "__main__":
    asyncio.run(main())
