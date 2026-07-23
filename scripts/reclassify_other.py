"""Reclassify ALL clauses with a NULL category_v2 via local Qwen3-8B — ADDITIVE ONLY.

Writes ONLY category_v2 / nlp_confidence_v2 / classifier_version; NEVER overwrites the
base `category` / `nlp_confidence`. Idempotent + resumable: it only ever selects rows
where `category_v2 IS NULL`, so each written row drops out of the work set and the job
can be stopped/restarted freely (mirror of the embedding backfill). Counts are logged.

Shares the exact taxonomy + classifier_version + classify function with the intake path
(`app/services/intake/classify_v2.py`), so ingest-time and batch labels are identical.

    PYTHONPATH=. python scripts/reclassify_other.py --dry-run
    PYTHONPATH=. python scripts/reclassify_other.py            # run to completion
    PYTHONPATH=. python scripts/reclassify_other.py --concurrency 6 --batch-size 200
"""
import argparse
import asyncio
import logging
import time
from collections import Counter

import httpx
from dotenv import dotenv_values

from app.services.intake.classify_v2 import CLASSIFIER_VERSION, classify_one
from app.services.llm import get_llm_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reclassify_v2")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def null_v2_count() -> int:
    r = httpx.get(f"{URL}/rest/v1/disclosure_clause?select=clause_id&category_v2=is.null",
                  headers={**H, "Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"},
                  timeout=30)
    return int(r.headers.get("content-range", "*/0").split("/")[-1])


def fetch_null_v2(limit: int) -> list[dict]:
    """Fetch clauses with category_v2 IS NULL. Always offset 0 — rows drop out as they
    are written, so this is inherently resumable."""
    r = httpx.get(f"{URL}/rest/v1/disclosure_clause"
                  f"?select=clause_id,normalized_text&category_v2=is.null&limit={limit}",
                  headers=H, timeout=30)
    return r.json() if r.status_code < 300 else []


def update_clause_v2(clause_id: str, category_v2: str, confidence_v2: float) -> bool:
    # Retry ALL transport-level transients (connect/read timeout, connection reset,
    # pool timeout) — a single blip during a multi-hour run must not crash the job.
    for attempt in range(5):
        try:
            r = httpx.patch(f"{URL}/rest/v1/disclosure_clause?clause_id=eq.{clause_id}",
                            headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                            json={"category_v2": category_v2, "nlp_confidence_v2": confidence_v2,
                                  "classifier_version": CLASSIFIER_VERSION}, timeout=30)
            if r.status_code < 300:
                return True
            if r.status_code < 500:          # 4xx won't fix on retry
                return False
        except httpx.TransportError:         # ConnectTimeout/ReadTimeout/ConnectError/PoolTimeout/…
            pass
        if attempt < 4:
            time.sleep(min(2 ** attempt, 10))
    return False


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    llm = get_llm_client()
    llm._backend = "local"                      # batch work runs on local Ollama, never hosted
    before = null_v2_count()
    log.info("LLM backend=local · category_v2 IS NULL before: %d", before)

    sem = asyncio.Semaphore(args.concurrency)
    processed = 0
    dist: Counter = Counter()
    stuck: set[str] = set()          # rows that failed to write after all retries — skip on re-fetch
    t0 = time.time()

    async def _one(clause: dict):
        nonlocal processed
        cid = clause["clause_id"]
        text = clause.get("normalized_text", "")
        if len(text) < 20:
            cat, conf = "other", 0.3   # too short to classify meaningfully
        else:
            async with sem:
                cat, conf = await classify_one(llm, text)
        if not args.dry_run and not update_clause_v2(cid, cat, conf):
            stuck.add(cid)             # write failed even after retries — don't loop on it
            return
        dist[cat] += 1
        processed += 1
        if processed % 100 == 0:
            rate = processed / max(1e-6, time.time() - t0)
            log.info("progress: %d/%d processed (%.1f/s) dist=%s stuck=%d",
                     processed, before, rate, dict(dist), len(stuck))

    while True:
        batch = fetch_null_v2(10 if args.dry_run else args.batch_size)
        fresh = [c for c in batch if c["clause_id"] not in stuck]
        if not fresh:
            if batch:
                log.warning("only stuck rows remain (%d) — stopping", len(stuck))
            break
        await asyncio.gather(*[_one(c) for c in fresh])
        if args.dry_run:
            log.info("[DRY-RUN] sample of %d classified: %s", len(fresh), dict(dist))
            break

    after = 0 if args.dry_run else null_v2_count()
    log.info("=== DONE: processed=%d · category_v2 NULL %d -> %d · distribution=%s ===",
             processed, before, after, dict(dist))


if __name__ == "__main__":
    asyncio.run(main())
