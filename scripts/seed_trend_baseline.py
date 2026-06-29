"""Seed ONE demo trend baseline snapshot for ONE notice.

Creates a PRIOR snapshot with a slightly different overall score so F-012
yields a genuine, traceable non-zero delta in tests. Additive only — never
overwrites an existing snapshot. Clearly labelled as a demo baseline.

Usage:
    PYTHONPATH=. python scripts/seed_trend_baseline.py
    PYTHONPATH=. python scripts/seed_trend_baseline.py --dry-run
"""

import argparse
import json
import logging
from uuid import uuid4

import httpx
from dotenv import dotenv_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_trend_baseline")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Pick the first notice with a snapshot
    r = httpx.get(f"{URL}/rest/v1/report_snapshot?select=snapshot_id,notice_id,organization_id,payload&limit=1",
                   headers=H, timeout=15)
    snapshots = r.json()
    if not snapshots:
        log.error("No existing snapshots to base the demo on.")
        return

    existing = snapshots[0]
    notice_id = existing["notice_id"]
    org_id = existing["organization_id"]
    log.info("Basing demo baseline on notice=%s (existing snapshot=%s)",
             notice_id[:12] if notice_id else "?", existing["snapshot_id"][:12])

    # Create a PRIOR baseline with a slightly lower score (simulating improvement)
    baseline_id = str(uuid4())
    baseline_payload = {
        "snapshot_id": baseline_id,
        "organization_id": org_id,
        "notice_id": notice_id,
        "payload": json.dumps({
            "demo_baseline": True,
            "label": "DEMO TREND BASELINE — created for F-012 demo purposes only. "
                     "Not a real historical assessment.",
            "overall_intelligence_prior": 55.0,  # prior score
            "created_for": "F-012_trend_delta_demo",
        }),
        "formula_version_set": json.dumps({"note": "demo_baseline_v0"}),
        "benchmark_population_version": 0,
        "source_corpus_version": 0,
    }

    # Also write a prior derived_data_item so F-012 can find it
    prior_derived = {
        "item_code": f"F-010_v1|demo-baseline|{notice_id[:8]}",
        "object_type": "overall_intelligence",
        "organization_id": org_id,
        "notice_id": notice_id,
        "score": 55.0,
        "value": 55.0,
        "value_label": "demo_baseline",
        "confidence_score": 0.5,
        "confidence_index": 50,
        "confidence_components": json.dumps({"note": "DEMO BASELINE for F-012 trend"}),
        "formula_version_id": "F-010_v1",
        "source_lineage": json.dumps({
            "demo_baseline": True,
            "label": "Prior data point for trend delta demonstration.",
            "baseline_snapshot_id": baseline_id,
        }),
        "source_snapshot_id": baseline_id,
    }

    if args.dry_run:
        log.info("[DRY-RUN] Would create baseline snapshot: %s", baseline_id[:12])
        log.info("[DRY-RUN] Would create prior derived_data_item: F-010=55.0")
        return

    # Insert snapshot
    r1 = httpx.post(f"{URL}/rest/v1/report_snapshot",
                     headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                     json=baseline_payload, timeout=15)
    log.info("Baseline snapshot: %s (%d)", baseline_id[:12], r1.status_code)

    # Insert prior derived value
    r2 = httpx.post(f"{URL}/rest/v1/derived_data_item",
                     headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                     json=prior_derived, timeout=15)
    log.info("Prior derived_data_item: F-010=55.0 (%d)", r2.status_code)

    log.info("=== Demo baseline seeded. Use notice=%s with prior=55.0 for F-012 demo. ===",
             notice_id[:12] if notice_id else "?")


if __name__ == "__main__":
    main()
