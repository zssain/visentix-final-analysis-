"""Backfill NULL embeddings for disclosure_clause and enforcement_record.

Usage:
    # Dry-run (10 rows, prints dims, no writes):
    python scripts/embed_backfill.py --dry-run

    # Full backfill:
    python scripts/embed_backfill.py

    # Single table:
    python scripts/embed_backfill.py --table disclosure_clause
    python scripts/embed_backfill.py --table enforcement_record

Resumable: only processes rows WHERE embedding IS NULL.
Idempotent: re-running updates 0 rows if all are filled.
Only touches the embedding column — no other columns modified.
"""

import argparse
import json
import logging
import sys
import time

import httpx
from dotenv import dotenv_values
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("embed_backfill")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
}

# Table configs: (pk_column, text_builder)
TABLE_CONFIGS = {
    "disclosure_clause": {
        "pk": "clause_id",
        "text_field": "normalized_text",
        "build_text": lambda row: row.get("normalized_text") or "",
    },
    "enforcement_record": {
        "pk": "enforcement_id",
        "text_field": "summary,issue_tags",
        "build_text": lambda row: _enforcement_text(row),
    },
}


def _enforcement_text(row: dict) -> str:
    """Build embedding text from enforcement summary + issue_tags."""
    parts = []
    if row.get("summary"):
        parts.append(row["summary"])
    tags = row.get("issue_tags")
    if tags:
        if isinstance(tags, list):
            parts.append(" ".join(tags))
        elif isinstance(tags, str):
            parts.append(tags)
    # Fallback to target_company if no summary
    if not parts and row.get("target_company"):
        parts.append(row["target_company"])
    return " ".join(parts)


def fetch_null_batch(table: str, pk: str, select_fields: str, limit: int) -> list[dict]:
    """Fetch a batch of rows where embedding IS NULL."""
    r = httpx.get(
        f"{URL}/rest/v1/{table}"
        f"?select={pk},{select_fields}"
        f"&embedding=is.null"
        f"&limit={limit}"
        f"&order={pk}",
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def update_embedding(table: str, pk: str, pk_value: str, embedding: list[float], retries: int = 3) -> None:
    """UPDATE only the embedding column for a single row by PK."""
    for attempt in range(retries):
        try:
            r = httpx.patch(
                f"{URL}/rest/v1/{table}?{pk}=eq.{pk_value}",
                headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json={"embedding": json.dumps(embedding)},
                timeout=30,
            )
            r.raise_for_status()
            return
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            if attempt < retries - 1:
                wait = 2 ** attempt
                log.warning("Timeout on %s=%s, retrying in %ds (%d/%d)", pk, pk_value, wait, attempt + 1, retries)
                time.sleep(wait)
            else:
                raise


def backfill_table(
    model: SentenceTransformer,
    table: str,
    batch_size: int = 256,
    dry_run: bool = False,
) -> int:
    """Backfill embeddings for a single table. Returns total rows updated."""
    cfg = TABLE_CONFIGS[table]
    pk = cfg["pk"]
    build_text = cfg["build_text"]

    # Determine select fields based on table
    if table == "disclosure_clause":
        select = "normalized_text"
    else:
        select = "summary,issue_tags,target_company"

    total_updated = 0
    batch_num = 0

    while True:
        limit = 10 if dry_run else batch_size
        rows = fetch_null_batch(table, pk, select, limit)

        if not rows:
            break

        batch_num += 1
        texts = [build_text(row) for row in rows]

        # Filter out empty texts
        valid = [(row, text) for row, text in zip(rows, texts) if text.strip()]
        if not valid:
            log.warning("Batch %d: all texts empty, skipping", batch_num)
            break

        valid_rows, valid_texts = zip(*valid)

        t0 = time.time()
        embeddings = model.encode(list(valid_texts), show_progress_bar=False)
        encode_ms = (time.time() - t0) * 1000

        log.info(
            "Batch %d: encoded %d rows in %.0fms (dim=%d)",
            batch_num, len(valid_rows), encode_ms, embeddings.shape[1],
        )

        if dry_run:
            for i, (row, emb) in enumerate(zip(valid_rows, embeddings)):
                log.info(
                    "  [DRY-RUN] %s=%s dim=%d first_3=%s",
                    pk, row[pk], len(emb), emb[:3].tolist(),
                )
            log.info("[DRY-RUN] Would update %d rows. Stopping.", len(valid_rows))
            return len(valid_rows)

        # Write embeddings one by one (safe, idempotent)
        for row, emb in zip(valid_rows, embeddings):
            update_embedding(table, pk, row[pk], emb.tolist())

        total_updated += len(valid_rows)
        log.info("Progress: %d rows updated so far", total_updated)

    return total_updated


def count_nulls(table: str) -> int:
    """Count rows where embedding IS NULL."""
    r = httpx.get(
        f"{URL}/rest/v1/{table}?select=*&embedding=is.null&limit=0",
        headers={**HEADERS, "Prefer": "count=exact"},
        timeout=15,
    )
    r.raise_for_status()
    cr = r.headers.get("content-range", "*/0")
    return int(cr.split("/")[-1])


def count_total(table: str) -> int:
    """Count total rows."""
    r = httpx.get(
        f"{URL}/rest/v1/{table}?select=*&limit=0",
        headers={**HEADERS, "Prefer": "count=exact"},
        timeout=15,
    )
    r.raise_for_status()
    cr = r.headers.get("content-range", "*/0")
    return int(cr.split("/")[-1])


def main():
    parser = argparse.ArgumentParser(description="Backfill NULL embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Embed 10 rows, print dims, no writes")
    parser.add_argument("--table", choices=list(TABLE_CONFIGS.keys()), help="Run on a single table")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size (default 256)")
    args = parser.parse_args()

    tables = [args.table] if args.table else list(TABLE_CONFIGS.keys())

    log.info("Loading model: all-MiniLM-L6-v2 ...")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    log.info("Model loaded (dim=%d)", model.get_sentence_embedding_dimension())

    for table in tables:
        total = count_total(table)
        nulls_before = count_nulls(table)
        log.info("=== %s: %d total rows, %d NULL embeddings ===", table, total, nulls_before)

        if nulls_before == 0:
            log.info("Nothing to do — 0 NULL embeddings.")
            continue

        updated = backfill_table(model, table, batch_size=args.batch_size, dry_run=args.dry_run)

        if not args.dry_run:
            nulls_after = count_nulls(table)
            log.info(
                "DONE %s: updated=%d, nulls_before=%d, nulls_after=%d",
                table, updated, nulls_before, nulls_after,
            )
        else:
            log.info("[DRY-RUN] %s: would start with %d NULL rows", table, nulls_before)


if __name__ == "__main__":
    main()
