"""Match disclosure clauses to obligations via embedding similarity.

Populates clause_obligation rows with match_method='embedding' and
cosine similarity scores. Only writes NEW rows — never touches
existing clause_obligation data.

Usage:
    PYTHONPATH=. python scripts/match_clause_obligations.py
    PYTHONPATH=. python scripts/match_clause_obligations.py --dry-run
    PYTHONPATH=. python scripts/match_clause_obligations.py --threshold 0.45
"""

import argparse
import json
import logging
import time

import httpx
import numpy as np
from dotenv import dotenv_values
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("match_obligations")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

DEFAULT_THRESHOLD = 0.40  # cosine similarity threshold for a match


def fetch_all(table, select, limit=1000):
    rows, offset = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{table}?select={select}&offset={offset}&limit={limit}",
                       headers=H, timeout=30)
        rows.extend(r.json())
        if len(r.json()) < limit:
            break
        offset += limit
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    log.info("Loading obligations...")
    obligations = fetch_all("obligation", "obligation_id,jurisdiction,law,domain,requirement_type,applicability")
    log.info(f"  {len(obligations)} obligations")

    log.info("Loading clause embeddings (sampling 500 from non-other categories)...")
    clauses = fetch_all("disclosure_clause",
                        "clause_id,category,normalized_text,embedding",
                        limit=500)
    # Filter to clauses with embeddings and non-other category
    clauses_with_emb = [c for c in clauses if c.get("embedding") and c["category"] != "other"]
    log.info(f"  {len(clauses_with_emb)} clauses with embeddings (non-other)")

    if not clauses_with_emb or not obligations:
        log.info("Nothing to match.")
        return

    # Embed obligations (they don't have embeddings yet — compute on the fly)
    log.info("Loading embedding model...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    obligation_texts = []
    for ob in obligations:
        text = f"{ob.get('law', '')} {ob.get('domain', '')} {ob.get('requirement_type', '')} {ob.get('applicability', '')}"
        obligation_texts.append(text.strip())

    log.info("Encoding obligations...")
    ob_embeddings = model.encode(obligation_texts, show_progress_bar=False)
    ob_norms = ob_embeddings / (np.linalg.norm(ob_embeddings, axis=1, keepdims=True) + 1e-9)

    # Parse clause embeddings
    clause_vecs = []
    for c in clauses_with_emb:
        emb = c["embedding"]
        if isinstance(emb, str):
            emb = json.loads(emb)
        clause_vecs.append(emb)

    clause_matrix = np.array(clause_vecs)
    clause_norms = clause_matrix / (np.linalg.norm(clause_matrix, axis=1, keepdims=True) + 1e-9)

    # Compute similarity matrix
    log.info("Computing similarity matrix...")
    sim_matrix = clause_norms @ ob_norms.T  # (n_clauses, n_obligations)

    # Find matches above threshold
    matches = []
    for i, clause in enumerate(clauses_with_emb):
        for j, ob in enumerate(obligations):
            sim = float(sim_matrix[i, j])
            if sim >= args.threshold:
                matches.append({
                    "clause_id": clause["clause_id"],
                    "obligation_id": ob["obligation_id"],
                    "match_method": "embedding",
                    "similarity": round(sim, 4),
                })

    log.info(f"Found {len(matches)} matches above threshold {args.threshold}")

    if args.dry_run:
        for m in matches[:10]:
            log.info(f"  [DRY-RUN] clause={m['clause_id'][:12]} → obligation={m['obligation_id'][:12]} sim={m['similarity']}")
        log.info(f"  [DRY-RUN] Would insert {len(matches)} rows")
        return

    # Insert in batches (with retry)
    inserted = 0
    for m in matches:
        for attempt in range(3):
            try:
                r = httpx.post(f"{URL}/rest/v1/clause_obligation",
                               headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                               json=m, timeout=15)
                if r.status_code in (200, 201):
                    inserted += 1
                    break
                elif r.status_code == 409:
                    break  # duplicate
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt < 2:
                    time.sleep(2 ** attempt)

    log.info(f"Inserted {inserted} clause_obligation rows")


if __name__ == "__main__":
    main()
