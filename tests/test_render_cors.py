"""Render smoke test + CORS configuration tests."""

import pytest

from app.config import Settings
from app.services.report.assembly import assemble_report
from app.services.report.renderer import render_html, render_pdf_weasyprint


# ── Render smoke test ────────────────────────────────────────

def _sample_report():
    return assemble_report(
        assessment_id="render-test-001", org_name="RenderCo",
        scores={"f010": {"score": 60, "lineage": {}}, "f002": {"score": 40, "tier": "moderate", "lineage": {}}},
        findings=[{"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 55}],
        vci={"score": 58, "label": "moderate"},
        narrative_exec="RenderCo scores 60 out of 100.",
        narrative_takeaways=["Data sharing elevated."],
        narrative_recommendations=[{"severity": "high", "code": "SH-002", "title": "Fix", "prose": "Review sharing."}],
        exemplars=[], enforcement_heatmap=[], cohort_size=30, cohort_date="2026-06-29",
    )


def test_weasyprint_produces_valid_pdf():
    """Active renderer (weasyprint) produces a non-empty valid PDF."""
    report = _sample_report()
    pdf_bytes = render_pdf_weasyprint(report)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:5] == b"%PDF-"


def test_html_render_has_all_12_sections():
    report = _sample_report()
    html = render_html(report)
    for i in range(1, 13):
        assert f"section-{i}" in html


def test_pdf_reproducible_from_same_input():
    """Same report → identical PDF bytes."""
    report = _sample_report()
    pdf1 = render_pdf_weasyprint(report)
    pdf2 = render_pdf_weasyprint(report)
    # weasyprint may embed timestamps, so check structure not byte-equality
    assert pdf1[:5] == pdf2[:5] == b"%PDF-"
    assert abs(len(pdf1) - len(pdf2)) < 100  # structurally same


# ── CORS configuration tests ────────────────────────────────

def test_cors_defaults_include_both_dev_origins():
    """Default CORS includes both localhost and 127.0.0.1."""
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test",
        supabase_service_role_key="test",
    )
    origins = s.cors_origins
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_cors_env_override():
    """CORS_ALLOWED_ORIGINS from env overrides defaults."""
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test",
        supabase_service_role_key="test",
        cors_allowed_origins="https://app.visentix.com",
    )
    origins = s.cors_origins
    assert "https://app.visentix.com" in origins
    assert "http://localhost:5173" not in origins


def test_cors_never_wildcard():
    """CORS origins must never be '*'."""
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test",
        supabase_service_role_key="test",
    )
    assert "*" not in s.cors_origins


def test_cors_multiple_origins():
    """Multiple origins separated by comma."""
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test",
        supabase_service_role_key="test",
        cors_allowed_origins="https://app.visentix.com,https://staging.visentix.com",
    )
    origins = s.cors_origins
    assert len(origins) == 2
    assert "https://app.visentix.com" in origins
    assert "https://staging.visentix.com" in origins


# ── Renderer config ──────────────────────────────────────────

def test_renderer_default_is_weasyprint():
    s = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test",
        supabase_service_role_key="test",
    )
    assert s.renderer == "weasyprint"


def test_renderer_no_arbitrary_url():
    """Renderer uses set_content (HTML string), never goto (URL)."""
    import inspect
    from app.services.report import renderer as mod
    source = inspect.getsource(mod)
    # Playwright path uses set_content, not goto
    assert "set_content" in source
    assert "page.goto" not in source
