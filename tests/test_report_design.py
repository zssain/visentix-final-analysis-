"""PHASE 6 — executive report design tests.

These lock the design layer to the product's non-negotiables:
  * determinism survives the restyle (byte-identical PDF, no volatile metadata),
  * honest absence is rendered, never a fabricated 0 / bar / peer average,
  * the phrasing guardrail still fails closed (restyle didn't route around it),
  * partner branding stays header-only (F20 — body bytes identical),
  * no un-substituted `{template}` token can reach a customer.
"""
import hashlib
import re
from collections import Counter

import pytest

from app.services.report.assembly import assemble_report
from app.services.report.renderer import (
    render_html,
    render_pdf_weasyprint,
    _strip_placeholders,
)
from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable


# ── Fixtures ────────────────────────────────────────────────────────────────

_REGULATORS = [
    {"regulator_id": "FTC", "name": "Federal Trade Commission", "jurisdiction": "US Federal",
     "priority_weights": {"data_sharing": 0.9, "ai_automated_decisions": 0.8, "sensitive_data": 0.7},
     "enforcement_frequency_weight": 0.8},
    {"regulator_id": "CPPA", "name": "California Privacy Protection Agency", "jurisdiction": "California",
     "priority_weights": {"consumer_rights": 0.9, "data_sharing": 0.8}, "enforcement_frequency_weight": 0.7},
]


def _heatmap():
    cats = Counter({"data_sharing": 12, "ai_automated_decisions": 3, "consumer_rights": 8})
    return heatmap_to_serializable(build_regulator_heatmap(_REGULATORS, cats))


