#!/usr/bin/env python3
"""Read-only exemplar domain integrity report for SME review.

For each approved exemplar, compare its persisted embedding with centroids made
from substantive, non-exemplar clauses. The script reports disagreements but
never writes, retags, approves, or deletes a corpus row.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import get_service_headers
from app.services.report.clause_data import canonical_domain, cosine_similarity


def _domain_map() -> dict[str, str]:
    rows = json.loads((ROOT / "config" / "clause_taxonomy.json").read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for row in rows:
        domain_id, slug = row.get("domain_id"), row.get("legacy_slug")
        if domain_id and slug and slug != "other" and domain_id not in result:
            result[domain_id] = slug
    return result


def _vector(value) -> list[float] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, list) or not value:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def _centroids(rows: list[dict], domain_map: dict[str, str]) -> dict[str, list[float]]:
    vectors: dict[str, list[list[float]]] = defaultdict(list)
    for row in rows:
        if row.get("is_noise") is True or row.get("is_exemplar") is True:
            continue
        vector = _vector(row.get("embedding"))
        domain = canonical_domain(row, domain_map)
        if vector and domain != "other":
            vectors[domain].append(vector)
    out: dict[str, list[float]] = {}
    for domain, items in vectors.items():
        width = len(items[0])
        compatible = [item for item in items if len(item) == width]
        if compatible:
            out[domain] = [sum(item[i] for item in compatible) / len(compatible) for i in range(width)]
    return out


def build_report(exemplars: list[dict], corpus_rows: list[dict]) -> list[dict]:
    domain_map = _domain_map()
    centroids = _centroids(corpus_rows, domain_map)
    report: list[dict] = []
    for row in sorted(exemplars, key=lambda item: str(item.get("clause_id") or "")):
        filed = canonical_domain(row, domain_map)
        vector = _vector(row.get("embedding"))
        scored = [
            (similarity, domain)
            for domain, centroid in centroids.items()
            if (similarity := cosine_similarity(vector, centroid)) is not None
        ] if vector else []
        scored.sort(key=lambda item: (-item[0], item[1]))
        assessed = scored[0][1] if scored else None
        report.append({
            "clause_id": row.get("clause_id"),
            "filed_domain": filed,
            "similarity_assessed_domain": assessed,
            "similarity": round(scored[0][0], 6) if scored else None,
            "disagreement": assessed is not None and assessed != filed,
            "status": "assessed" if assessed else "embedding_or_centroid_not_recorded",
        })
    return report


def main() -> int:
    headers = get_service_headers()
    select = "clause_id,domain_id,category,category_v2,embedding,is_noise,is_exemplar,exemplar_status"
    with httpx.Client(timeout=30) as client:
        exemplar_response = client.get(
            f"{settings.supabase_url}/rest/v1/disclosure_clause",
            headers=headers,
            params={"select": select, "is_exemplar": "eq.true", "exemplar_status": "eq.approved", "limit": "10000"},
        )
        corpus_response = client.get(
            f"{settings.supabase_url}/rest/v1/disclosure_clause",
            headers=headers,
            params={"select": select, "limit": "10000"},
        )
    exemplar_response.raise_for_status()
    corpus_response.raise_for_status()
    print(json.dumps(build_report(exemplar_response.json(), corpus_response.json()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
