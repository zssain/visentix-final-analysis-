"""Bounded local unblock (F05/F18 prereq): embed the demo-COHORT clauses so the
obligation matcher can produce real clause_obligation rows for retail/healthcare/
fintech. Same model + version string as the RunPod plan (all-MiniLM-L6-v2);
device is MPS locally — recorded here as provenance (vectors are cosine-stable
but not bit-identical to CUDA; see decision-log). Retail first (pilot).
"""

from __future__ import annotations

import logging

import psycopg

import scripts.db.apply_and_record as _mig
from app.services.embeddings import (
    EMBEDDING_MODEL_NAME, _select_device, embed_texts, write_clause_embeddings,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("embed_demo_cohorts")

COHORTS = ["retail", "healthcare", "fintech"]   # retail mandatory first

_UNEMBEDDED_SQL = """
SELECT dc.clause_id::text, dc.normalized_text
FROM benchmark_membership bm
JOIN organization o ON o.organization_id = bm.organization_id
JOIN privacy_notice pn ON pn.organization_id = o.organization_id
JOIN notice_section ns ON ns.notice_id = pn.notice_id
JOIN disclosure_clause dc ON dc.section_id = ns.section_id
WHERE o.industry = %s AND dc.is_noise = false
  AND dc.embedding IS NULL AND dc.normalized_text IS NOT NULL
"""


def _fetch(cohort: str) -> list[dict]:
    kw, _ = _mig._conn_kwargs()
    with psycopg.connect(**kw) as c, c.cursor() as cur:
        cur.execute(_UNEMBEDDED_SQL, (cohort,))
        return [{"clause_id": r[0], "normalized_text": r[1]} for r in cur.fetchall()
                if (r[1] or "").strip()]


def run() -> None:
    device = _select_device()
    log.info("DEVICE=%s MODEL=%s (version string identical to RunPod plan; device is provenance-only)",
             device, EMBEDDING_MODEL_NAME)
    total = 0
    for cohort in COHORTS:
        rows = _fetch(cohort)
        log.info("[%s] unembedded substantive clauses: %d", cohort, len(rows))
        embedded = 0
        for i in range(0, len(rows), 256):
            batch = rows[i:i + 256]
            vecs = embed_texts([r["normalized_text"] for r in batch])
            embedded += write_clause_embeddings(
                [{"clause_id": r["clause_id"], "embedding": v} for r, v in zip(batch, vecs)])
        total += embedded
        log.info("[%s] embedded +%d (device=%s)", cohort, embedded, device)
    log.info("DONE: embedded %d demo-cohort clauses on device=%s", total, device)


if __name__ == "__main__":
    run()
