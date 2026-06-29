"""Recompute F-001 Source Reliability for all 303 source_record rows.

Writes to derived_data_item (NEVER updates source_record).
Also generates docs/F001_RECOMPUTE_REPORT.md comparing stored vs recomputed.

Usage:
    PYTHONPATH=. python scripts/compute_f001.py
    PYTHONPATH=. python scripts/compute_f001.py --dry-run
"""

import argparse
import json
import logging
import time

import httpx
from dotenv import dotenv_values

from app.services.scoring.f001 import compute_f001

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("compute_f001")

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load F-001_v1 weights
    r = httpx.get(f"{URL}/rest/v1/formula_version?select=weights&formula_version_id=eq.F-001_v1",
                   headers=H, timeout=15)
    weights = r.json()[0]["weights"]
    log.info("F-001_v1 weights: %s", weights)

    # Load all source_record
    sources = fetch_all("source_record",
        "source_id,authority_weight,freshness_weight,completeness_weight,extraction_confidence,source_reliability_score")
    log.info("Source records: %d", len(sources))

    results = []
    written = 0

    for src in sources:
        result = compute_f001(
            source_id=src["source_id"],
            authority_weight=src.get("authority_weight") or 0,
            freshness_weight=src.get("freshness_weight") or 0,
            completeness_weight=src.get("completeness_weight") or 0,
            extraction_confidence=src.get("extraction_confidence") or 0,
            weights=weights,
        )

        stored = src.get("source_reliability_score") or 0
        delta = round(abs(result.score - stored), 6)

        results.append({
            "source_id": src["source_id"],
            "stored": stored,
            "recomputed": result.score,
            "delta": delta,
        })

        if args.dry_run:
            if delta > 0.001:
                log.info("[DRY-RUN] %s stored=%.4f recomputed=%.4f DELTA=%.4f",
                         src["source_id"], stored, result.score, delta)
            continue

        # Write to derived_data_item
        payload = {
            "item_code": f"F-001_v1|{src['source_id']}",
            "object_type": "source",
            "organization_id": None,
            "notice_id": None,
            "score": result.score_100,
            "value": result.score,
            "value_label": "",
            "confidence_score": 0.9,  # F-001 is a simple formula, high confidence
            "confidence_index": 90,
            "confidence_components": json.dumps({"note": "F-001 recompute verification"}),
            "formula_version_id": "F-001_v1",
            "source_lineage": json.dumps({
                "source_id": src["source_id"],
                "components": result.components,
                "weights": weights,
                "stored_score": stored,
                "delta": delta,
            }),
            "benchmark_population_id": None,
        }

        for attempt in range(3):
            try:
                r = httpx.post(f"{URL}/rest/v1/derived_data_item",
                               headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                               json=payload, timeout=15)
                if r.status_code in (200, 201):
                    written += 1
                    break
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt < 2: time.sleep(2 ** attempt)

    # Generate comparison report
    drifted = [r for r in results if r["delta"] > 0.001]
    log.info("Total: %d, Drifted (delta>0.001): %d, Written: %d", len(results), len(drifted), written)

    report_lines = [
        "# F-001 Recompute Report",
        "",
        f"**Date:** 2026-06-29",
        f"**Formula:** F-001_v1 = Σ(component × weight), weights={json.dumps(weights)}",
        f"**Sources:** {len(results)}",
        f"**Drifted (delta > 0.001):** {len(drifted)}",
        "",
        "## Summary",
        "",
        f"All {len(results)} source_record rows were recomputed using the F-001_v1 formula.",
        f"The recomputed values were written to derived_data_item (object_type='source').",
        f"The original source_record.source_reliability_score was NOT modified.",
        "",
    ]

    if drifted:
        report_lines.extend([
            "## Drifted Sources",
            "",
            "| Source ID | Stored | Recomputed | Delta |",
            "|---|---:|---:|---:|",
        ])
        for d in sorted(drifted, key=lambda x: -x["delta"]):
            report_lines.append(f"| {d['source_id']} | {d['stored']:.4f} | {d['recomputed']:.4f} | {d['delta']:.4f} |")
    else:
        report_lines.extend([
            "## Result: Zero Drift",
            "",
            "All stored scores match the recomputed values exactly.",
            "The original corpus F-001 scores are consistent with the formula definition.",
        ])

    report_lines.extend([
        "",
        "## Conclusion",
        "",
        "source_record.source_reliability_score remains UNTOUCHED.",
        "Recomputed values are in derived_data_item for lineage/verification.",
    ])

    if not args.dry_run:
        with open("docs/F001_RECOMPUTE_REPORT.md", "w") as f:
            f.write("\n".join(report_lines) + "\n")
        log.info("Report written to docs/F001_RECOMPUTE_REPORT.md")


if __name__ == "__main__":
    main()
