"""Re-score all 26 notices — compute missing F-008, F-009, F-010, F-011.

The original scoring pipeline only persisted F-002 through F-007. This script
reads those scores and computes the compound/overall/percentile formulas that
were added later.

Idempotent: checks for existing overall_intelligence rows and skips.

Usage:
    PYTHONPATH=. python scripts/rescore_all.py
    PYTHONPATH=. python scripts/rescore_all.py --dry-run
"""

import argparse
import json
import logging
from collections import defaultdict
from uuid import uuid4

import httpx
from dotenv import dotenv_values

from app.services.scoring.formulas_advanced import (
    compute_f008,
    compute_f009,
    compute_f010,
    compute_f011,
    compute_f012,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rescore")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

SCORE_TYPE_MAP = {
    "regulatory_exposure": "f002",
    "benchmark_deviation": "f003",
    "enforcement_correlation": "f004",
    "disclosure_maturity": "f005",
    "transparency": "f006",
    "ai_transparency": "f007",
    "compound_risk": "f008",
    "confidence_weighted": "f009",
    "overall_intelligence": "f010",
    "benchmark_percentile": "f011",
}

REVERSE_MAP = {v: k for k, v in SCORE_TYPE_MAP.items()}

F010_WEIGHTS = {
    "regulatory": 0.25, "benchmark": 0.20, "disclosure": 0.20,
    "enforcement": 0.10, "ai": 0.15, "compound": 0.10,
}


def fetch_all(path):
    rows, offset = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{path}&offset={offset}&limit=1000", headers=H, timeout=30)
        batch = r.json() if r.status_code == 200 else []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load all notices
    notices = fetch_all("privacy_notice?select=notice_id,organization_id")
    log.info("Notices: %d", len(notices))

    # Load all derived_data_item
    derived = fetch_all("derived_data_item?select=derived_data_item_id,notice_id,object_type,score,value,value_label,confidence_score,formula_version_id,source_lineage,benchmark_population_id")
    log.info("Derived items: %d", len(derived))

    # Group by notice_id
    by_notice = defaultdict(list)
    for d in derived:
        if d.get("notice_id"):
            by_notice[d["notice_id"]].append(d)

    # Load benchmark memberships for percentile
    members = fetch_all("benchmark_membership?select=organization_id,normalization_score,benchmark_weight")
    # Load org profiles for pgms
    profiles = fetch_all("organization_intelligence_profile?select=organization_id,pgms")
    pgms_map = {p["organization_id"]: p.get("pgms", 50) for p in profiles}

    # Build peer scores from profiles
    peer_scores = [{"score": p.get("pgms", 50), "weight": 1.0} for p in profiles]

    total_inserted = 0
    total_skipped = 0

    for notice in notices:
        nid = notice["notice_id"]
        oid = notice["organization_id"]
        items = by_notice.get(nid, [])

        # Extract existing scores
        scores = {}
        seen_types = set()
        for d in items:
            otype = d.get("object_type", "")
            fkey = SCORE_TYPE_MAP.get(otype)
            if fkey and fkey not in seen_types:
                scores[fkey] = d.get("score") or 0
                seen_types.add(fkey)

        # Skip if already has F-010
        if "f010" in scores:
            log.info("Notice %s: already has F-010 (score=%.2f), skipping", nid[:12], scores["f010"])
            total_skipped += 1
            continue

        # Need at least F-002 and F-005 to compute
        if "f002" not in scores and "f005" not in scores:
            log.warning("Notice %s: no base scores found, skipping", nid[:12])
            total_skipped += 1
            continue

        f002 = scores.get("f002", 0)
        f003 = scores.get("f003", 0)
        f004 = scores.get("f004", 50)  # neutral prior
        f005 = scores.get("f005", 0)
        f006 = scores.get("f006", 0)
        f007 = scores.get("f007", 0)

        # F-008: Compound Risk
        risk_scores = {
            "regulatory": f002,
            "benchmark": f003,
            "disclosure": max(0, 100 - f005),
            "ai": max(0, 100 - f007),
        }
        # Use empty RPW — we don't have regulator context here
        f008_result = compute_f008(risk_scores, {})
        f008 = f008_result.score

        # F-010: Overall Intelligence
        component_map = {
            "regulatory": f002,
            "benchmark": f003,
            "disclosure": max(0, 100 - f005),
            "enforcement": f004,
            "ai": max(0, 100 - f007),
            "compound": f008,
        }
        f010_result = compute_f010(component_map, F010_WEIGHTS)
        f010 = f010_result.score

        # F-009: Confidence Weighted
        # Use a reasonable VCI estimate
        vci_score = 0.5
        existing_conf = next((d.get("confidence_score") for d in items if d.get("confidence_score")), 0.5)
        if existing_conf:
            vci_score = existing_conf
        f009_result = compute_f009(f010, vci_score)
        f009 = f009_result.score

        # F-011: Benchmark Percentile
        org_pgms = pgms_map.get(oid, 50)
        f011_result = compute_f011(org_pgms, peer_scores, len(peer_scores) + 1)
        f011 = f011_result.score

        log.info(
            "Notice %s: f002=%.1f f005=%.1f f007=%.1f → f008=%.1f f010=%.1f f011=%.1f",
            nid[:12], f002, f005, f007, f008, f010, f011,
        )

        if args.dry_run:
            continue

        # Get pop_key and confidence from existing rows
        sample = items[0] if items else {}
        pop_key = sample.get("benchmark_population_id", "cohort-v1")
        conf_score = sample.get("confidence_score", 0.5)

        # Build new derived_data_item rows
        new_rows = []
        for fkey, score, result_obj in [
            ("f008", f008, f008_result),
            ("f009", f009, f009_result),
            ("f010", f010, f010_result),
            ("f011", f011, f011_result),
        ]:
            obj_type = REVERSE_MAP[fkey]
            formula_vid = f"F-{fkey[1:]}_v1".upper().replace("F-0", "F-00")
            # Fix formula version id format
            num = fkey[1:]
            formula_vid = f"F-{num.lstrip('0') or '0'}_v1"
            if len(num) == 3:
                formula_vid = f"F-{num}_v1"
            else:
                formula_vid = f"F-0{num[-2:]}_v1" if len(num) == 2 else f"F-{num}_v1"

            item_code = f"{formula_vid}|{nid[:8]}"
            new_rows.append({
                "derived_data_item_id": str(uuid4()),
                "item_code": item_code,
                "object_type": obj_type,
                "organization_id": oid,
                "notice_id": nid,
                "score": score,
                "value": score,
                "value_label": "",
                "confidence_score": conf_score,
                "confidence_index": conf_score,
                "confidence_components": json.dumps({}),
                "formula_version_id": formula_vid,
                "source_lineage": json.dumps(result_obj.source_lineage if hasattr(result_obj, 'source_lineage') else {}),
                "benchmark_population_id": pop_key,
            })

        r = httpx.post(
            f"{URL}/rest/v1/derived_data_item",
            headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=new_rows,
            timeout=15,
        )
        if r.status_code < 300:
            total_inserted += len(new_rows)
        else:
            log.error("Insert failed for %s: %d %s", nid[:12], r.status_code, r.text[:200])

    log.info("=== Done: %d rows inserted, %d skipped ===", total_inserted, total_skipped)


if __name__ == "__main__":
    main()
