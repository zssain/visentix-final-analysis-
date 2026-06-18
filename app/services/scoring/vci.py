"""Visentix Confidence Index (VCI) — honesty mechanism for derived values.

VCI = NLP 30% + Benchmark 25% + Regulatory 15% + Enforcement 15% + Source 15%.
Maps to labels and suppression rules.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── VCI dimension weights (VICBNF spec) ──────────────────────
VCI_WEIGHTS = {
    "nlp": 0.30,
    "benchmark": 0.25,
    "regulatory": 0.15,
    "enforcement": 0.15,
    "source": 0.15,
}

# ── Label mapping ────────────────────────────────────────────
VCI_LABELS = [
    (80, 100, "very_high", "Suitable for executive presentation"),
    (60, 79, "high", "Suitable for standard reporting"),
    (40, 59, "moderate", "Include with confidence caveat"),
    (20, 39, "low", "Route to review — do not present as definitive"),
    (0, 19, "very_low", "Suppress — insufficient data for meaningful output"),
]

SUPPRESSION_THRESHOLD = 40  # VCI < 40 → do-not-present


@dataclass
class VCIResult:
    """VCI computation result."""

    score: float  # 0-100
    label: str
    guidance: str
    suppress: bool  # True if VCI < 40
    components: dict[str, float]


def compute_vci(
    nlp_confidence: float = 0.5,
    benchmark_confidence: float = 0.5,
    regulatory_confidence: float = 0.5,
    enforcement_confidence: float = 0.5,
    source_reliability: float = 0.5,
) -> VCIResult:
    """Compute VCI from dimension confidences (each 0-1 scale).

    Returns a 0-100 score with label and suppression flag.
    """
    components = {
        "nlp": nlp_confidence,
        "benchmark": benchmark_confidence,
        "regulatory": regulatory_confidence,
        "enforcement": enforcement_confidence,
        "source": source_reliability,
    }

    score = sum(
        VCI_WEIGHTS[dim] * val * 100
        for dim, val in components.items()
    )
    score = round(min(max(score, 0), 100), 2)

    label, guidance = _score_to_label(score)
    suppress = score < SUPPRESSION_THRESHOLD

    return VCIResult(
        score=score,
        label=label,
        guidance=guidance,
        suppress=suppress,
        components=components,
    )


def _score_to_label(score: float) -> tuple[str, str]:
    for lo, hi, label, guidance in VCI_LABELS:
        if lo <= score <= hi:
            return label, guidance
    return "very_low", "Suppress — insufficient data"
