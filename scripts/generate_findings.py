"""Generate risk findings, junction rows, and report snapshots for all notices.

Usage:
    PYTHONPATH=. python scripts/generate_findings.py
    PYTHONPATH=. python scripts/generate_findings.py --dry-run
"""

import argparse
import json
import logging
import time
from collections import Counter, defaultdict
from uuid import uuid4

import httpx
from dotenv import dotenv_values

from app.services.scoring.findings import FindingInput, select_findings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("generate_findings")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def fetch_all(table, select, limit=1000):
    rows, offset = [], 0
    while True:
        r = httpx.get(f"{URL}/rest/v1/{table}?select={select}&offset={offset}&limit={limit}",
                       headers=H, timeout=30)
        rows.extend(r.json())
        if len(r.json()) < limit: break
        offset += limit
    return rows


def post_with_retry(table, payload, retries=3):
    for attempt in range(retries):
        try:
            r = httpx.post(f"{URL}/rest/v1/{table}",
                           headers={**H, "Content-Type": "application/json", "Prefer": "return=representation"},
                           json=payload, timeout=30)
            if r.status_code in (200, 201):
                return r.json()
            if r.status_code >= 400:
                log.error("POST %s failed: %s", table, r.text[:200])
                return None
        except (httpx.ReadTimeout, httpx.RemoteProtocolError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                log.error("POST %s timed out after %d retries", table, retries)
                return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load data
    log.info("Loading data...")
    orgs = {o["organization_id"]: o for o in fetch_all("organization", "organization_id,name,industry")}
    notices = fetch_all("privacy_notice", "notice_id,organization_id")
    sections = fetch_all("notice_section", "section_id,notice_id")
    clauses = fetch_all("disclosure_clause", "clause_id,section_id,category,ambiguity_score")
    finding_types = {ft["code"]: ft for ft in fetch_all("finding_type", "code,title,default_severity,domain")}
    recs = {rl["finding_type_code"]: rl["id"] for rl in fetch_all("recommendation_library", "id,finding_type_code")}
    enforcements = fetch_all("enforcement_record", "enforcement_id,issue_tags,jurisdiction")

    # Load formula versions for snapshot
    fv_rows = fetch_all("formula_version", "formula_version_id,formula_id,name")
    formula_set = {fv["formula_version_id"]: fv["name"] for fv in fv_rows}

    # Build mappings
    notice_org = {n["notice_id"]: n["organization_id"] for n in notices}
    section_notice = {s["section_id"]: s["notice_id"] for s in sections}

    # Group clauses by notice
    notice_clauses = defaultdict(list)
    for c in clauses:
        nid = section_notice.get(c["section_id"])
        if nid:
            notice_clauses[nid].append(c)

    total_findings = 0
    total_snapshots = 0

    for notice in notices:
        nid = notice["notice_id"]
        oid = notice["organization_id"]
        org = orgs.get(oid, {})
        cls = notice_clauses.get(nid, [])

        if not cls:
            continue

        # Build finding input
        cats = Counter(c["category"] for c in cls)
        clause_ids_by_domain = defaultdict(list)
        amb_by_domain = defaultdict(list)
        for c in cls:
            clause_ids_by_domain[c["category"]].append(c["clause_id"])
            amb_by_domain[c["category"]].append(c.get("ambiguity_score") or 0)

        avg_amb = {d: sum(v)/len(v) for d, v in amb_by_domain.items()}

        # Domain scores: proxy from clause count (higher count = higher maturity)
        # Real maturity comes from F-005 but we approximate per-domain here
        domain_scores = {}
        for domain in cats:
            if domain == "other":
                continue
            count = cats[domain]
            # More clauses in a domain → higher disclosure maturity for that domain
            domain_scores[domain] = min(count * 15, 100)  # 7+ clauses → 100

        # Enforcement matches (by jurisdiction)
        enf_matches = [
            {"enforcement_id": e["enforcement_id"], "issue_tags": e.get("issue_tags") or []}
            for e in enforcements[:20]
        ]

        inp = FindingInput(
            organization_id=oid,
            notice_id=nid,
            clause_categories=cats,
            clause_ids_by_domain=dict(clause_ids_by_domain),
            domain_scores=domain_scores,
            avg_ambiguity_by_domain=avg_amb,
            enforcement_matches=enf_matches,
            vci_score=55.0,  # representative VCI
            formula_version_id="F-002_v1",
            finding_types=finding_types,
            recommendations=recs,
        )

        findings = select_findings(inp)

        if args.dry_run:
            log.info("[DRY-RUN] %s (%s): %d findings → %s",
                     org.get("name", "?"), nid[:8],
                     len(findings),
                     [f.finding_type_code for f in findings])
            total_findings += len(findings)
            continue

        # Create report_snapshot
        snapshot_id = str(uuid4())
        snap_payload = {
            "snapshot_id": snapshot_id,
            "organization_id": oid,
            "notice_id": nid,
            "payload": json.dumps({
                "findings_count": len(findings),
                "finding_codes": [f.finding_type_code for f in findings],
                "clause_count": len(cls),
                "domains": sorted(cats.keys()),
            }),
            "formula_version_set": json.dumps(formula_set),
            "benchmark_population_version": 1,
            "source_corpus_version": 1,
        }
        snap_result = post_with_retry("report_snapshot", snap_payload)
        if snap_result:
            total_snapshots += 1

        # Insert findings + junctions
        for f in findings:
            finding_payload = {
                "organization_id": oid,
                "notice_id": nid,
                "finding_type_code": f.finding_type_code,
                "severity": f.severity,
                "score": f.score,
                "confidence_score": f.confidence_score,
                "formula_version_id": f.formula_version_id,
                "snapshot_id": snapshot_id,
                "domain": f.domain,
            }
            result = post_with_retry("risk_finding", finding_payload)
            if not result:
                continue

            finding_id = result[0]["finding_id"] if isinstance(result, list) else result.get("finding_id")
            if not finding_id:
                continue

            total_findings += 1

            # finding_clause junctions
            for cid in f.triggering_clause_ids[:10]:
                post_with_retry("finding_clause", {"finding_id": finding_id, "clause_id": cid})

            # finding_enforcement junctions
            for eid in f.enforcement_ids[:5]:
                post_with_retry("finding_enforcement", {
                    "finding_id": finding_id,
                    "enforcement_id": eid,
                    "similarity": 0.5,
                })

        log.info("%s: %d findings, snapshot=%s",
                 org.get("name", "?"), len(findings), snapshot_id[:12])

    log.info("=== Done: %d findings, %d snapshots ===", total_findings, total_snapshots)


if __name__ == "__main__":
    main()
