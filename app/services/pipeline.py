"""Pipeline service — orchestrates the full assessment flow.

Responsibilities (Phase 3+):
- Accept a notice URL or uploaded document
- Run extraction → classification → scoring → findings → report
- Coordinate calls to embeddings, scoring, narrative, and guardrail services
"""


async def run_assessment(organization_id: str, notice_id: str) -> dict:
    """Run the full assessment pipeline for a notice. Implemented in Phase 3."""
    raise NotImplementedError("Pipeline not yet implemented")
