"""Phase 5 intake tests — SSRF, size limits, decomposition, classification."""

import pytest

from app.services.intake.ssrf import SSRFError, validate_url
from app.services.intake.extract import (
    ExtractionError,
    MAX_TEXT_LENGTH,
    extract_from_text,
)
from app.services.intake.decompose import (
    classify_clause,
    compute_ambiguity,
    compute_readability,
    decompose,
)


# ── SSRF defense ─────────────────────────────────────────────

def test_ssrf_blocks_private_10():
    with pytest.raises(SSRFError, match="private"):
        validate_url("http://10.0.0.1/admin")


def test_ssrf_blocks_private_172():
    with pytest.raises(SSRFError, match="private"):
        validate_url("http://172.16.0.1/internal")


def test_ssrf_blocks_private_192():
    with pytest.raises(SSRFError, match="private"):
        validate_url("http://192.168.1.1/router")


def test_ssrf_blocks_loopback():
    with pytest.raises(SSRFError, match="loopback|private"):
        validate_url("http://127.0.0.1/secret")


def test_ssrf_blocks_localhost():
    with pytest.raises(SSRFError, match="loopback|private"):
        validate_url("http://localhost/admin")


def test_ssrf_blocks_metadata():
    with pytest.raises(SSRFError, match="link-local|metadata|private"):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_ssrf_blocks_ftp():
    with pytest.raises(SSRFError, match="scheme"):
        validate_url("ftp://example.com/file")


def test_ssrf_blocks_file():
    with pytest.raises(SSRFError, match="scheme"):
        validate_url("file:///etc/passwd")


def test_ssrf_allows_public_https():
    url = validate_url("https://example.com/privacy")
    assert url == "https://example.com/privacy"


# ── Text extraction ──────────────────────────────────────────

def test_text_extraction_basic():
    text, hash_ = extract_from_text("This is a test privacy notice.")
    assert text == "This is a test privacy notice."
    assert len(hash_) == 64  # sha256 hex


def test_text_extraction_empty_rejected():
    with pytest.raises(ExtractionError, match="Empty"):
        extract_from_text("")


def test_text_extraction_whitespace_rejected():
    with pytest.raises(ExtractionError, match="Empty"):
        extract_from_text("   \n\t  ")


def test_text_extraction_oversized_rejected():
    with pytest.raises(ExtractionError, match="too long"):
        extract_from_text("x" * (MAX_TEXT_LENGTH + 1))


# ── Classification ───────────────────────────────────────────

def test_classify_data_sharing():
    cat, conf = classify_clause("We share your data with third party service providers.")
    assert cat == "data_sharing"
    assert conf >= 0.6


def test_classify_tracking():
    cat, conf = classify_clause("We use cookies and tracking pixels for analytics.")
    assert cat == "tracking_cookies"


def test_classify_consumer_rights():
    cat, conf = classify_clause("You have the right to delete your personal data and opt out.")
    assert cat == "consumer_rights"


def test_classify_ai():
    cat, conf = classify_clause("We use automated decision-making and AI profiling algorithms.")
    assert cat == "ai_automated_decisions"


def test_classify_retention():
    cat, conf = classify_clause("We retain your data for the retention period specified.")
    assert cat == "retention"


def test_classify_children():
    cat, conf = classify_clause("Our services are not directed to children under 13.")
    assert cat == "children_teens"


def test_classify_sensitive():
    cat, conf = classify_clause("We collect biometric and health data with explicit consent.")
    assert cat == "sensitive_data"


def test_classify_cross_border():
    cat, conf = classify_clause("Your data may be transferred internationally outside the EU.")
    assert cat == "cross_border"


def test_classify_unknown():
    cat, conf = classify_clause("Thank you for reading our policy document.")
    assert cat == "other"
    assert conf == 0.5


# ── Ambiguity ────────────────────────────────────────────────

def test_ambiguity_clear_text():
    score = compute_ambiguity("We collect your email address when you sign up.")
    assert score < 0.05


def test_ambiguity_vague_text():
    score = compute_ambiguity("We may sometimes share certain data as appropriate and reasonable.")
    assert score > 0.05


# ── Readability ──────────────────────────────────────────────

def test_readability_short_sentences():
    score = compute_readability("We collect data. We use it. We protect it.")
    assert score > 0.5


def test_readability_long_sentences():
    long = ("We collect information about you through various means including but "
            "not limited to cookies web beacons and other tracking technologies "
            "that are used to gather data about your browsing behavior and preferences "
            "across multiple websites and online services.")
    score = compute_readability(long)
    assert score < 0.5


# ── Full decomposition ──────────────────────────────────────

SAMPLE_NOTICE = """
# Introduction
We care about your privacy.

# Information We Collect
We collect your email address and browsing data.
We use cookies and tracking pixels for analytics.

# How We Share Your Data
We share your data with third party service providers for operations.
We may disclose data to partners for advertising.

# Your Rights
You have the right to access, delete, and correct your data.
You may opt out of data sales at any time.

# Data Retention
We retain your data for 3 years or as long as needed.

# Children's Privacy
Our services are not intended for children under 13.
"""


def test_decompose_produces_sections():
    result = decompose(SAMPLE_NOTICE)
    assert len(result.sections) >= 4


def test_decompose_produces_clauses():
    result = decompose(SAMPLE_NOTICE)
    assert len(result.clauses) >= 5


def test_decompose_classifies_clauses():
    result = decompose(SAMPLE_NOTICE)
    categories = {c.category for c in result.clauses}
    assert "tracking_cookies" in categories or "data_sharing" in categories


def test_decompose_clause_has_scores():
    result = decompose(SAMPLE_NOTICE)
    for clause in result.clauses:
        assert 0 <= clause.ambiguity_score <= 1
        assert 0 <= clause.readability_score <= 1
        assert 0 <= clause.nlp_confidence <= 1


def test_decompose_deterministic():
    r1 = decompose(SAMPLE_NOTICE)
    r2 = decompose(SAMPLE_NOTICE)
    assert len(r1.sections) == len(r2.sections)
    assert len(r1.clauses) == len(r2.clauses)
    # Categories should match (UUIDs will differ)
    cats1 = [c.category for c in r1.clauses]
    cats2 = [c.category for c in r2.clauses]
    assert cats1 == cats2
