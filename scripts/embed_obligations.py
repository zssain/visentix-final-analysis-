"""Backfill NULL embeddings on obligation table.

Embeds the obligation's requirement text (law + domain + requirement_type +
applicability) with all-MiniLM-L6-v2 (384-dim). UPDATE only the embedding
column by PK. Idempotent + resumable (only NULL rows).

Usage:
    PYTHONPATH=. python scripts/embed_obligations.py
    PYTHONPATH=. python scripts/embed_obligations.py --dry-run
"""

import argparse
import json
import logging
import time

import httpx
from dotenv import dotenv_values
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("embed_obligations")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def build_text(ob: dict) -> str:
    """Build embedding text from obligation fields."""
    parts = [
        ob.get("law") or "",
        ob.get("domain") or "",
        ob.get("requirement_type") or "",
        ob.get("applicability") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Fetch obligations with NULL embedding
    r = httpx.get(
        f"{URL}/rest/v1/obligation?select=obligation_id,law,domain,requirement_type,applicability"
        f"&embedding=is.null&order=obligation_id",
        headers=H, timeout=15,
    )
    obligations = r.json()
    log.info("Obligations with NULL embedding: %d", len(obligations))

    if not obligations:
        log.info("Nothing to do.")
        return

    log.info("Loading model: all-MiniLM-L6-v2")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    texts = [build_text(ob) for ob in obligations]
    valid = [(ob, t) for ob, t in zip(obligations, texts) if t]

    if args.dry_run:
        for ob, t in valid[:5]:
            vec = model.encode(t)
            log.info("[DRY-RUN] %s dim=%d text=%s...", ob["obligation_id"][:12], len(vec), t[:60])
        log.info("[DRY-RUN] Would embed %d obligations", len(valid))
        return

    log.info("Encoding %d obligations...", len(valid))
    all_texts = [t for _, t in valid]
    embeddings = model.encode(all_texts, show_progress_bar=False)
    log.info("Encoded. Dim=%d", embeddings.shape[1])

    updated = 0
    for (ob, _), emb in zip(valid, embeddings):
        for attempt in range(3):
            try:
                r = httpx.patch(
                    f"{URL}/rest/v1/obligation?obligation_id=eq.{ob['obligation_id']}",
                    headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json={"embedding": json.dumps(emb.tolist())},
                    timeout=30,
                )
                if r.status_code < 300:
                    updated += 1
                    break
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt < 2:
                    time.sleep(2 ** attempt)

    log.info("Updated %d obligation embeddings", updated)

    # Verify
    r = httpx.get(f"{URL}/rest/v1/obligation?select=obligation_id&embedding=is.null&limit=0",
                   headers={**H, "Prefer": "count=exact"}, timeout=15)
    remaining = r.headers.get("content-range", "*/0").split("/")[-1]
    log.info("Remaining NULL: %s", remaining)


if __name__ == "__main__":
    main()
