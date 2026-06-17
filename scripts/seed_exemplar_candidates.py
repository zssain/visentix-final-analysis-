"""Seed exemplar candidates from highest-maturity existing clauses.

Per taxonomy domain, selects the top-N clauses scoring well on clarity
(low ambiguity, high readability, high NLP confidence) and inserts them
into the exemplar table with sme_cleaned=false.

Usage:
    python scripts/seed_exemplar_candidates.py
    python scripts/seed_exemplar_candidates.py --top 3
    python scripts/seed_exemplar_candidates.py --dry-run

Candidates are NOT customer-facing until an SME sets sme_cleaned=true.
"""

import argparse
import json
import logging

import httpx
from dotenv import dotenv_values
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_exemplars")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

# Domains to seed (skip "other" — too generic for exemplar use)
DOMAINS = [
    "data_sharing",
    "tracking_cookies",
    "consumer_rights",
    "cross_border",
    "sensitive_data",
    "retention",
    "children_teens",
    "ai_automated_decisions",
]


def fetch_top_clauses(domain: str, top_n: int) -> list[dict]:
    """Fetch the top-N clauses per domain ranked by quality.

    Quality = low ambiguity + high readability + high NLP confidence.
    PostgREST doesn't support computed sorts, so we fetch more and rank locally.
    """
    r = httpx.get(
        f"{URL}/rest/v1/disclosure_clause"
        f"?select=clause_id,normalized_text,ambiguity_score,readability_score,nlp_confidence,embedding"
        f"&category=eq.{domain}"
        f"&nlp_confidence=gte.0.7"
        f"&limit=50"
        f"&order=ambiguity_score.asc",
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    rows = r.json()

    # Rank: lowest ambiguity, then highest readability, then highest confidence
    rows.sort(key=lambda r: (
        r.get("ambiguity_score") or 1.0,
        -(r.get("readability_score") or 0.0),
        -(r.get("nlp_confidence") or 0.0),
    ))

    return rows[:top_n]


def check_existing_candidate(clause_id: str) -> bool:
    """Check if this clause is already seeded as an exemplar candidate."""
    ref = f"AUTO-CANDIDATE-{clause_id}"
    r = httpx.get(
        f"{URL}/rest/v1/exemplar?select=id&source_internal_ref=eq.{ref}&limit=1",
        headers=HEADERS,
        timeout=10,
    )
    return bool(r.json())


def insert_exemplar(
    domain: str,
    category: str,
    clause_text: str,
    clause_id: str,
    embedding: list[float] | None,
) -> bool:
    """Insert an exemplar candidate. Returns True if inserted."""
    ref = f"AUTO-CANDIDATE-{clause_id}"

    payload = {
        "domain": domain,
        "category": category,
        "clause_text": clause_text,
        "maturity_note": "AUTO-SEEDED CANDIDATE — awaiting SME review and de-identification.",
        "source_internal_ref": ref,
        "sme_cleaned": False,
    }
    if embedding:
        # PostgREST returns vectors as strings; computed ones are lists
        if isinstance(embedding, str):
            payload["embedding"] = embedding
        else:
            payload["embedding"] = json.dumps(embedding)

    r = httpx.post(
        f"{URL}/rest/v1/exemplar",
        headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return True


def main():
    parser = argparse.ArgumentParser(description="Seed exemplar candidates")
    parser.add_argument("--top", type=int, default=5, help="Max candidates per domain")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates without inserting")
    args = parser.parse_args()

    model = None
    total_seeded = 0

    for domain in DOMAINS:
        clauses = fetch_top_clauses(domain, args.top)
        log.info("=== %s: %d candidate(s) found ===", domain, len(clauses))

        inserted = 0
        for clause in clauses:
            cid = clause["clause_id"]

            if check_existing_candidate(cid):
                log.info("  SKIP %s (already seeded)", cid[:12])
                continue

            text = clause.get("normalized_text") or ""
            if not text.strip():
                continue

            # Use existing embedding if available, otherwise compute
            embedding = clause.get("embedding")
            if not embedding:
                if model is None:
                    log.info("Loading embedding model...")
                    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                embedding = model.encode(text).tolist()

            if args.dry_run:
                log.info(
                    "  [DRY-RUN] Would seed: %s amb=%.3f read=%.3f conf=%.2f text=%.60s...",
                    cid[:12],
                    clause.get("ambiguity_score", 0),
                    clause.get("readability_score", 0),
                    clause.get("nlp_confidence", 0),
                    text,
                )
            else:
                insert_exemplar(domain, domain, text, cid, embedding)
                inserted += 1
                log.info(
                    "  SEEDED %s amb=%.3f read=%.3f conf=%.2f",
                    cid[:12], clause.get("ambiguity_score", 0),
                    clause.get("readability_score", 0),
                    clause.get("nlp_confidence", 0),
                )

        total_seeded += inserted

    log.info("=== TOTAL: %d new candidates seeded ===", total_seeded)

    # Report final counts per domain
    r = httpx.get(
        f"{URL}/rest/v1/exemplar?select=domain,sme_cleaned",
        headers=HEADERS, timeout=15,
    )
    rows = r.json()
    from collections import Counter
    counts = Counter(row["domain"] for row in rows)
    auto = Counter(row["domain"] for row in rows if not row["sme_cleaned"])
    log.info("=== Exemplar counts per domain ===")
    for d in DOMAINS:
        log.info("  %s: %d total (%d auto-candidates)", d, counts.get(d, 0), auto.get(d, 0))


if __name__ == "__main__":
    main()
