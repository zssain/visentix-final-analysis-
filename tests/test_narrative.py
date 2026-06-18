"""Narrative tests — no new numbers, guardrail passes, fallback works."""

import pytest

from app.services.narrative import (
    NarrativeOutput,
    Statement,
    build_executive_summary_statement,
    build_recommendation_statements,
    build_takeaway_statements,
    extract_numbers,
    generate_narrative,
    verify_rephrased,
)


# ── Number extraction ────────────────────────────────────────

def test_extract_numbers():
    nums = extract_numbers("Score is 75.3 out of 100, percentile 84 (n=30).")
    assert "75.3" in nums
    assert "100" in nums
    assert "84" in nums
    assert "30" in nums


def test_extract_numbers_with_decimals():
    nums = extract_numbers("Improved from 60.5 to 69.2 points.")
    assert "60.5" in nums
    assert "69.2" in nums


# ── Verification ─────────────────────────────────────────────

def test_verify_identical_text():
    passed, reason = verify_rephrased("Score is 75.3.", "Score is 75.3.")
    assert passed


def test_verify_new_number_fails():
    passed, reason = verify_rephrased(
        "Score is 75.3 out of 100.",
        "Score is 75.3 out of 100, representing a 25% gap.",
    )
    assert not passed
    assert "New numbers" in reason


def test_verify_rephrased_without_new_numbers():
    source = "The organization scores 65.5 out of 100 at the 72nd percentile."
    rephrased = "With a score of 65.5 out of 100, the organization ranks at the 72nd percentile."
    passed, reason = verify_rephrased(source, rephrased)
    assert passed


def test_verify_too_many_numbers_lost():
    source = "Scores: 75.3, 84.5, 30, 65.2, 90.1."
    rephrased = "The score was high."  # lost all numbers
    passed, reason = verify_rephrased(source, rephrased)
    assert not passed
    assert "lost" in reason.lower()


def test_verify_new_entity_fails():
    source = "Acme Corp presents elevated exposure."
    rephrased = "Acme Corp and Google present elevated exposure."
    passed, reason = verify_rephrased(
        source, rephrased, known_entities={"Acme Corp", "Google"}
    )
    assert not passed
    assert "entities" in reason.lower()


# ── Statement builders ───────────────────────────────────────

def test_executive_summary_contains_all_numbers():
    stmt = build_executive_summary_statement(
        org_name="TestCo",
        overall_score=72.5,
        percentile=85.0,
        vci_label="high",
        cohort_size=30,
        cohort_date="2026-06-18",
        finding_count=5,
        top_domain="data sharing",
    )
    nums = extract_numbers(stmt.template)
    assert "72.5" in nums
    assert "30" in nums
    assert "5" in nums
    assert "TestCo" in stmt.template


def test_takeaway_statements_per_finding():
    findings = [
        {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
        {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 40.0},
    ]
    stmts = build_takeaway_statements(findings, {})
    assert len(stmts) == 2
    assert "65.0" in stmts[0].template
    assert "SH-002" in stmts[0].template
    assert stmts[0].severity == "high"


def test_recommendation_statements_from_library():
    findings = [{"code": "RT-003", "domain": "retention", "severity": "medium", "score": 50}]
    library = {
        "RT-003": {
            "title": "Define Retention Periods",
            "body_template": "Review retention practices for {domain} data.",
        }
    }
    stmts = build_recommendation_statements(findings, library)
    assert len(stmts) == 1
    assert "retention" in stmts[0].template.lower()


# ── Narrative generation (no LLM — template fallback) ────────

@pytest.mark.anyio
async def test_narrative_without_llm():
    """Without an LLM, templates are used directly."""
    scores = {
        "f010": {"score": 72.5},
        "f011": {"score": 85.0},
    }
    findings = [
        {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
    ]
    vci = {"label": "high", "score": 65}

    result = await generate_narrative(
        org_name="TestCo",
        scores=scores,
        findings=findings,
        vci=vci,
        recommendation_library={},
        rephrase_fn=None,
    )

    assert isinstance(result, NarrativeOutput)
    assert "TestCo" in result.executive_summary
    assert "72.5" in result.executive_summary
    assert len(result.takeaways) == 1
    assert len(result.recommendations) == 1


@pytest.mark.anyio
async def test_narrative_guardrail_on_templates():
    """Templates themselves must pass the guardrail."""
    scores = {"f010": {"score": 50}, "f011": {"score": 50}}
    findings = []
    vci = {"label": "moderate", "score": 50}

    result = await generate_narrative(
        org_name="SafeCo",
        scores=scores,
        findings=findings,
        vci=vci,
        recommendation_library={},
        rephrase_fn=None,
    )
    assert result.all_guardrail_passed


# ── LLM misbehavior fallback ─────────────────────────────────

@pytest.mark.anyio
async def test_fallback_on_new_numbers():
    """If LLM introduces new numbers, fall back to template."""

    async def bad_llm(template, context):
        return template + " This represents a 99% improvement over last year."

    scores = {"f010": {"score": 50}, "f011": {"score": 50}}
    findings = [{"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0}]
    vci = {"label": "moderate", "score": 50}

    result = await generate_narrative(
        org_name="TestCo",
        scores=scores,
        findings=findings,
        vci=vci,
        recommendation_library={},
        rephrase_fn=bad_llm,
    )
    # Should have fallen back on at least the exec summary
    assert result.fallback_count >= 1


@pytest.mark.anyio
async def test_fallback_on_guardrail_fail():
    """If LLM output contains banned terms, fall back to template."""

    async def banned_llm(template, context):
        return "This is a clear violation of privacy law."

    scores = {"f010": {"score": 50}, "f011": {"score": 50}}
    findings = []
    vci = {"label": "moderate", "score": 50}

    result = await generate_narrative(
        org_name="TestCo",
        scores=scores,
        findings=findings,
        vci=vci,
        recommendation_library={},
        rephrase_fn=banned_llm,
    )
    assert result.fallback_count >= 1
    # Fallback text should NOT contain banned terms
    assert "violation" not in result.executive_summary.lower()


@pytest.mark.anyio
async def test_fallback_on_llm_exception():
    """If LLM throws an error, fall back gracefully."""

    async def crashing_llm(template, context):
        raise RuntimeError("LLM connection failed")

    scores = {"f010": {"score": 50}, "f011": {"score": 50}}
    findings = []
    vci = {"label": "moderate", "score": 50}

    result = await generate_narrative(
        org_name="TestCo",
        scores=scores,
        findings=findings,
        vci=vci,
        recommendation_library={},
        rephrase_fn=crashing_llm,
    )
    # Should still produce output (template fallback)
    assert result.executive_summary != ""
    assert result.fallback_count >= 1


# ── Good LLM behavior ───────────────────────────────────────

@pytest.mark.anyio
async def test_good_llm_passes():
    """A well-behaved LLM that preserves numbers passes verification."""

    async def good_llm(template, context):
        # Rephrase but keep all numbers
        return template.replace("presents", "demonstrates").replace("placing", "ranking")

    scores = {"f010": {"score": 72.5}, "f011": {"score": 85.0}}
    findings = []
    vci = {"label": "high", "score": 65}

    result = await generate_narrative(
        org_name="TestCo",
        scores=scores,
        findings=findings,
        vci=vci,
        recommendation_library={},
        rephrase_fn=good_llm,
    )
    assert "72.5" in result.executive_summary
    assert result.fallback_count == 0
