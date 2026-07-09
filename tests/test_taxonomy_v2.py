"""VICBNF v2 clause taxonomy tests.

Validates:
1. Every one of the 30 clause_types resolves for a representative sentence.
2. Every clause_type has a legacy_slug that is one of the original 9 values.
3. JSON has no duplicate (domain_id, clause_type) pairs.
4. classify_clause() backward-compat still returns legacy slugs.
5. compute_transparency produces sensible scores.
6. DecomposedClause carries all new fields.
"""

import json
from pathlib import Path

import pytest

from app.services.intake.decompose import (
    CLAUSE_TAXONOMY,
    classify_clause,
    classify_clause_v2,
    compute_transparency,
    decompose,
)

LEGACY_SLUGS = {
    "consumer_rights", "data_sharing", "tracking_cookies", "retention",
    "ai_automated_decisions", "cross_border", "sensitive_data",
    "children_teens", "other",
}

VALID_DOMAIN_IDS = {"CR", "DC", "SH", "RT", "AI", "SEC", "TRK", "XB"}


# ── Taxonomy JSON structure ──────────────────────────────────

def test_taxonomy_json_loads():
    assert len(CLAUSE_TAXONOMY) == 30, f"Expected 30 clause types, got {len(CLAUSE_TAXONOMY)}"


def test_taxonomy_no_duplicate_pairs():
    pairs = [(e["domain_id"], e["clause_type"]) for e in CLAUSE_TAXONOMY]
    assert len(pairs) == len(set(pairs)), f"Duplicate (domain_id, clause_type) pairs found"


def test_taxonomy_all_domain_ids_valid():
    ids = {e["domain_id"] for e in CLAUSE_TAXONOMY}
    assert ids == VALID_DOMAIN_IDS, f"Domain IDs {ids} != expected {VALID_DOMAIN_IDS}"


def test_taxonomy_all_legacy_slugs_valid():
    slugs = {e["legacy_slug"] for e in CLAUSE_TAXONOMY}
    assert slugs.issubset(LEGACY_SLUGS), f"Unknown legacy slugs: {slugs - LEGACY_SLUGS}"


def test_taxonomy_entries_have_required_fields():
    for entry in CLAUSE_TAXONOMY:
        assert "domain_id" in entry
        assert "domain" in entry
        assert "clause_type" in entry
        assert "definition" in entry
        assert "keywords" in entry and len(entry["keywords"]) >= 1
        assert "legacy_slug" in entry


# ── Every clause_type resolves ───────────────────────────────

REPRESENTATIVE_SENTENCES = {
    # CR
    ("CR", "Access"): "You have the right to access your personal data and request a copy.",
    ("CR", "Delete"): "You have the right to delete your personal information from our systems.",
    ("CR", "Correct"): "You can correct any inaccurate personal information we hold about you.",
    ("CR", "Portability"): "You can request your data in a portable, machine-readable format.",
    ("CR", "Appeal"): "You may appeal our decision regarding your privacy request.",
    ("CR", "Opt-Out"): "You can opt out of the sale of your personal information at any time.",
    ("CR", "Authorized Agent"): "You may designate an authorized agent to submit requests on your behalf.",
    # DC
    ("DC", "Personal Information Categories"): "We collect the following categories of personal information from users.",
    ("DC", "Sensitive Information"): "We may collect sensitive personal information including health data.",
    ("DC", "Biometric Data"): "We collect biometric data such as fingerprint and facial recognition scans.",
    ("DC", "Precise Location"): "We collect precise geolocation data from your mobile device via GPS.",
    ("DC", "Children Data"): "We do not knowingly collect data from children under 13 without parental consent.",
    # SH
    ("SH", "Service Providers"): "We share data with service providers who process information on our behalf.",
    ("SH", "Advertising Networks"): "We share data with advertising networks for targeted ads and marketing.",
    ("SH", "Analytics Providers"): "We share usage data with analytics providers including Google Analytics.",
    ("SH", "Affiliates"): "We may share data with our affiliates and subsidiary companies.",
    ("SH", "Data Brokers"): "We may sell your data to data brokers and third-party purchasers.",
    # RT
    ("RT", "Specific Period"): "We retain your data for 12 months after account closure.",
    ("RT", "Criteria Based"): "We retain data as long as necessary for the business purpose for which it was collected.",
    ("RT", "Undefined"): "We retain your information for the retention period required by applicable law.",
    # AI
    ("AI", "Automated Decisions"): "We use automated decision-making that produces significant effects on you.",
    ("AI", "Profiling"): "We engage in profiling to evaluate your behavior and predict preferences.",
    ("AI", "Human Review"): "You may request human review and human intervention to contest the decision.",
    ("AI", "Training Data"): "Your data may be used to train our machine learning models.",
    ("AI", "AI Transparency"): "We use artificial intelligence for content moderation and impact assessment.",
    # SEC
    ("SEC", "Safeguards"): "We implement encryption, access controls, and security measures to protect your data.",
    ("SEC", "Incident / Breach Reference"): "In the event of a data breach, we will notify affected users promptly.",
    # TRK
    ("TRK", "Cookies"): "We use cookies, pixels, and beacon tracking technologies on our site.",
    ("TRK", "Preference Center"): "You can manage your cookie settings through our preference center.",
    # XB
    ("XB", "Transfers"): "Your data may be transferred internationally outside the EU using standard contractual clauses.",
}


