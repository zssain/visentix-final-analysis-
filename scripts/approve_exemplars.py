"""Phase-5 F06 exemplar pipeline — select, de-id-check, approve (attributed ai_reviewed).

Marks >=1 strong, GENUINELY de-identified clause per demo domain as
disclosure_clause.is_exemplar=true, exemplar_status='approved' (unblocks M-03:
BenchmarkLanguage reads `disclosure_clause WHERE is_exemplar = true`).

De-id safety: a clause is only approved if its text PASSES validate_deidentification
with the org's OWN name added as a blocked token — so no org name / email / URL can
reach the BenchmarkLanguage surface. Candidates that fail the checker are skipped
(never force-cleaned in place — we never overwrite raw_text/normalized_text). The human
SME re-reviews before any client delivery.

Run:
    PYTHONPATH=. python scripts/approve_exemplars.py --per-domain 1
    PYTHONPATH=. python scripts/approve_exemplars.py --dry-run
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
from pathlib import Path

from app.services.exemplar_review import validate_deidentification, validate_exemplar_for_approval

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("approve_exemplars")

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)

# The eight demo domains (category_v2 slugs), excluding the 'other' bucket.
DEMO_DOMAINS = ["consumer_rights", "data_sharing", "retention", "ai_automated_decisions",
                "tracking_cookies", "children_teens", "cross_border", "sensitive_data"]


def _org_tokens(name: str | None) -> set[str]:
    """Blocked tokens derived from an org name (whole name + significant words)."""
    if not name:
        return set()
    toks = {name.lower()}
    for w in name.replace(",", " ").replace(".", " ").split():
        if len(w) >= 4 and w.lower() not in {"inc", "llc", "corp", "company", "group", "the"}:
            toks.add(w.lower())
    return toks


def main() -> int:
    import psycopg
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-domain", type=int, default=1, help="exemplars to approve per demo domain")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    kw = _ar._conn_kwargs()[0]
    with psycopg.connect(**kw) as conn:
        conn.autocommit = False
        approved_by_domain: dict[str, int] = {}
        with conn.cursor() as cur:
            for domain in DEMO_DOMAINS:
                # Strong candidates: clear, specific, low-ambiguity, sensible length.
                # Prefer fresh (open_web) notices; COALESCE category_v2→category.
                cur.execute(
                    """
                    SELECT dc.clause_id, dc.normalized_text, dc.raw_text, o.name,
                           COALESCE(dc.transparency_score,0)+COALESCE(dc.specificity_score,0)
                             - COALESCE(dc.ambiguity_score,0) AS quality
                    FROM disclosure_clause dc
                    JOIN notice_section ns ON ns.section_id = dc.section_id
                    JOIN privacy_notice pn ON pn.notice_id = ns.notice_id
                    JOIN organization o ON o.organization_id = pn.organization_id
                    WHERE COALESCE(dc.category_v2, dc.category) = %s
                      AND COALESCE(dc.is_exemplar, false) = false
                      AND length(COALESCE(dc.normalized_text, dc.raw_text)) BETWEEN 120 AND 600
                    ORDER BY (pn.notice_type = 'open_web') DESC, quality DESC NULLS LAST
                    LIMIT 200
                    """, (domain,))
                picked = 0
                for clause_id, norm, raw, org_name, _q in cur.fetchall():
                    if picked >= args.per_domain:
                        break
                    text = (norm or raw or "").strip()
                    blocked = _org_tokens(org_name)
                    # must pass de-id with the org's own name blocked, AND the approval gate
                    if validate_deidentification(text, extra_blocked_tokens=blocked):
                        continue
                    if validate_exemplar_for_approval(text, f"Strong {domain} exemplar (ai_reviewed).") is not None:
                        continue
                    log.info("[%s] approve clause %s (org=%s): %s", domain, clause_id, org_name, text[:70])
                    if not args.dry_run:
                        cur.execute(
                            "UPDATE disclosure_clause SET is_exemplar=true, exemplar_status='approved' "
                            "WHERE clause_id=%s", (clause_id,))
                    picked += 1
                approved_by_domain[domain] = picked
                if picked == 0:
                    log.warning("[%s] no de-id-passing candidate found — 0 approved", domain)
            if not args.dry_run:
                conn.commit()
        print("\n=== exemplar approval (ai_reviewed) ===")
        for d in DEMO_DOMAINS:
            print(f"  {d:<22} approved: {approved_by_domain.get(d,0)}")
        covered = sum(1 for d in DEMO_DOMAINS if approved_by_domain.get(d, 0) > 0)
        print(f"domains covered: {covered}/{len(DEMO_DOMAINS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
