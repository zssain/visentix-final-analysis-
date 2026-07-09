"""Backfill embeddings for new enforcement_record rows (embedding IS NULL).

Reuses the existing embed_backfill.py logic with all-MiniLM-L6-v2 (384-dim).
Idempotent + resumable: only processes rows where embedding IS NULL.

Usage:
    PYTHONPATH=. python scripts/ingest/embed_enforcement_new.py
    PYTHONPATH=. python scripts/ingest/embed_enforcement_new.py --dry-run
    PYTHONPATH=. python scripts/ingest/embed_enforcement_new.py --batch-size 128
"""

import argparse
import logging
import sys

# Reuse the existing backfill machinery
from scripts.embed_backfill import (
    backfill_table,
    count_nulls,
    count_total,
)
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("embed_enforcement_new")

TABLE = "enforcement_record"


def main():
    parser = argparse.ArgumentParser(description="Backfill enforcement_record embeddings")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    total = count_total(TABLE)
    nulls = count_nulls(TABLE)
    log.info("%s: %d total, %d NULL embeddings", TABLE, total, nulls)

    if nulls == 0:
        log.info("Nothing to do — 0 NULL embeddings.")
        return

    log.info("Loading model: all-MiniLM-L6-v2 ...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    log.info("Model loaded (dim=%d)", model.get_sentence_embedding_dimension())

    updated = backfill_table(model, TABLE, batch_size=args.batch_size, dry_run=args.dry_run)

    if not args.dry_run:
        nulls_after = count_nulls(TABLE)
        log.info("DONE: updated=%d, nulls_before=%d, nulls_after=%d", updated, nulls, nulls_after)

        if nulls_after > 0:
            log.warning("%d rows still have NULL embedding (empty text?)", nulls_after)
    else:
        log.info("[DRY-RUN] Would embed %d rows", updated)


if __name__ == "__main__":
    main()
