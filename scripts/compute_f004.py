"""Compute F-004 Enforcement Correlation Score for all 26 corpus notices.

Writes NEW derived_data_item rows — never overwrites existing ones.

Usage:
    PYTHONPATH=. python scripts/compute_f004.py
    PYTHONPATH=. python scripts/compute_f004.py --dry-run
"""

import argparse
import json
import logging
import time
from collections import defaultdict

import httpx
from dotenv import dotenv_values

from app.services.scoring.formulas import EnforcementMatch, compute_f004
from app.services.scoring.similarity import top_k_enforcement_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("compute_f004")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

SIMILARITY_FLOOR = 0.30
TOP_K = 5


def fetch_all(table, select, limit=1000):
    rows, offset = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{table}?select={select}&offset={offset}&limit={limit}",
                       headers=H, timeout=30)
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load formula_version F-004_v1
    r = httpx.get(f"{URL}/rest/v1/formula_version?select=*&formula_version_id=eq.F-004_v1",
                   headers=H, timeout=15)
    fv = r.json()[0]
    thresholds = fv.get("thresholds")  # may be None
    log.info("F-004_v1: definition='%s', thresholds=%s", fv["definition"], thresholds)

    # Load notices
    notices = fetch_all("privacy_notice", "notice_id,organization_id")
    log.info("Notices: %d", len(notices))

    # Load section→notice mapping
    sections = fetch_all("notice_section", "section_id,notice_id")
    section_notice = {s["section_id"]: s["notice_id"] for s in sections}

    # Load clauses with embeddings + category
    log.info("Loading clauses with embeddings...")
    clauses = fetch_all("disclosure_clause", "clause_id,section_id,category,embedding")
    log.info("  Total clauses: %d", len(clauses))

    # Group clauses by notice
    notice_clauses = defaultdict(list)
    for c in clauses:
        nid = section_notice.get(c["section_id"])
        if nid and c.get("embedding"):
            notice_clauses[nid].append(c)

    # Load enforcement records with embeddings + regulator
    log.info("Loading enforcement records...")
    enforcements = fetch_all("enforcement_record",
                             "enforcement_id,regulator_id,embedding")
    enf_with_emb = [e for e in enforcements if e.get("embedding")]
    log.info("  Enforcements with embeddings: %d", len(enf_with_emb))

    # Load regulators (RPW + EFW)
    regulators = fetch_all("regulator",
                           "regulator_id,priority_weights,enforcement_frequency_weight")
    reg_map = {r["regulator_id"]: r for r in regulators}

    # Process each notice
    total_written = 0
    for notice in notices:
        nid = notice["notice_id"]
        oid = notice["organization_id"]
        n_clauses = notice_clauses.get(nid, [])

        if not n_clauses:
            continue

        # For each clause, find top-k enforcement matches
        all_matches = []
        for clause in n_clauses:
            emb = clause["embedding"]
            if isinstance(emb, str):
                emb = json.loads(emb)

            top_matches = top_k_enforcement_sync(
                clause_embedding=emb,
                enforcement_rows=enf_with_emb,
                k=TOP_K,
                similarity_floor=SIMILARITY_FLOOR,
            )

            domain = clause.get("category", "other")

            for tm in top_matches:
                reg = reg_map.get(tm["regulator_id"], {})
                rpw_dict = reg.get("priority_weights", {})
                rpw = rpw_dict.get(domain, 0.0) if isinstance(rpw_dict, dict) else 0.0
                efw = reg.get("enforcement_frequency_weight", 0.5)

                all_matches.append(EnforcementMatch(
                    clause_id=clause["clause_id"],
                    enforcement_id=tm["enforcement_id"],
                    regulator_id=tm["regulator_id"],
                    cosine_similarity=tm["cosine_similarity"],
                    rpw=rpw,
                    efw=efw,
                    domain=domain,
                ))

        # Compute F-004
        result = compute_f004(
            matches=all_matches,
            similarity_floor=SIMILARITY_FLOOR,
            thresholds=thresholds,
        )

        if args.dry_run:
            log.info("[DRY-RUN] notice=%s score=%.2f matches=%d",
                     nid[:12], result.score, len(all_matches))
            continue

        # Write to derived_data_item (NEW row, never overwrite)
        payload = {
            "item_code": f"F-004_v1|{nid[:8]}",
            "object_type": result.object_type,
            "organization_id": oid,
            "notice_id": nid,
            "score": result.score,
            "value": result.score,
            "value_label": result.tier or "",
            "confidence_score": result.confidence_score,
            "confidence_index": result.confidence_score * 100,
            "confidence_components": json.dumps({
                "note": "F-004 enforcement correlation confidence. "
                        "TODO: wire into VCI enforcement component (15%).",
            }),
            "formula_version_id": result.formula_version_id,
            "source_lineage": json.dumps(result.source_lineage),
            "benchmark_population_id": "cohort-v1",
        }

        for attempt in range(3):
            try:
                r = httpx.post(f"{URL}/rest/v1/derived_data_item",
                               headers={**H, "Content-Type": "application/json",
                                        "Prefer": "return=minimal"},
                               json=payload, timeout=15)
                if r.status_code in (200, 201):
                    total_written += 1
                    break
                elif r.status_code >= 400:
                    log.error("Insert failed: %s", r.text[:200])
                    break
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt < 2:
                    time.sleep(2 ** attempt)

        log.info("notice=%s score=%.2f matches=%d", nid[:12], result.score, len(all_matches))

    log.info("=== Done: %d F-004 rows written ===", total_written)


if __name__ == "__main__":
    main()