def _full_payload(**overrides):
    """A complete Brex-like payload — every panel has real data."""
    defaults = dict(
        assessment_id="brex-demo-0001",
        org_name="Brex, Inc.",
        scores={
            "f002": {"score": 62.4, "tier": "high", "band": "", "lineage": {}},
            "f003": {"score": 22.1, "tier": "", "band": "",
                     "lineage": {"org_score": 70.9, "top_quartile_score": 84.5,
                                 "deviation": 13.6, "n_peers": 93, "weighted": True}},
            "f005": {"score": 98.5, "tier": "", "band": "", "lineage": {}},
            "f006": {"score": 45.1, "tier": "", "band": "", "lineage": {}},
            "f007": {"score": 15.7, "tier": "", "band": "", "lineage": {}},
            "f008": {"score": 58.3, "tier": "", "band": "",
                     "lineage": {"contributors": [{"code": "AI-004", "score": 70.0}]}},
            "f010": {"score": 70.9, "tier": "", "band": "Developing", "lineage": {}},
            "f011": {"score": 88.1, "tier": "", "band": "", "lineage": {}},
        },
        findings=[
            {"code": "AI-004", "domain": "ai_automated_decisions", "severity": "high", "score": 70.0},
            {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
            {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 45.0},
        ],
        vci={"score": 71.4, "label": "Moderate", "guidance": "Present with clear limitations"},
        narrative_exec="Brex presents an overall score of 70.9 out of 100 (Developing).",
        narrative_takeaways=["Data sharing exposure elevated (SH-002, 65.0/100)."],
        narrative_recommendations=[
            {"severity": "high", "code": "AI-004", "title": "Disclose automated decision logic",
             "prose": "Add a plain-language explanation of automated decisions."},
        ],
        exemplars=[],
        enforcement_heatmap=_heatmap(),
        org_clauses_by_domain={"data_sharing": "We share personal information with partners."},
        cohort_size=93,
        cohort_date="2026-08-05",
        snapshot_id="a1b2c3d4e5f600112233",
        guardrail_result={"status": "passed", "checked": 12},
    )
    defaults.update(overrides)
    return assemble_report(**defaults)


def _absence_payload():
    """A payload where the honest-absence branches must fire: no VCI score, no
    peer benchmark, no exemplar, no trend, no overall score."""
    return assemble_report(
        assessment_id="empty-0001",
        org_name="Fixture Co.",
        scores={
            "f003": {"score": 0.0, "tier": "", "band": "", "lineage": {"reason": "no_peers"}},
            "f010": {"score": None, "tier": "", "band": "", "lineage": {}},
            "f011": {"score": None, "tier": "", "band": "", "lineage": {}},
        },
        findings=[],
        vci={"score": None, "label": ""},
        narrative_exec="Scoring for Fixture Co. has not yet completed.",
        narrative_takeaways=[],
        narrative_recommendations=[],
        exemplars=[],
        enforcement_heatmap=[],
        org_clauses_by_domain={},
        cohort_size=0,
        cohort_date="2026-08-05",
        snapshot_id="deadbeef0000",
        guardrail_result={"status": "not_recorded"},
    )


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _body_only(html: str) -> str:
    """Strip the <style> block so brace assertions only see rendered content."""
    return re.sub(r"<style.*?</style>", "", html, flags=re.S)


# ── Determinism ─────────────────────────────────────────────────────────────

def test_pdf_byte_identical_across_simulated_date_change(monkeypatch):
    """Same frozen payload → identical PDF bytes, even if the wall clock moves
    between renders. Proves the render path takes NO now()/today()."""
    report = _full_payload()
    a = render_pdf_weasyprint(report)

    # Simulate the calendar advancing between two renders of the SAME snapshot.
    import app.services.report.assembly as asm

    class _FakeDate(asm.date):
        @classmethod
        def today(cls):
            return asm.date(2027, 1, 1)

    monkeypatch.setattr(asm, "date", _FakeDate)
    b = render_pdf_weasyprint(report)

    assert a and b
    assert _sha(a) == _sha(b), "restyled PDF is no longer byte-identical for a frozen snapshot"


def test_pdf_carries_no_nondeterministic_metadata():
    pdf = render_pdf_weasyprint(_full_payload())
    for tag in (b"/CreationDate", b"/ModDate", b"/ID"):
        assert tag not in pdf, f"PDF contains {tag.decode()} — breaks byte-identity"


def test_html_identical_from_same_inputs():
    assert render_html(_full_payload()) == render_html(_full_payload())


# ── Honest absence ──────────────────────────────────────────────────────────

def test_absence_states_render_not_fabricated_numbers():
    html = render_html(_absence_payload())

    # The honest-absence copy must appear …
    assert "Not recorded" in html                      # VCI / overall KPI + gauge
    assert "Insufficient peer data" in html            # §4 — no fabricated industry avg
    assert "Trend begins after your next monitored capture" in html  # §12
    assert "Language benchmarking pending" in html     # §8 — no unapproved exemplar

    # … and the fabricated-layout artefacts must NOT.
    body = _body_only(html)
    assert "Peer top-quartile threshold" not in body, "drew a peer bar with no peer data"
    # No un-substituted template tokens anywhere in the visible body.
    assert re.search(r"\{[a-z][a-z0-9_]*\}", body) is None


def test_absent_score_is_not_rendered_as_zero():
    """A missing overall/percentile/VCI must read 'Not recorded', never '0.0'."""
    html = render_html(_absence_payload())
    # Isolate section 2 (exec summary) exactly, by its id boundaries.
    seg = html.split('id="section-2"')[1].split('id="section-3"')[0]
    assert "0.0" not in seg, "an absent metric was rendered as a fabricated 0.0"
    assert seg.count("Not recorded") >= 2


# ── Guardrail stays in the path ─────────────────────────────────────────────

def test_guardrail_still_fails_closed_after_restyle():
    """A banned term in generated prose must still hard-fail the snapshot build.
    The restyle must not route around reports._enforce_snapshot_prose."""
    from app.routers.reports import _enforce_snapshot_prose
    from app.services.guardrail import GuardrailError

    with pytest.raises(GuardrailError):
        _enforce_snapshot_prose(
            "This notice is in violation of the law.",  # 'violation' is banned
            [],
            [],
        )


# ── Partner branding (F20) ──────────────────────────────────────────────────

def test_branding_is_header_only_body_bytes_identical():
    report = _full_payload()
    plain = render_html(report)
    branded = render_html(report, branding={
        "partner_id": "p1", "partner_name": "Acme Partners", "brand_color": "#2FB3A0",
    })
    assert plain != branded
    # Remove the injected band → the rest of the document must be byte-identical.
    stripped = re.sub(r'<div class="brand-band".*?</div>', "", branded, count=1, flags=re.S)
    assert stripped == plain, "branding changed the report body (F20 violation)"


def test_branding_rejects_css_injection_color():
    report = _full_payload()
    branded = render_html(report, branding={
        "partner_id": "p1", "partner_name": "Acme", "brand_color": "red;}body{display:none}",
    })
    # SEC-006: the malicious color is dropped for the safe default; the payload
    # never reaches the CSS context.
    assert "display:none" not in branded
    assert "#0f3460" in branded  # the safe default color


# ── Placeholder leak ────────────────────────────────────────────────────────

def test_no_template_token_survives_render():
    report = _full_payload(narrative_recommendations=[
        {"severity": "high", "code": "AI-004", "title": "Explain {ai_use_cases}",
         "prose": "Given your use of {ai_use_cases}, describe {sensitive_data_types} handling."},
    ])
    body = _body_only(render_html(report))
    assert "{ai_use_cases}" not in body
    assert "{sensitive_data_types}" not in body
    assert re.search(r"\{[a-z][a-z0-9_]*\}", body) is None


def test_strip_placeholders_reads_cleanly():
    out = _strip_placeholders("Given your use of {ai_use_cases}, review {sensitive_data_types} now.")
    assert "{" not in out and "}" not in out
    assert "  " not in out
    assert " ," not in out


# ── Visual artefact for human review ────────────────────────────────────────

def test_renders_valid_pdf_artifact(tmp_path):
    pdf = render_pdf_weasyprint(_full_payload())
    assert pdf.startswith(b"%PDF"), "output is not a PDF"
    assert len(pdf) > 20_000, "PDF suspiciously small — design likely didn't render"
    out = tmp_path / "brex_sample.pdf"
    out.write_bytes(pdf)
    assert out.stat().st_size == len(pdf)
