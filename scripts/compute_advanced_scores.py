"""Compute F-008–F-014 + VCI backfill for all orgs.

Usage:
    PYTHONPATH=. python scripts/compute_advanced_scores.py
    PYTHONPATH=. python scripts/compute_advanced_scores.py --dry-run
"""

import argparse
import json
import logging
from collections import defaultdict

import httpx
from dotenv import dotenv_values

from app.services.scoring.formulas_advanced import (
    compute_f008, compute_f009, compute_f010, compute_f011,
    compute_f012, compute_f013, compute_f014,
)
from app.services.scoring.vci import compute_vci, SUPPRESSION_THRESHOLD

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("advanced_scores")

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


def insert_derived(payload, dry_run=False):
    if dry_run:
        log.info("  [DRY-RUN] %s = %.2f (VCI=%.1f %s)",
                 payload["object_type"], payload["score"],
                 payload.get("confidence_index", 0), payload.get("value_label", ""))
        return
    r = httpx.post(f"{URL}/rest/v1/derived_data_item",
                    headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=payload, timeout=15)
    if r.status_code >= 400:
        log.error("INSERT failed: %s", r.text[:200])
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load existing P4.1 scores
    log.info("Loading existing derived_data_item scores...")
    existing = fetch_all("derived_data_item",
                         "derived_data_item_id,object_type,organization_id,score,confidence_score,confidence_index")

    # Group by org
    org_scores = defaultdict(dict)
    for row in existing:
        oid = row["organization_id"]
        otype = row["object_type"]
        # Take latest (highest score row if duplicates)
        if otype not in org_scores[oid] or row["score"] is not None:
            org_scores[oid][otype] = row

    # Load F-010 weights from DB
    r = httpx.get(f"{URL}/rest/v1/formula_version?select=weights&formula_version_id=eq.F-010_v1",
                   headers=H, timeout=15)
    f010_weights = r.json()[0]["weights"]
    log.info("F-010 weights: %s", f010_weights)

    # Load benchmark data for F-011
    bm = fetch_all("benchmark_membership", "organization_id,benchmark_weight")
    bm_map = {b["organization_id"]: b["benchmark_weight"] or 0.5 for b in bm}

    # Load profiles for F-011 comparison scores
    profiles = fetch_all("organization_intelligence_profile",
                         "organization_id,rss,pgms")
    profile_map = {p["organization_id"]: p for p in profiles}

    # Load source reliability avg
    sources = fetch_all("source_record", "source_reliability_score")
    avg_sr = sum(s.get("source_reliability_score") or 0 for s in sources) / max(len(sources), 1)

    # Load regulators for F-008
    regs = fetch_all("regulator", "regulator_id,priority_weights,enforcement_frequency_weight")
    # Use FTC as representative regulator weights
    ftc = next((r for r in regs if r["regulator_id"] == "FTC"), regs[0])
    ftc_rpw = ftc.get("priority_weights", {})

    orgs = fetch_all("organization", "organization_id,name")
    org_names = {o["organization_id"]: o["name"] for o in orgs}

    total = 0
    for oid in org_scores:
        scores = org_scores[oid]
        name = org_names.get(oid, oid[:12])

        # Extract component scores
        f002_score = (scores.get("regulatory_exposure") or {}).get("score") or 0
        f003_score = (scores.get("benchmark_deviation") or {}).get("score") or 0
        f005_score = (scores.get("disclosure_maturity") or {}).get("score") or 0
        f006_score = (scores.get("transparency") or {}).get("score") or 0
        f007_score = (scores.get("ai_transparency") or {}).get("score") or 0

        # F-008: Compound Risk
        risk_scores = {
            "regulatory": f002_score,
            "benchmark": f003_score,
            "disclosure": max(0, 100 - f005_score),  # invert maturity to risk
            "ai": max(0, 100 - f007_score),
        }
        f008 = compute_f008(risk_scores, ftc_rpw)

        # F-010: Overall Intelligence (uses stored weights)
        component_map = {
            "regulatory": f002_score,
            "benchmark": f003_score,
            "disclosure": max(0, 100 - f005_score),
            "enforcement": 50,  # proxy from EHP
            "ai": max(0, 100 - f007_score),
            "compound": f008.score,
        }
        f010 = compute_f010(component_map, f010_weights)

        # F-011: Benchmark Percentile (weighted)
        prof = profile_map.get(oid, {})
        org_pgms = prof.get("pgms", 0)
        peer_scores = [
            {"score": profile_map.get(pid, {}).get("pgms", 0), "weight": bm_map.get(pid, 0.5)}
            for pid in bm_map if pid != oid
        ]
        f011 = compute_f011(org_pgms, peer_scores, len(peer_scores) + 1)

        # F-009: Confidence-Weighted (using F-010 + VCI)
        # Compute VCI first
        avg_nlp = 0.7 if f005_score > 0 else 0.3
        vci = compute_vci(
            nlp_confidence=avg_nlp,
            benchmark_confidence=0.4 if len(peer_scores) < 50 else 0.7,
            regulatory_confidence=0.7 if f002_score > 0 else 0.3,
            enforcement_confidence=0.5,
            source_reliability=avg_sr,
        )

        f009 = compute_f009(f010.score, vci.score / 100)

        # F-012: Trend Delta (no prior data yet)
        f012 = compute_f012(f010.score, None)

        # F-013: Alert Escalation (no monitoring history yet)
        f013 = compute_f013()

        # F-014: Report Confidence
        total_findings = sum(1 for s in scores.values() if s.get("score", 0) > 0)
        f014 = compute_f014(total_findings, max(total_findings, 1), avg_sr, avg_nlp)

        # Build payloads with real VCI
        results = [
            ("F-008", f008), ("F-009", f009), ("F-010", f010), ("F-011", f011),
            ("F-012", f012), ("F-013", f013), ("F-014", f014),
        ]

        for fid, res in results:
            vci_label = "suppressed" if vci.suppress else vci.label
            payload = {
                "item_code": f"{res.formula_version_id}|{oid[:8]}",
                "object_type": res.object_type,
                "organization_id": oid,
                "score": res.score,
                "value": res.score,
                "value_label": vci_label,
                "confidence_score": vci.score / 100,
                "confidence_index": vci.score,
                "confidence_components": json.dumps({
                    "vci_score": vci.score,
                    "vci_label": vci.label,
                    "vci_guidance": vci.guidance,
                    "suppress": vci.suppress,
                    "components": vci.components,
                }),
                "formula_version_id": res.formula_version_id,
                "source_lineage": json.dumps(res.source_lineage),
                "benchmark_population_id": "cohort-v1",
            }
            insert_derived(payload, dry_run=args.dry_run)
            total += 1

        if not args.dry_run:
            log.info("%s: F-010=%.1f F-011=%.1f%% VCI=%.1f(%s) %s",
                     name, f010.score, f011.score, vci.score, vci.label,
                     "SUPPRESSED" if vci.suppress else "")

    # Backfill VCI onto P4.1 rows
    if not args.dry_run:
        log.info("Backfilling VCI onto P4.1 placeholder rows...")
        backfill_count = 0
        for row in existing:
            if row.get("confidence_index") is None or row["confidence_index"] == 0.5:
                oid = row["organization_id"]
                scores = org_scores.get(oid, {})
                f005_score = (scores.get("disclosure_maturity") or {}).get("score") or 0
                avg_nlp = 0.7 if f005_score > 0 else 0.3

                vci = compute_vci(
                    nlp_confidence=avg_nlp,
                    benchmark_confidence=0.4,
                    regulatory_confidence=0.7 if (scores.get("regulatory_exposure") or {}).get("score", 0) > 0 else 0.3,
                    enforcement_confidence=0.5,
                    source_reliability=avg_sr,
                )

                try:
                    r = httpx.patch(
                        f"{URL}/rest/v1/derived_data_item?derived_data_item_id=eq.{row['derived_data_item_id']}",
                        headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                        json={
                            "confidence_score": vci.score / 100,
                            "confidence_index": vci.score,
                            "confidence_components": json.dumps({
                                "vci_score": vci.score,
                                "vci_label": vci.label,
                                "suppress": vci.suppress,
                                "components": vci.components,
                            }),
                            "value_label": "suppressed" if vci.suppress else vci.label,
                        },
                        timeout=30,
                    )
                    if r.status_code < 300:
                        backfill_count += 1
                except Exception:
                    pass  # retry-safe, skip timeouts

        log.info("VCI backfilled on %d P4.1 rows", backfill_count)

    log.info("=== Done: %d advanced score rows written ===", total)


if __name__ == "__main__":
    main()
