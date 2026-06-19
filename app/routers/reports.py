"""Report endpoints — assemble and render intelligence reports."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.services.report.assembly import assemble_report
from app.services.report.renderer import render_html, render_pdf_weasyprint

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
    # For MVP, return a sample assembled report
    # In production, this would load from stored data
    report = _assemble_from_stored(assessment_id)
    return asdict(report)


@router.get("/{assessment_id}/pdf")
async def get_report_pdf(
    assessment_id: str,
    renderer: str = Query("weasyprint", enum=["weasyprint", "playwright"]),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Render the report as PDF. Same data as the portal view."""
    report = _assemble_from_stored(assessment_id)

    if renderer == "playwright":
        from app.services.report.renderer import render_pdf_playwright
        pdf_bytes = await render_pdf_playwright(report)
    else:
        pdf_bytes = render_pdf_weasyprint(report)

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
        enforcement_heatmap=[],
        cohort_size=30,
        cohort_date="2026-06-19",
        snapshot_id=assessment_id,
    )
