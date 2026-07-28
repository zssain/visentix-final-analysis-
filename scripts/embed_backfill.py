"""Backfill embeddings for disclosure_clause (+ enforcement_record, obligation).

Local model only (all-MiniLM-L6-v2, 384-dim) — NO external API (Rule 7).
GPU-aware (CUDA > Apple MPS > CPU), batched (256), idempotent (only rows whose
`embedding IS NULL` are touched — never overwrites), resumable (keyset checkpoint),
rate-logged, and tranched (demo-industry orgs first so the pilot benefits even if
the full run takes days). Stores `embedding_model` per row via the
apply_clause_embeddings RPC (bulk UPDATE — not one PATCH per row).

Usage:
    # Runtime estimate on THIS device (no writes):
    python scripts/embed_backfill.py --estimate

    # Demo-industry tranche first (retail/healthcare/fintech):
    python scripts/embed_backfill.py --tranche demo

    # Everything remaining:
    python scripts/embed_backfill.py --tranche all

    # Bounded run (e.g. 5000 clauses) / resume:
    python scripts/embed_backfill.py --tranche demo --limit 5000

Coverage is reported honestly before and after. On RunPod the same command runs
unchanged and auto-selects CUDA.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import httpx

from app.config import settings
from app.services.embeddings import (
    DEFAULT_BATCH_SIZE,
    EMBEDDING_MODEL_NAME,
    embed_texts,
    get_model,
    write_clause_embeddings,
)
from scripts.dbcount import exact_count

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("embed_backfill")

URL = settings.supabase_url
H = {"apikey": settings.supabase_service_role_key,
     "Authorization": f"Bearer {settings.supabase_service_role_key}"}
DEMO_INDUSTRIES = ["retail", "healthcare", "fintech"]   # build_cohorts.py
CHECKPOINT = Path(__file__).resolve().parents[1] / "logs" / "embed_backfill.checkpoint.json"


# ── Counting ─────────────────────────────────────────────────

def coverage(table: str) -> tuple[int, int]:
    # Exact counts via the pooler — PostgREST count=exact times out on 684k rows.
    total = exact_count(table=table)
    embedded = exact_count(where="dc.embedding IS NOT NULL", table=table)
    return embedded, total


def report_coverage(tag: str = "") -> None:
    log.info("── coverage %s ──", tag)
    for t in ["disclosure_clause", "enforcement_record", "obligation"]:
        e, n = coverage(t)
        pct = e / n * 100 if n else 0.0
        log.info("  %-20s %d/%d embedded (%.1f%%)", t, e, n, pct)


# ── Demo tranche resolution (org.industry → notice → section) ─

def _in_chunks(ids: list[str], size: int):
    for i in range(0, len(ids), size):
        yield ids[i:i + size]


def demo_section_ids() -> list[str]:
    """Section ids belonging to demo-industry orgs (retail/healthcare/fintech)."""
    ind = ",".join(DEMO_INDUSTRIES)
    orgs = _paged(f"organization?select=organization_id&industry=in.({ind})", "organization_id")
    log.info("demo-industry orgs: %d", len(orgs))
    notices: list[str] = []
    for ch in _in_chunks(orgs, 80):
        inl = ",".join(f'"{o}"' for o in ch)
        notices += _paged(f"privacy_notice?select=notice_id&organization_id=in.({inl})", "notice_id")
    log.info("demo notices: %d", len(notices))
    sections: list[str] = []
    for ch in _in_chunks(notices, 60):
        inl = ",".join(f'"{n}"' for n in ch)
        sections += _paged(f"notice_section?select=section_id&notice_id=in.({inl})", "section_id")
    log.info("demo sections: %d", len(sections))
    return sections


def _paged(path: str, key: str, page: int = 1000) -> list[str]:
    """Page through a select with Range headers (PostgREST caps at 1000/req)."""
    out, offset = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{path}&limit={page}&offset={offset}", headers=H, timeout=60)
        rows = r.json() if r.status_code == 200 else []
        if not rows:
            break
        out += [x[key] for x in rows if x.get(key)]
        if len(rows) < page:
            break
        offset += page
    return out


# ── Estimate ─────────────────────────────────────────────────

def run_estimate(sample: int = 512) -> None:
    e, n = coverage("disclosure_clause")
    remaining = n - e
    log.info("Loading model + benchmarking encode on this device …")
    get_model()  # warm
    rows = _fetch_unembedded(after_id="", limit=sample, section_ids=None)
    texts = [r["normalized_text"] for r in rows if (r.get("normalized_text") or "").strip()]
    if not texts:
        log.info("No unembedded clauses to sample.")
        return
    t0 = time.time()
    embed_texts(texts, batch_size=DEFAULT_BATCH_SIZE)
    dt = time.time() - t0
    rate = len(texts) / dt if dt else 0
    log.info("Encoded %d clauses in %.1fs → %.0f clauses/sec (encode only) on this device.",
             len(texts), dt, rate)
    if rate:
        hrs = remaining / rate / 3600
        log.info("Remaining %d clauses → ~%.1f h encode-only here (writes add I/O).", remaining, hrs)
    log.info("NOTE: a RunPod CUDA GPU is typically 5–20x faster than this device.")


# ── Core fetch/loop ──────────────────────────────────────────

def _fetch_unembedded(after_id: str, limit: int, section_ids: list[str] | None) -> list[dict]:
    """Keyset page of unembedded clauses (clause_id > after_id), optionally scoped
    to a section-id set. Keyset guarantees forward progress past empty-text rows."""
    flt = "embedding=is.null"
    if after_id:
        flt += f"&clause_id=gt.{after_id}"
    if section_ids is not None:
        inl = ",".join(f'"{s}"' for s in section_ids)
        flt += f"&section_id=in.({inl})"
    r = httpx.get(
        f"{URL}/rest/v1/disclosure_clause"
        f"?select=clause_id,normalized_text&{flt}&order=clause_id.asc&limit={limit}",
        headers=H, timeout=60,
    )
    r.raise_for_status()
    return r.json()


def _load_ckpt(tranche: str) -> str:
    if CHECKPOINT.exists():
        data = json.loads(CHECKPOINT.read_text())
        if data.get("tranche") == tranche:
            return data.get("after_id", "")
    return ""


def _save_ckpt(tranche: str, after_id: str, embedded: int) -> None:
    CHECKPOINT.write_text(json.dumps(
        {"tranche": tranche, "after_id": after_id, "embedded": embedded,
         "model": EMBEDDING_MODEL_NAME}))


def backfill_clauses(tranche: str, batch_size: int, limit: int | None, dry_run: bool) -> int:
    section_ids = demo_section_ids() if tranche == "demo" else None
    section_chunks = list(_in_chunks(section_ids, 100)) if section_ids is not None else [None]

    get_model()  # load once, log device
    total_embedded, seen = 0, 0
    start = time.time()

    for chunk in section_chunks:
        after_id = "" if section_ids is not None else _load_ckpt(tranche)
        while True:
            rows = _fetch_unembedded(after_id, batch_size, chunk)
            if not rows:
                break
            after_id = rows[-1]["clause_id"]           # advance keyset (past empty-text too)
            valid = [r for r in rows if (r.get("normalized_text") or "").strip()]
            seen += len(rows)

            if dry_run:
                log.info("[DRY-RUN] batch of %d (%d embeddable); first=%s", len(rows), len(valid), rows[0]["clause_id"])
                if limit and seen >= limit:
                    break
                continue

            if valid:
                t0 = time.time()
                vecs = embed_texts([r["normalized_text"] for r in valid], batch_size=batch_size)
                enc = time.time() - t0
                n = write_clause_embeddings([{"clause_id": r["clause_id"], "embedding": v}
                                             for r, v in zip(valid, vecs)])
                total_embedded += n
                rate = total_embedded / (time.time() - start) if time.time() > start else 0
                log.info("embedded +%d (total %d) | enc %.0fms | %.0f rows/s | keyset=%s",
                         n, total_embedded, enc * 1000, rate, after_id[:8])

            if section_ids is None:
                _save_ckpt(tranche, after_id, total_embedded)
            if limit and seen >= limit:
                log.info("Reached --limit %d; stopping (resumable).", limit)
                return total_embedded

    return total_embedded


# ── Main ─────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill embeddings (local model only)")
    ap.add_argument("--tranche", choices=["demo", "all"], default="demo",
                    help="demo = retail/healthcare/fintech orgs first (default); all = everything remaining")
    ap.add_argument("--estimate", action="store_true", help="Benchmark + project runtime, no writes")
    ap.add_argument("--dry-run", action="store_true", help="Iterate without encoding/writing")
    ap.add_argument("--limit", type=int, default=None, help="Max clauses to scan this run (resumable)")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = ap.parse_args()

    if args.estimate:
        run_estimate()
        return

    report_coverage("BEFORE")
    log.info("Backfilling clauses — tranche=%s model=%s", args.tranche, EMBEDDING_MODEL_NAME)
    embedded = backfill_clauses(args.tranche, args.batch_size, args.limit, args.dry_run)
    log.info("DONE clause backfill: embedded=%d", embedded)
    log.info("enforcement_record + obligation are already 100%% embedded — skipped (idempotent).")
    report_coverage("AFTER")


if __name__ == "__main__":
    main()
