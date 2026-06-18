"""Compute F-002/003/005/006/007 for all orgs and write to derived_data_item.

Usage:
    PYTHONPATH=. python scripts/compute_scores.py
    PYTHONPATH=. python scripts/compute_scores.py --dry-run
"""

import argparse
import json
import logging
from collections import Counter, defaultdict

import httpx
from dotenv import dotenv_values

from app.services.scoring.engine import (
    load_element_checklist,
    load_jurisdiction_weights,
    get_expected_elements,
)
from app.services.scoring.formulas import (
    ScoringContext,
    compute_f002,
    compute_f003,
    compute_f005,
    compute_f006,
    compute_f007,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("compute_scores")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def fetch_all(table, select, limit=1000):
    rows, offset = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{table}?select={select}&offset={offset}&limit={limit}",
                       headers=H, timeout=30)
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit: break
        offset += limit
    return rows


def build_contexts():
    """Build ScoringContext per org from live data."""
    jw = load_jurisdiction_weights()
    checklist = load_element_checklist()

    orgs = fetch_all("organization", "organization_id,name,industry,geography")
    notices = fetch_all("privacy_notice", "notice_id,organization_id")
    sections = fetch_all("notice_section", "section_id,notice_id")
    clauses = fetch_all("disclosure_clause",
                        "clause_id,section_id,category,ambiguity_score,readability_score,nlp_confidence")
    regulators = fetch_all("regulator", "regulator_id,jurisdiction,enforcement_frequency_weight,priority_weights")
    bm = fetch_all("benchmark_membership", "organization_id,normalization_score,benchmark_weight")
    profiles = fetch_all("organization_intelligence_profile",
                         "organization_id,rss,pgms,osi,dsi,ehp,aigms")

    # Build mappings
    notice_org = {n["notice_id"]: n["organization_id"] for n in notices}
    section_notice = {s["section_id"]: s["notice_id"] for s in sections}

    # Org → clause data
    org_clauses = defaultdict(list)
    for c in clauses:
        nid = section_notice.get(c["section_id"])
        oid = notice_org.get(nid) if nid else None
        if oid:
            org_clauses[oid].append(c)

    # Org → notice_id
    org_notices = defaultdict(list)
    for n in notices:
        org_notices[n["organization_id"]].append(n["notice_id"])

    # Regulator list
    reg_list = [
        {
            "id": r["regulator_id"],
            "jurisdiction": r["jurisdiction"],
            "efw": r["enforcement_frequency_weight"],
            "rpw": r["priority_weights"] or {},
        }
        for r in regulators
    ]

    # Benchmark weights
    bm_weights = {b["organization_id"]: b for b in bm}

    # Profile scores for benchmark comparison
    profile_map = {p["organization_id"]: p for p in profiles}

    contexts = []
    for org in orgs:
        oid = org["organization_id"]
        cls = org_clauses.get(oid, [])
        cats = Counter(c["category"] for c in cls)
        domains = set(c["category"] for c in cls if c["category"] != "other")

        avg_amb = sum(c.get("ambiguity_score") or 0 for c in cls) / max(len(cls), 1)
        avg_read = sum(c.get("readability_score") or 0 for c in cls) / max(len(cls), 1)
        avg_conf = sum(c.get("nlp_confidence") or 0 for c in cls) / max(len(cls), 1)

        # Build peer scores for F-003 (using PGMS as the comparison metric)
        org_profile = profile_map.get(oid, {})
        org_pgms = org_profile.get("pgms", 0)

        peer_scores = []
        for pid, pw in bm_weights.items():
            if pid != oid:
                pp = profile_map.get(pid, {})
                peer_scores.append({
                    "org_id": pid,
                    "score": pp.get("pgms", 0),
                    "weight": pw.get("benchmark_weight", 0),
                })

        nids = org_notices.get(oid, [])

        ctx = ScoringContext(
            organization_id=oid,
            notice_id=nids[0] if nids else None,
            industry=org.get("industry", ""),
            jurisdiction=org.get("geography", "US"),
            clause_categories=cats,
            total_clauses=len(cls),
            avg_ambiguity=avg_amb,
            avg_readability=avg_read,
            avg_nlp_confidence=avg_conf,
            domains_present=domains,
            regulators=reg_list,
            jurisdiction_weights=jw,
            peer_scores=peer_scores,
            org_score=org_pgms,
            ai_clauses=cats.get("ai_automated_decisions", 0),
        )
        contexts.append((org, ctx))

    return contexts, checklist


def insert_derived(org_id, notice_id, result, dry_run=False):
    """Insert a derived_data_item row."""
    payload = {
        "item_code": f"{result.formula_version_id}|{org_id[:8]}",
        "object_type": result.object_type,
        "organization_id": org_id,
        "notice_id": notice_id,
        "score": result.score,
        "value": result.score,
        "value_label": result.tier or "",
        "confidence_score": result.confidence_score,
        "confidence_index": result.confidence_score,
        "confidence_components": json.dumps({"note": "placeholder_until_VCI_P4.3"}),
        "formula_version_id": result.formula_version_id,
        "source_lineage": json.dumps(result.source_lineage),
        "benchmark_population_id": "cohort-v1",
    }

    if dry_run:
        log.info("  [DRY-RUN] %s = %.2f (%s)", result.object_type, result.score,
                 result.tier or "—")
        return

    r = httpx.post(
        f"{URL}/rest/v1/derived_data_item",
        headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json=payload, timeout=15,
    )
    if r.status_code >= 400:
        log.error("INSERT failed: %s %s", r.status_code, r.text[:200])
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    contexts, checklist = build_contexts()
    all_elements = get_expected_elements(checklist)
    ai_elements = get_expected_elements(checklist, ai_only=True)

    # Load F-002 thresholds from DB
    r = httpx.get(f"{URL}/rest/v1/formula_version?select=thresholds&formula_version_id=eq.F-002_v1",
                   headers=H, timeout=15)
    f002_thresholds = r.json()[0]["thresholds"]

    total = 0
    for org, ctx in contexts:
        name = org["name"]
        oid = ctx.organization_id
        nid = ctx.notice_id

        results = [
            compute_f002(ctx, f002_thresholds),
            compute_f003(ctx),
            compute_f005(ctx, all_elements),
            compute_f006(ctx),
            compute_f007(ctx, ai_elements),
        ]

        if args.dry_run:
            log.info("%s:", name)

        for res in results:
            insert_derived(oid, nid, res, dry_run=args.dry_run)
            total += 1

        if not args.dry_run:
            scores_str = " | ".join(f"{r.object_type}={r.score:.1f}" for r in results)
            log.info("%s: %s", name, scores_str)

    log.info("=== Done: %d derived_data_item rows written ===", total)


if __name__ == "__main__":
    main()
