"""F-001 Source Reliability Score — recompute for verification/lineage.

Definition (from formula_version F-001_v1):
    Source Reliability = Σ(component × weight)
    Weights: authority=0.25, freshness=0.25, completeness=0.25, extraction_confidence=0.25

Reads weights from formula_version — NEVER hardcoded.
Writes to derived_data_item — NEVER updates source_record.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class F001Result:
    source_id: str
    score: float  # 0–1 (matches source_record convention)
    score_100: float  # 0–100 (for derived_data_item)
    components: dict[str, float] = field(default_factory=dict)
    formula_version_id: str = "F-001_v1"


def compute_f001(
    source_id: str,
    authority_weight: float,
    freshness_weight: float,
    completeness_weight: float,
    extraction_confidence: float,
    weights: dict[str, float] | None = None,
) -> F001Result:
    """Compute F-001 Source Reliability Score.

    weights: from formula_version F-001_v1 (e.g. {authority: 0.25, ...}).
             If None, defaults to equal weighting (matching the stored definition).

    Returns score on 0–1 scale (matching source_record convention) and 0–100 scale.
    """
    if weights is None:
        # Equal weighting as fallback — but callers SHOULD pass from DB
        weights = {
            "authority": 0.25,
            "freshness": 0.25,
            "completeness": 0.25,
            "extraction_confidence": 0.25,
        }

    components = {
        "authority": authority_weight,
        "freshness": freshness_weight,
        "completeness": completeness_weight,
        "extraction_confidence": extraction_confidence,
    }

    score = sum(
        components[k] * weights.get(k, 0.25)
        for k in components
    )

    # Clamp 0–1
    score = round(min(max(score, 0.0), 1.0), 6)

    return F001Result(
        source_id=source_id,
        score=score,
        score_100=round(score * 100, 2),
        components=components,
        formula_version_id="F-001_v1",
    )
