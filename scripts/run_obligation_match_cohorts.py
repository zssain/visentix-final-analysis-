"""Cohort-scoped obligation matcher (bounded unblock for F05/F18).

Runs the SAME tested matcher (obligation_match, 0.35 floor, exposure-context
framing UNCHANGED) over the demo COHORT clauses (retail → healthcare → fintech),
now that they are 100% embedded. Populates clause_obligation with similarity +
matched_terms + model_version. Enforces the ≥95% coverage gate per cohort and
RECORDS SCOPE (which cohorts/orgs were covered) to logs/eval/obligation_match_scope.json
so the evidence-stack assembler can treat out-of-scope orgs as honest absence
("obligation context not yet available"), never "no obligations matched".
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import psycopg

import scripts.db.apply_and_record as _mig
from app.services.embeddings import EMBEDDING_MODEL_NAME
from app.services.scoring.obligation_match import SIMILARITY_FLOOR, match_clauses_to_obligations
from scripts.run_obligation_match import load_obligations, matched_terms, upsert

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("match_cohorts")

COHORTS = ["retail", "healthcare", "fintech"]
SCOPE_PATH = Path(__file__).resolve().parents[1] / "logs" / "eval" / "obligation_match_scope.json"

_CLAUSE_SQL = """
SELECT dc.clause_id::text, COALESCE(dc.category_v2, dc.category, 'other') AS category,
       dc.normalized_text, dc.embedding::text, o.organization_id::text
FROM benchmark_membership bm
JOIN organization o ON o.organization_id = bm.organization_id
JOIN privacy_notice pn ON pn.organization_id = o.organization_id
JOIN notice_section ns ON ns.notice_id = pn.notice_id
JOIN disclosure_clause dc ON dc.section_id = ns.section_id
WHERE o.industry = %s AND dc.is_noise = false AND dc.embedding IS NOT NULL
"""


def _coverage(cur, cohort: str) -> float:
    cur.execute("""SELECT count(*) FILTER (WHERE dc.is_noise=false) sub,
                   count(*) FILTER (WHERE dc.is_noise=false AND dc.embedding IS NOT NULL) emb
        FROM benchmark_membership bm JOIN organization o ON o.organization_id=bm.organization_id
        JOIN privacy_notice pn ON pn.organization_id=o.organization_id
        JOIN notice_section ns ON ns.notice_id=pn.notice_id
        JOIN disclosure_clause dc ON dc.section_id=ns.section_id
        WHERE o.industry=%s""", (cohort,))
    sub, emb = cur.fetchone()
    return emb / sub if sub else 0.0


def run(min_coverage: float = 0.95) -> None:
    obligations = load_obligations()
    log.info("loaded %d embedded obligations; floor=%.2f (unchanged)", len(obligations), SIMILARITY_FLOOR)
    ob_by_id = {o["obligation_id"]: o for o in obligations}
    scope = {"generated_at": date(2026, 7, 28).isoformat(), "model_version": EMBEDDING_MODEL_NAME,
             "device": "mps", "floor": SIMILARITY_FLOOR, "cohorts": {}}

    kw, _ = _mig._conn_kwargs()
    for cohort in COHORTS:
        with psycopg.connect(**kw) as c, c.cursor() as cur:
            cov = _coverage(cur, cohort)
            if cov < min_coverage:
                log.error("REFUSING %s: coverage %.1f%% < %.0f%% gate", cohort, cov * 100, min_coverage * 100)
                scope["cohorts"][cohort] = {"status": "skipped_below_gate", "coverage": round(cov, 4)}
                continue
            cur.execute(_CLAUSE_SQL, (cohort,))
            rows = cur.fetchall()
        clauses = [{"clause_id": r[0], "category": r[1], "normalized_text": r[2], "embedding": r[3]}
                   for r in rows]
        orgs = sorted({r[4] for r in rows})
        matches = match_clauses_to_obligations(clauses, obligations, similarity_floor=SIMILARITY_FLOOR)
        text_by_id = {c["clause_id"]: c["normalized_text"] for c in clauses}
        payload = [{
            "clause_id": m.clause_id, "obligation_id": m.obligation_id, "match_method": m.match_method,
            "similarity": m.similarity, "model_version": EMBEDDING_MODEL_NAME,
            "matched_terms": json.dumps(matched_terms(text_by_id.get(m.clause_id, ""),
                                                      ob_by_id.get(m.obligation_id, {}))),
        } for m in matches]
        for i in range(0, len(payload), 500):
            upsert(payload[i:i + 500])
        log.info("[%s] orgs=%d clauses=%d matches=%d written", cohort, len(orgs), len(clauses), len(payload))
        scope["cohorts"][cohort] = {"status": "covered", "coverage": round(cov, 4),
                                    "orgs": len(orgs), "org_ids": orgs, "clauses": len(clauses),
                                    "matches": len(payload)}

    SCOPE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCOPE_PATH.write_text(json.dumps(scope, indent=2))
    log.info("scope recorded → %s", SCOPE_PATH.name)


if __name__ == "__main__":
    run()
