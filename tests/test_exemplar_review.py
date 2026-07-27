"""Exemplar review tests — approve, de-identification, Section 8 rendering."""

import pytest

from app.services.exemplar_review import (
    DeIdentificationError,
    redact,
    validate_deidentification,
    validate_exemplar_for_approval,
)
from app.services.report.assembly import assemble_report


# ── De-identification validation ─────────────────────────────

def test_clean_text_passes():
    found = validate_deidentification(
        "[Organization] shares data with third-party service providers."
    )
    assert found == []


def test_org_name_blocked():
    found = validate_deidentification(
        "PayPal shares data with third-party service providers."
    )
    assert "paypal" in found


def test_multiple_org_names_blocked():
    found = validate_deidentification(
        "Stripe and Coinbase both share data with partners."
    )
    assert "stripe" in found
    assert "coinbase" in found


def test_case_insensitive():
    found = validate_deidentification("FEDEX ships your packages.")
    assert "fedex" in found


def test_extra_blocked_tokens():
    found = validate_deidentification(
        "Acme Corp processes your data.",
        extra_blocked_tokens={"acme corp"},
    )
    assert "acme corp" in found


def test_placeholder_org_allowed():
    found = validate_deidentification("[Organization] processes your data.")
    assert found == []


# ── Structural PII (email / URL) de-id gate (Phase 5.4) ──────

def test_email_blocked():
    found = validate_deidentification(
        "Contact us at privacy@example.com to exercise your rights."
    )
    assert any(f.startswith("email:") for f in found)


def test_url_blocked():
    found = validate_deidentification(
        "See our full policy at https://acme-corp.com/privacy for details."
    )
    assert any(f.startswith("url:") for f in found)


def test_approve_with_email_rejected():
    """An exemplar containing an email address must NOT be approvable — the email
    identifies the source even after org names are stripped (F06 de-id gate)."""
    error = validate_exemplar_for_approval(
        "[Organization] lets you email privacy@company.com to delete your data.",
        "High maturity — clear rights channel.",
    )
    assert error is not None
    assert "identifying" in error.lower()


def test_redact_removes_email_and_url():
    cleaned = redact("Email privacy@x.com or visit https://x.com/privacy — PayPal policy.")
    assert "@" not in cleaned and "http" not in cleaned and "paypal" not in cleaned.lower()
    assert validate_deidentification(cleaned) == []


# ── Approval validation ──────────────────────────────────────

def test_approve_without_text_rejected():
    error = validate_exemplar_for_approval(None, "Some maturity note")
    assert error is not None
    assert "de-identified" in error.lower() or "cleaned" in error.lower()


def test_approve_with_short_text_rejected():
    error = validate_exemplar_for_approval("too short", "note")
    assert error is not None


def test_approve_without_maturity_note_rejected():
    error = validate_exemplar_for_approval(
        "[Organization] shares data with service providers for operations.",
        None,
    )
    assert error is not None
    assert "maturity" in error.lower()


def test_approve_with_org_name_rejected():
    error = validate_exemplar_for_approval(
        "PayPal shares data with third-party service providers for analytics.",
        "High maturity — names categories.",
    )
    assert error is not None
    assert "identifying" in error.lower()


def test_approve_with_clean_text_passes():
    error = validate_exemplar_for_approval(
        "[Organization] shares data with third-party service providers for operations and analytics.",
        "High maturity — names categories and purposes.",
    )
    assert error is None


# ── Section 8 rendering ──────────────────────────────────────

def _build_report(exemplars):
    return assemble_report(
        assessment_id="test", org_name="TestCo",
        scores={"f010": {"score": 50}},
        findings=[], vci={"label": "moderate"},
        narrative_exec="Summary.", narrative_takeaways=[], narrative_recommendations=[],
        exemplars=exemplars, enforcement_heatmap=[],
    )


def test_section8_renders_cleaned_exemplars():
    report = _build_report([
        {"domain": "data_sharing", "clause_text": "De-identified sharing text.", "sme_cleaned": True},
    ])
    s8 = report.sections[7]  # Section 8
    assert s8.content["sme_cleaned_available"] is True
    texts = [e["exemplar_text"] for e in s8.content["entries"]]
    assert "De-identified sharing text." in texts


def test_section8_excludes_uncleaned():
    report = _build_report([
        {"domain": "data_sharing", "clause_text": "Cleaned.", "sme_cleaned": True},
        {"domain": "retention", "clause_text": "Raw competitor text.", "sme_cleaned": False},
    ])
    s8 = report.sections[7]
    texts = [e["exemplar_text"] for e in s8.content["entries"]]
    assert "Cleaned." in texts
    assert "Raw competitor text." not in texts


@pytest.mark.skip(reason="DEBT: report Section 8 emits no placeholder entry when there are no "
                         "SME-cleaned exemplars — report-builder placeholder path unimplemented")
def test_section8_placeholder_when_none_cleaned():
    report = _build_report([
        {"domain": "data_sharing", "clause_text": "Raw.", "sme_cleaned": False},
    ])
    s8 = report.sections[7]
    assert s8.content["sme_cleaned_available"] is False
    assert "pending" in s8.content["entries"][0]["exemplar_text"].lower()


def test_section8_placeholder_when_empty():
    report = _build_report([])
    s8 = report.sections[7]
    assert s8.content["sme_cleaned_available"] is False
