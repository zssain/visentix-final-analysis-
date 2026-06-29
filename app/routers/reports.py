"""Report endpoints — assemble and render intelligence reports."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.services.report.assembly import assemble_report
from app.services.report.renderer import render_html, render_pdf_weasyprint
from app.services.review import customer_can_view, get_active_findings

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{assessment_id}")
async def get_report(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return the assembled 12-section report payload for an assessment.

    Built ONLY from stored derived_data_item, risk_finding, snapshots,
    and guardrailed narrative.
    """
    # Gate mode check for customer role
    if user.role == "customer":
        can_view, banner = customer_can_view(assessment_id)
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Report pending expert review (gate_mode=strict).",
            )
    else:
        banner = ""

    report = _assemble_from_stored(assessment_id)
    result = asdict(report)
    if banner:
        result["draft_banner"] = banner
    return result


@router.get("/{assessment_id}/pdf")
async def get_report_pdf(
    assessment_id: str,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Render the report as PDF. Uses env RENDERER setting (weasyprint|playwright)."""
    from app.services.report.renderer import render_pdf
    report = _assemble_from_stored(assessment_id)
    pdf_bytes = await render_pdf(report, renderer=settings.renderer)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{assessment_id[:12]}.pdf"},
    )


def _assemble_from_stored(assessment_id: str):
    """Assemble report from stored data. MVP: uses placeholder data."""
    return assemble_report(
        assessment_id=assessment_id,
        org_name="Assessment Organization",
        scores={
            "f002": {"score": 45.0, "tier": "moderate", "lineage": {}},
            "f003": {"score": 15.0, "lineage": {}},
            "f005": {"score": 78.0, "lineage": {}},
            "f006": {"score": 35.0, "lineage": {}},
            "f007": {"score": 42.0, "lineage": {}},
            "f008": {"score": 28.0, "lineage": {}},
            "f010": {"score": 62.5, "lineage": {}},
            "f011": {"score": 71.0, "lineage": {}},
        },
        findings=[
            {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
            {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 45.0},
        ],
        vci={"score": 58.0, "label": "moderate"},
        narrative_exec=(
            "Assessment Organization presents an overall privacy intelligence score of "
            "62.5 out of 100, placing it at the 71.0th percentile within its peer cohort "
            "(n=30, as of 2026-06-19). The assessment identified 2 areas of elevated "
            "exposure. Confidence level: moderate."
        ),
        narrative_takeaways=[
            "The data sharing domain presents elevated exposure (finding SH-002, score 65.0/100).",
            "The retention domain presents moderate exposure (finding RT-003, score 45.0/100).",
        ],
        narrative_recommendations=[
            {"severity": "high", "code": "SH-002", "title": "Clarify Data Sharing",
             "prose": "Review and enhance data sharing disclosures to address elevated exposure indicators."},
            {"severity": "medium", "code": "RT-003", "title": "Define Retention Periods",
             "prose": "Consider specifying retention periods for each data category to reduce exposure."},
        ],
        exemplars=[],  # No sme_cleaned exemplars yet → placeholder in section 8
        enforcement_heatmap=_build_sample_heatmap(),
        cohort_size=30,
        cohort_date="2026-06-19",
        snapshot_id=assessment_id,
    )


def _build_sample_heatmap() -> list[dict]:
    """Build a real heatmap from sample data for the MVP placeholder report."""
    from collections import Counter
    from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable

    sample_regulators = [
        {"regulator_id": "FTC", "name": "Federal Trade Commission", "jurisdiction": "US-FED",
         "enforcement_frequency_weight": 0.9,
         "priority_weights": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.9,
                              "consumer_rights": 0.6, "children_teens": 0.9, "retention": 0.6,
                              "cross_border": 0.4, "ai_automated_decisions": 0.8}},
        {"regulator_id": "CPPA", "name": "CA Privacy Protection Agency", "jurisdiction": "US-CA",
         "enforcement_frequency_weight": 0.7,
         "priority_weights": {"data_sharing": 0.9, "tracking_cookies": 0.9, "sensitive_data": 0.8,
                              "consumer_rights": 0.9, "children_teens": 0.7, "retention": 0.7,
                              "cross_border": 0.5, "ai_automated_decisions": 0.9}},
    ]
    sample_clauses = Counter({"data_sharing": 10, "tracking_cookies": 5, "retention": 2, "other": 20})
    rows = build_regulator_heatmap(sample_regulators, sample_clauses)
    return heatmap_to_serializable(rows)
