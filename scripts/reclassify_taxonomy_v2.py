"""Backfill domain_id, clause_type, transparency_score on existing disclosure_clause rows.

Uses the same classify_clause_v2 + compute_transparency from decompose.py.
Does NOT change the `category` column — existing scoring is untouched.
Idempotent: skips rows that already have domain_id populated.

Usage:
    python scripts/reclassify_taxonomy_v2.py
    python scripts/reclassify_taxonomy_v2.py --dry-run
"""

import argparse
import logging

import httpx
from dotenv import dotenv_values

from app.services.intake.decompose import classify_clause_v2, compute_transparency

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reclassify_taxonomy_v2")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def fetch_all(table: str, select: str, filters: str = "", limit: int = 1000) -> list[dict]:
    rows = []
    offset = 0
    while True:
        qs = f"select={select}&offset={offset}&limit={limit}"
        if filters:
            qs += f"&{filters}"
        r = httpx.get(f"{URL}/rest/v1/{table}?{qs}", headers=H, timeout=30)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def update_clause(clause_id: str, domain_id: str, clause_type: str,
                  transparency_score: float) -> None:
    headers = {**H, "Content-Type": "application/json", "Prefer": "return=minimal"}
    r = httpx.patch(
        f"{URL}/rest/v1/disclosure_clause?clause_id=eq.{clause_id}",
        headers=headers,
        json={
            "domain_id": domain_id,
            "clause_type": clause_type,
            "transparency_score": round(transparency_score, 4),
        },
        timeout=15,
    )
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info("Loading clauses...")
    clauses = fetch_all(
        "disclosure_clause",
        "clause_id,raw_text,category,domain_id",
    )
    log.info("Loaded %d clauses", len(clauses))

    updated = 0
    skipped = 0

    for c in clauses:
        # Skip already-classified rows (idempotent)
        if c.get("domain_id"):
            skipped += 1
            continue

        raw = c.get("raw_text") or ""
        if not raw.strip():
            skipped += 1
            continue

        domain_id, clause_type, _legacy, confidence = classify_clause_v2(raw)
        transparency = compute_transparency(raw)

        if args.dry_run:
            log.info(
                "[DRY-RUN] %s → %s/%s (legacy=%s conf=%.2f trans=%.4f)",
                c["clause_id"][:12], domain_id, clause_type, _legacy,
                confidence, transparency,
            )
        else:
            update_clause(c["clause_id"], domain_id, clause_type, transparency)

        updated += 1

    log.info("=== Done: %d updated, %d skipped ===", updated, skipped)


if __name__ == "__main__":
    main()
