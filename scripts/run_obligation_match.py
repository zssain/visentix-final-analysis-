"""Activate Part-B clause→obligation matching over EMBEDDED clauses.

Populates `clause_obligation` (similarity + matched_terms + model_version) using
the existing matcher (`obligation_match.match_clauses_to_obligations`) — its 0.35
similarity floor and "exposure context only" framing are UNCHANGED.

HARD GATE (MUST NOT run on <95% coverage and present as complete): the runner
refuses unless the target scope's clause embedding coverage is ≥ --min-coverage.
Idempotent: upserts on the (clause_id, obligation_id) primary key.

Usage:
    python scripts/run_obligation_match.py --scope all               # whole embedded corpus
    python scripts/run_obligation_match.py --scope org --org <uuid>  # one org
    python scripts/run_obligation_match.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re

import httpx

from app.config import settings
from app.services.embeddings import EMBEDDING_MODEL_NAME
from app.services.scoring.obligation_match import (
    SIMILARITY_FLOOR,
    match_clauses_to_obligations,
)
from scripts.dbcount import exact_count

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_obligation_match")

URL = settings.supabase_url
H = {"apikey": settings.supabase_service_role_key,
     "Authorization": f"Bearer {settings.supabase_service_role_key}"}
_WORD = re.compile(r"\b[a-z]{4,}\b")


def _section_filter(scope: str, org: str | None) -> str:
    """Return a PostgREST filter fragment scoping clauses to org's sections, or ''."""
    if scope != "org" or not org:
        return ""
    notices = _paged(f"privacy_notice?select=notice_id&organization_id=eq.{org}", "notice_id")
    secs = []
    for i in range(0, len(notices), 60):
        inl = ",".join(f'"{n}"' for n in notices[i:i + 60])
        secs += _paged(f"notice_section?select=section_id&notice_id=in.({inl})", "section_id")
    if not secs:
        return "&section_id=in.()"
    inl = ",".join(f'"{s}"' for s in secs)
    return f"&section_id=in.({inl})"


def _paged(path: str, key: str, page: int = 1000) -> list:
    out, off = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{path}&limit={page}&offset={off}", headers=H, timeout=90)
        rows = r.json() if r.status_code == 200 else []
        if not rows:
            break
        out += [x[key] if key else x for x in rows]
        if len(rows) < page:
            break
        off += page
    return out


def coverage(scope: str, org: str | None) -> tuple[int, int, float]:
    """Exact embedding coverage for the scope (via pooler — REST count times out)."""
    joins, where = "", "dc.is_noise = false"
    if scope == "org" and org:
        joins = ("JOIN notice_section ns ON dc.section_id = ns.section_id "
                 "JOIN privacy_notice pn ON ns.notice_id = pn.notice_id")
        where += f" AND pn.organization_id = '{org}'"
    total = exact_count(where=where, joins=joins)
    emb = exact_count(where=where + " AND dc.embedding IS NOT NULL", joins=joins)
    return emb, total, (emb / total if total else 0.0)


def matched_terms(clause_text: str, ob: dict) -> list[str]:
    ob_text = " ".join([ob.get("law") or "", ob.get("requirement_type") or "",
                        ob.get("applicability") or ""]).lower()
    return sorted(set(_WORD.findall(ob_text)) & set(_WORD.findall((clause_text or "").lower())))


def load_obligations() -> list[dict]:
    return _paged("obligation?select=obligation_id,domain,embedding,effective_date,law,"
                  "requirement_type,applicability&embedding=not.is.null", None)


def upsert(rows: list[dict]) -> None:
    r = httpx.post(
        f"{URL}/rest/v1/clause_obligation?on_conflict=clause_id,obligation_id",
        headers={**H, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=rows, timeout=90,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"clause_obligation upsert failed: {r.status_code} {r.text[:200]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["all", "org"], default="all")
    ap.add_argument("--org", help="organization_id when --scope org")
    ap.add_argument("--min-coverage", type=float, default=0.95)
    ap.add_argument("--limit", type=int, default=None, help="max clauses to match this run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    emb, total, cov = coverage(args.scope, args.org)
    log.info("Scope=%s coverage: %d/%d substantive clauses embedded (%.1f%%)", args.scope, emb, total, cov * 100)
    sf = _section_filter(args.scope, args.org)

    # HARD GATE — never match a cohort below the coverage floor.
    if cov < args.min_coverage:
        log.error("REFUSING: coverage %.1f%% < required %.1f%%. Finish the embedding "
                  "backfill for this scope first (MUST NOT present partial as complete).",
                  cov * 100, args.min_coverage * 100)
        raise SystemExit(2)

    obligations = load_obligations()
    log.info("Loaded %d embedded obligations. Similarity floor=%.2f (unchanged).", len(obligations), SIMILARITY_FLOOR)

    written, scanned = 0, 0
    off = 0
    while True:
        page = httpx.get(
            f"{URL}/rest/v1/disclosure_clause"
            f"?select=clause_id,category,normalized_text,embedding"
            f"&is_noise=eq.false&embedding=not.is.null{sf}"
            f"&order=clause_id.asc&limit=500&offset={off}",
            headers=H, timeout=90,
        ).json()
        if not page:
            break
        off += len(page)
        scanned += len(page)

        matches = match_clauses_to_obligations(page, obligations, similarity_floor=SIMILARITY_FLOOR)
        ob_by_id = {o["obligation_id"]: o for o in obligations}
        text_by_id = {c["clause_id"]: c.get("normalized_text", "") for c in page}
        rows = [{
            "clause_id": m.clause_id,
            "obligation_id": m.obligation_id,
            "match_method": m.match_method,
            "similarity": m.similarity,
            "matched_terms": json.dumps(matched_terms(text_by_id.get(m.clause_id, ""),
                                                       ob_by_id.get(m.obligation_id, {}))),
            "model_version": EMBEDDING_MODEL_NAME,
        } for m in matches]

        if rows and not args.dry_run:
            upsert(rows)
        written += len(rows)
        log.info("scanned %d clauses | matches this page %d | total written %d", scanned, len(rows), written)

        if args.limit and scanned >= args.limit:
            log.info("Reached --limit %d; stopping.", args.limit)
            break

    log.info("DONE: %d clause_obligation rows %s (scope=%s).",
             written, "would write [dry-run]" if args.dry_run else "written", args.scope)


if __name__ == "__main__":
    main()