@pytest.mark.parametrize(
    "expected_pair,sentence",
    list(REPRESENTATIVE_SENTENCES.items()),
    ids=[f"{d}-{ct}" for d, ct in REPRESENTATIVE_SENTENCES.keys()],
)
def test_clause_type_resolves(expected_pair, sentence):
    """Each of the 30 clause_types must resolve from its representative sentence."""
    domain_id, clause_type, legacy_slug, confidence = classify_clause_v2(sentence)
    expected_domain, expected_type = expected_pair
    assert domain_id == expected_domain, (
        f"Expected domain_id={expected_domain}, got {domain_id} for '{sentence[:60]}...'"
    )
    assert clause_type == expected_type, (
        f"Expected clause_type={expected_type}, got {clause_type} for '{sentence[:60]}...'"
    )
    assert confidence > 0.5


@pytest.mark.parametrize(
    "expected_pair,sentence",
    list(REPRESENTATIVE_SENTENCES.items()),
    ids=[f"{d}-{ct}-legacy" for d, ct in REPRESENTATIVE_SENTENCES.keys()],
)
def test_clause_type_has_valid_legacy_slug(expected_pair, sentence):
    """Every clause_type result must map to a valid legacy slug."""
    _, _, legacy_slug, _ = classify_clause_v2(sentence)
    assert legacy_slug in LEGACY_SLUGS, f"legacy_slug={legacy_slug} not in {LEGACY_SLUGS}"


# ── Backward compatibility ───────────────────────────────────

def test_classify_clause_returns_legacy_tuple():
    """The original classify_clause() API still returns (slug, confidence)."""
    slug, conf = classify_clause("We share your data with third party service providers.")
    assert slug == "data_sharing"
    assert isinstance(conf, float)
    assert conf >= 0.5


def test_classify_clause_unknown_still_other():
    slug, conf = classify_clause("Thank you for reading our policy document.")
    assert slug == "other"
    assert conf == 0.5


# ── Transparency score ───────────────────────────────────────

def test_transparency_specific_text():
    """Concrete text with timeframes, named parties should score higher."""
    text = (
        "We retain your personal data for 12 months after account closure. "
        "Data is encrypted using AES-256 and stored in the United States."
    )
    score = compute_transparency(text)
    assert score > 0.5, f"Expected > 0.5 for specific text, got {score}"


def test_transparency_vague_text():
    """Vague text should score lower."""
    text = (
        "We may sometimes share certain data with various partners "
        "as appropriate and reasonable from time to time."
    )
    score = compute_transparency(text)
    assert score < 0.5, f"Expected < 0.5 for vague text, got {score}"


def test_transparency_range():
    score = compute_transparency("We collect data.")
    assert 0.0 <= score <= 1.0


def test_transparency_empty():
    assert compute_transparency("") == 0.0


# ── Decompose carries new fields ─────────────────────────────

SAMPLE_NOTICE = """
# Introduction
We care about your privacy.

# How We Share Your Data
We share your data with third party service providers for operations.
We may disclose data to advertising partners for marketing.

# Your Rights
You have the right to access, delete, and correct your data.
You may opt out of data sales at any time.

# Data Retention
We retain your data for 12 months or as long as needed.

# Children's Privacy
Our services are not intended for children under 13.
"""


def test_decompose_clauses_have_domain_id():
    result = decompose(SAMPLE_NOTICE)
    clauses_with_domain = [c for c in result.clauses if c.domain_id]
    assert len(clauses_with_domain) >= 3, (
        f"Expected >=3 clauses with domain_id, got {len(clauses_with_domain)}"
    )


def test_decompose_clauses_have_clause_type():
    result = decompose(SAMPLE_NOTICE)
    clauses_with_type = [c for c in result.clauses if c.clause_type]
    assert len(clauses_with_type) >= 2, (
        f"Expected >=2 clauses with clause_type, got {len(clauses_with_type)}"
    )


def test_decompose_clauses_have_transparency_score():
    result = decompose(SAMPLE_NOTICE)
    for clause in result.clauses:
        assert 0.0 <= clause.transparency_score <= 1.0


def test_decompose_category_still_legacy_slug():
    """category field must still be one of the legacy 9 slugs."""
    result = decompose(SAMPLE_NOTICE)
    for clause in result.clauses:
        assert clause.category in LEGACY_SLUGS, (
            f"category={clause.category} not a legacy slug"
        )
