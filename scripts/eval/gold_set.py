"""Gold-set sampler (F17 component 1).

Deterministic, stratified 200-clause sample across 8 domains + other × §8
confidence bands × corpus source. Excludes is_noise=true clauses (Prompt-2 noise
filter landed). Freezes membership to logs/eval/gold_set_v1.json and a CSV with
BLANK gold columns for the SME to fill. **Pre-fills NOTHING** — no gold_domain,
no verdict; those come only from a human via CSV import or the labeling endpoint.

Run: PYTHONPATH=. python scripts/eval/gold_set.py [--target 200] [--pool 30000]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import defaultdict

from scripts.eval.common import (
    DOMAINS,
    GOLD_SET_CSV,
    GOLD_SET_PATH,
    GOLD_SET_VERSION,
    SOURCE_GROUPS,
    VCI_BANDS,
    band_of,
    conn,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gold_set")

# md5-ordered pool → deterministic pseudo-random, bounded (full 684k join would time out).
_POOL_SQL = """
SELECT dc.clause_id::text, dc.category_v2, dc.nlp_confidence_v2, dc.raw_text,
       CASE
         WHEN pn.notice_type = 'open_web' THEN 'fresh_2026'
         WHEN pn.intake_method = 'upload' THEN 'upload_rehearsal'
         WHEN o.origin = 'rehearsal' THEN 'upload_rehearsal'
         ELSE 'legacy'
       END AS source_group
FROM disclosure_clause dc
JOIN notice_section ns ON dc.section_id = ns.section_id
JOIN privacy_notice pn ON ns.notice_id = pn.notice_id
LEFT JOIN organization o ON pn.organization_id = o.organization_id
WHERE dc.is_noise = false AND dc.category_v2 IS NOT NULL
ORDER BY md5(dc.clause_id::text)
LIMIT %s
"""


def build(target: int = 200, pool: int = 30000) -> dict:
    with conn() as c, c.cursor() as cur:
        cur.execute(_POOL_SQL, (pool,))
        rows = cur.fetchall()
    log.info("candidate pool (is_noise-excluded, category_v2 present): %d", len(rows))

    # Bucket by stratum = (domain, band, source_group). md5 order is deterministic,
    # so first-seen ordering within a bucket is stable.
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for clause_id, cat, conf, text, src in rows:
        buckets[(cat, band_of(conf), src)].append({
            "clause_id": clause_id, "category_v2": cat,
            "nlp_confidence_v2": conf, "source_group": src,
            "band": band_of(conf), "raw_text": (text or "")[:280],
        })

    strata = [(d, b[0], s) for d in DOMAINS for b in VCI_BANDS for s in SOURCE_GROUPS]
    # Round-robin across strata → even spread; stop at target. Honest per-cell counts.
    selected, cursors = [], {k: 0 for k in strata}
    progressed = True
    while len(selected) < target and progressed:
        progressed = False
        for k in strata:
            if len(selected) >= target:
                break
            i = cursors[k]
            if i < len(buckets.get(k, [])):
                selected.append(buckets[k][i])
                cursors[k] = i + 1
                progressed = True

    per_cell = {f"{d}|{b}|{s}": min(cursors[(d, b, s)], len(buckets.get((d, b, s), [])))
                for (d, b, s) in strata}
    empty_cells = sorted(k for k, v in per_cell.items() if v == 0)

    manifest = {
        "gold_set_version": GOLD_SET_VERSION,
        "target": target, "selected": len(selected),
        "pool_size": len(rows),
        "note": ("Stratified 8 domains × 5 §8 bands × 3 sources; is_noise excluded; "
                 "NO gold labels pre-filled. Under-populated cells reported, not back-filled."),
        "per_cell_counts": per_cell,
        "empty_cells": empty_cells,
        "clauses": [{k: r[k] for k in ("clause_id", "category_v2", "nlp_confidence_v2",
                                       "source_group", "band", "raw_text")} for r in selected],
    }
    return manifest


def freeze(manifest: dict) -> None:
    GOLD_SET_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    with GOLD_SET_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        # BLANK gold columns — the SME fills gold_domain / verdict / note.
        w.writerow(["clause_id", "machine_category_v2", "nlp_confidence_v2",
                    "source_group", "band", "raw_text",
                    "gold_domain(FILL)", "verdict(FILL)", "note(FILL)"])
        for r in manifest["clauses"]:
            w.writerow([r["clause_id"], r["category_v2"], r["nlp_confidence_v2"],
                        r["source_group"], r["band"], r["raw_text"], "", "", ""])
    log.info("froze %d clauses → %s (+ CSV with BLANK gold columns)",
             manifest["selected"], GOLD_SET_PATH.name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=200)
    ap.add_argument("--pool", type=int, default=30000)
    args = ap.parse_args()
    m = build(args.target, args.pool)
    freeze(m)
    log.info("selected=%d/%d | empty strata cells=%d (reported honestly, not back-filled)",
             m["selected"], args.target, len(m["empty_cells"]))


if __name__ == "__main__":
    main()
