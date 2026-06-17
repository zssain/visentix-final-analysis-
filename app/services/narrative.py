"""Narrative service — LLM-powered phrasing over pre-computed data.

Responsibilities (Phase 5):
- Take pre-computed scores, findings, and recommendations
- Use Qwen3 to smooth tone into professional privacy-intelligence language
- The LLM CLASSIFIES and PHRASES only — it never invents claims or numbers
- All output passes through the guardrail service before delivery
"""


async def generate_narrative(
    findings: list[dict],
    recommendations: list[dict],
    scores: dict,
) -> str:
    """Generate report narrative from pre-computed data. Implemented in Phase 5."""
    raise NotImplementedError("Narrative service not yet implemented")
