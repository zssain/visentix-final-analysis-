"""Pure helpers for the report's single substantive-clause read path.

The live database currently scopes ``disclosure_clause`` through
``notice_section.section_id`` (``disclosure_clause.notice_id`` is not live).
The router performs that read once and these helpers give every report section
the same domain mapping, noise rule, representative selection, and evidence
shape. No scoring or stored value is recalculated here.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable

from app.services.scoring.heatmap import TAXONOMY_DOMAINS
from app.services.scoring.similarity import SIMILARITY_FLOOR


def canonical_domain(row: dict, domain_id_to_slug: dict[str, str]) -> str:
    """Return a governed report slug, preferring v2/base category over id map."""
    valid = {*TAXONOMY_DOMAINS, "other"}
    for key in ("category_v2", "category"):
        value = row.get(key)
        if value in valid:
            return value
    return domain_id_to_slug.get(str(row.get("domain_id") or ""), "other")


def substantive_rows(rows: list[dict]) -> list[dict]:
    """Match ``pipeline.score_notice``: only ``is_noise is not true`` rows."""
    return [row for row in rows if row.get("is_noise") is not True]


def heatmap_counts(rows: list[dict], domain_id_to_slug: dict[str, str]) -> Counter:
    """Count all substantive clauses; ``other`` remains only in the denominator."""
    counts: Counter = Counter()
    for row in substantive_rows(rows):
        counts[canonical_domain(row, domain_id_to_slug)] += 1
    return counts


def representative_clauses(
    rows: list[dict], domain_id_to_slug: dict[str, str], *, minimum_length: int = 31
) -> dict[str, dict]:
    """Highest-confidence substantive clause per domain, with stable tie-break."""
    selected: dict[str, dict] = {}
    for row in substantive_rows(rows):
        domain = canonical_domain(row, domain_id_to_slug)
        if domain == "other":
            continue
        text = str(row.get("normalized_text") or row.get("raw_text") or "").strip()
        if len(text) < minimum_length:
            continue
        confidence = row.get("nlp_confidence_v2")
        if not isinstance(confidence, (int, float)):
            confidence = row.get("nlp_confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else -1.0
        candidate = {
            "domain": domain,
            "text": text[:1000],
            "clause_id": row.get("clause_id"),
            "section_id": row.get("section_id"),
            "section_title": row.get("section_title"),
            "section_sequence": row.get("section_sequence"),
            "confidence": confidence if confidence >= 0 else None,
            "transparency_score": row.get("transparency_score"),
            "embedding": row.get("embedding"),
        }
        current = selected.get(domain)
        current_key = (
            float(current.get("confidence")) if current and isinstance(current.get("confidence"), (int, float)) else -1.0,
            str(current.get("clause_id") or "") if current else "",
        )
        candidate_key = (confidence, str(candidate.get("clause_id") or ""))
        if current is None or candidate_key > current_key:
            selected[domain] = candidate
    return selected


def _vector(value) -> list[float] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, list) or not value:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def cosine_similarity(left, right) -> float | None:
    """Dependency-free cosine similarity for already-persisted embeddings."""
    a, b = _vector(left), _vector(right)
    if not a or not b or len(a) != len(b):
        return None
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if denom <= 0:
        return None
    return sum(x * y for x, y in zip(a, b)) / denom


def select_comparators(
    org_clauses: dict[str, dict],
    exemplar_rows: list[dict],
    domain_id_to_slug: dict[str, str],
    *,
    similarity_fn: Callable[[object, object], float | None] = cosine_similarity,
    similarity_floor: float = SIMILARITY_FLOOR,
) -> list[dict]:
    """Choose one approved, comparable exemplar for each org-disclosed domain.

    ``SIMILARITY_FLOOR`` is the existing governed F-004 semantic floor. Missing
    embeddings/maturity signals suppress a comparator; they never fall through
    to first-row selection.
    """
    by_domain: dict[str, list[dict]] = {}
    for row in exemplar_rows:
        if row.get("is_exemplar") is not True or row.get("exemplar_status") != "approved":
            continue
        domain = canonical_domain(row, domain_id_to_slug)
        if domain != "other":
            by_domain.setdefault(domain, []).append(row)

    out: list[dict] = []
    for domain in sorted(org_clauses):
        org = org_clauses[domain]
        org_maturity = org.get("transparency_score")
        candidates: list[tuple[float, float, str, dict]] = []
        if isinstance(org_maturity, (int, float)) and org.get("embedding"):
            for row in by_domain.get(domain, []):
                maturity = row.get("transparency_score")
                if not isinstance(maturity, (int, float)) or maturity < org_maturity:
                    continue
                similarity = similarity_fn(org.get("embedding"), row.get("embedding"))
                if similarity is None or similarity < similarity_floor:
                    continue
                candidates.append((
                    float(similarity), float(maturity), str(row.get("clause_id") or ""), row
                ))
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
        if candidates:
            similarity, maturity, _cid, row = candidates[0]
            text = str(row.get("normalized_text") or row.get("raw_text") or "").strip()
            if text:
                out.append({
                    "domain": domain,
                    "clause_text": text,
                    "clause_id": row.get("clause_id"),
                    "similarity": round(similarity, 6),
                    "transparency_score": maturity,
                    "maturity_note": "Approved peer language with comparable semantics and a recorded maturity signal.",
                    "sme_cleaned": True,
                })
    return out
