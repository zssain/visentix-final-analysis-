"""Scoring service — computes formula-driven scores.

Responsibilities (Phase 4):
- Load formula_version definitions (weights, thresholds)
- Compute F-001 through F-014 scores from clause/obligation/enforcement data
- Write results to derived_data_item and risk_finding with full lineage
- Every score stores: formula_version_id, input refs, confidence, generated_at
"""


async def compute_scores(organization_id: str, notice_id: str) -> dict:
    """Compute all formula scores for a notice. Implemented in Phase 4."""
    raise NotImplementedError("Scoring engine not yet implemented")
