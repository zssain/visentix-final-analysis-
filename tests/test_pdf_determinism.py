"""PDF byte-determinism — the report PDF for a FROZEN snapshot must be
byte-for-byte reproducible so a delivered artifact is verifiable by its file hash.

This tests the ACTUAL promise (raw PDF file bytes), not HTML-string equality —
the gap found on 2026-07-29: the old suite asserted `render_html == render_html`
(HTML determinism) and the reputation of "byte-identical double pull" rode on
that, but no test ever rendered a PDF twice and compared sha256. It also guards
against a future WeasyPrint version re-introducing a non-deterministic
/CreationDate, /ModDate or /ID (WeasyPrint 69 emits none — determinism by
absence; if an upgrade adds a live timestamp, this test fails loudly).

NOTE on the live double-pull that differed: that was an UNFROZEN report, which is
assembled live (`_assemble_from_live` → `date.today()` + live recompute) and is
NOT expected to be byte-stable. The guarantee is for the stored/frozen snapshot,
which is what this test renders (a fixed ReportPayload with no now()/today()).
"""
import hashlib

from app.services.report.assembly import ReportPayload, ReportSection
from app.services.report.renderer import render_pdf_weasyprint

# A FIXED snapshot payload — every value is literal (no now()/today()), standing
# in for a frozen report_snapshot.rendered_report.
FROZEN_REPORT = ReportPayload(
    assessment_id="00000000-0000-0000-0000-0000000000aa",
    organization_name="Determinism Fixture Co.",
    generated_date="2026-07-29",
    cohort_size=93,
    cohort_date="2026-07-29",
    vci_label="Moderate",
    sections=[
        ReportSection(number=1, title="Executive Summary",
                      content={"text": "Exposure is moderate across the assessed domains."}),
        ReportSection(number=2, title="Scores",
                      content={"overall_intelligence": 46.79, "transparency": 45.07,
                               "ai_transparency": 15.36, "disclosure_maturity": 49.7,
                               "vci_score": 71.5, "date": "2026-07-29"}),
        ReportSection(number=3, title="Findings",
                      content={"findings": [
                          {"domain": "retention", "severity": "medium", "code": "RT-003"},
                          {"domain": "ai_automated_decisions", "severity": "high", "code": "AI-004"},
                      ]}),
    ],
)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_frozen_snapshot_pdf_is_byte_identical():
    """Render the SAME snapshot twice → identical file bytes (sha256)."""
    a = render_pdf_weasyprint(FROZEN_REPORT)
    b = render_pdf_weasyprint(FROZEN_REPORT)
    assert a, "renderer produced empty PDF"
    assert _sha(a) == _sha(b), (
        "FROZEN-snapshot PDF is NOT byte-identical across renders — a delivered "
        "report can no longer be verified by its file hash. Likely a "
        "non-deterministic field entered the render path (a timestamp/uuid) or "
        "WeasyPrint began stamping /CreationDate|/ID."
    )


def test_pdf_carries_no_nondeterministic_metadata():
    """Guard: no /CreationDate, /ModDate, or /ID (these would break byte-identity)."""
    pdf = render_pdf_weasyprint(FROZEN_REPORT)
    for tag in (b"/CreationDate", b"/ModDate", b"/ID"):
        assert tag not in pdf, (
            f"PDF contains {tag.decode()} — a live timestamp/uuid that breaks "
            "byte-identity. Pin it (metadata override / post-process) or strip it."
        )
