"""Guardrail tests — banned terms blocked, exposure phrasing passes, edge cases."""

import pytest

from app.services.guardrail import (
    BannedSpan,
    GuardrailError,
    check_generated_prose,
    check_text,
    enforce,
    load_banned_terms,
)


# ── Banned terms blocked ─────────────────────────────────────

@pytest.mark.parametrize("term", [
    "violation", "violates", "illegal", "unlawful",
    "non-compliant", "noncompliant", "breach of law",
    "guilty", "liable",
])
def test_banned_term_blocked(term):
    text = f"This practice is a {term} of privacy standards."
    spans = check_generated_prose(text)
    assert len(spans) > 0, f"'{term}' should be blocked"
    assert any(s.term == term.lower() for s in spans)


def test_banned_term_case_insensitive():
    spans = check_generated_prose("This is ILLEGAL and a VIOLATION.")
    terms = {s.term for s in spans}
    assert "illegal" in terms
    assert "violation" in terms


def test_enforce_raises_on_banned_term():
    with pytest.raises(GuardrailError, match="HARD FAIL"):
        enforce("The company violated privacy regulations.")


def test_enforce_error_includes_terms():
    try:
        enforce("This is illegal and a violation.")
    except GuardrailError as e:
        assert "illegal" in e.terms
        assert "violation" in e.terms
        assert len(e.spans) >= 2


def test_multi_word_banned_term():
    spans = check_generated_prose("This constitutes a breach of law under CCPA.")
    assert any(s.term == "breach of law" for s in spans)


def test_in_violation_of():
    spans = check_generated_prose("The practice is in violation of federal law.")
    terms = {s.term for s in spans}
    assert "in violation of" in terms or "violation" in terms


# ── Exposure phrasing passes ─────────────────────────────────

@pytest.mark.parametrize("text", [
    "This practice presents elevated exposure under CCPA requirements.",
    "Data sharing patterns indicate heightened scrutiny risk.",
    "The AI governance posture suggests moderate maturity gaps.",
    "Cross-border transfer disclosures show below-median completeness.",
    "Retention practices present elevated regulatory exposure.",
    "Benchmarked against 30 peers as of 2026-06-18 (small cohort).",
])
def test_exposure_phrasing_passes(text):
    spans = check_generated_prose(text)
    assert len(spans) == 0, f"Approved phrasing should pass: {text}"
    # enforce should return the text unchanged
    assert enforce(text) == text


# ── Source excerpt handling ───────────────────────────────────

def test_quoted_source_excerpt_allowed():
    """Banned terms inside quotes are source excerpts, not generated prose."""
    text = 'The FTC stated this was a "violation of Section 5" in their order.'
    # check_text finds it but marks as source excerpt
    all_spans = check_text(text)
    assert any(s.term == "violation" for s in all_spans)
    assert all(s.in_source_excerpt for s in all_spans if s.term == "violation")

    # check_generated_prose excludes source excerpts
    prose_spans = check_generated_prose(text)
    assert len(prose_spans) == 0, "Quoted source excerpt should be allowed"


def test_single_quotes_do_not_exempt():
    """GRD-003: stylistic single quotes are NOT a source-excerpt delimiter.

    This replaces the old test_single_quoted_source_allowed, which wrongly
    "proved" single quotes work using a single-quoted excerpt — conflating
    stylistic quoting/contractions with cited evidence. Per business-logic.md
    §2 an excerpt is exempt only when tagged [source: …] (see below). A banned
    term wrapped in single quotes in generated prose must be CAUGHT.
    """
    text = "The consent order described 'illegal data collection' practices."
    prose_spans = check_generated_prose(text)
    assert any(s.term == "illegal" for s in prose_spans), \
        "single-quoted 'illegal' must not be exempted"


@pytest.mark.parametrize("text", [
    # Verdict word sitting between two contraction apostrophes — the GRD-003 bypass.
    "The company's practice violates the vendor's terms.",
    "It's a case where the policy violates what we'd expect.",
    # Verdict word wrapped in stylistic single quotes.
    "The finding notes the clause 'violates' expected norms.",
    # Plain prose control (was already caught).
    "This clearly violates the rule.",
])
def test_contraction_and_single_quote_bypass_caught(text):
    """All must be caught after removing the single-quote alternation."""
    spans = check_generated_prose(text)
    assert any(s.term == "violates" for s in spans), \
        f"'violates' must be caught in: {text!r}"
    with pytest.raises(GuardrailError):
        enforce(text)


def test_source_tagged_excerpt_still_exempt_with_contractions():
    """A properly [source: …]-tagged excerpt remains exempt even with apostrophes."""
    text = "Per the record [source: FTC order: the company's conduct was a violation]."
    prose_spans = check_generated_prose(text)
    assert len(prose_spans) == 0, "attributed [source: …] excerpt must stay exempt"
    assert enforce(text) == text


def test_source_tag_allowed():
    text = "The enforcement record states [source: company found guilty of misuse]."
    prose_spans = check_generated_prose(text)
    assert len(prose_spans) == 0


def test_unquoted_banned_term_still_blocked():
    """Banned term OUTSIDE quotes must still be blocked."""
    text = 'The report noted a "violation of Section 5" and the company is liable.'
    prose_spans = check_generated_prose(text)
    assert any(s.term == "liable" for s in prose_spans)


def test_mixed_quoted_and_prose():
    """Quote is ok, but the same term outside the quote is not."""
    text = 'Per the FTC "violation of Section 5" order, this is a clear violation.'
    prose_spans = check_generated_prose(text)
    # "violation" appears twice: once in quotes (ok), once in prose (blocked)
    assert any(s.term == "violation" for s in prose_spans)
    assert len(prose_spans) >= 1


# ── Span positions ───────────────────────────────────────────

def test_span_positions_accurate():
    text = "This is an illegal practice."
    spans = check_text(text)
    assert len(spans) == 1
    s = spans[0]
    assert text[s.start:s.end].lower() == "illegal"


# ── Config extensibility ─────────────────────────────────────

def test_banned_terms_loaded_from_config():
    terms = load_banned_terms()
    assert "violation" in terms
    assert "guilty" in terms
    assert len(terms) >= 8  # at least the core terms


def test_config_comments_ignored():
    terms = load_banned_terms()
    assert not any(t.startswith("#") for t in terms)


# ── Edge cases ───────────────────────────────────────────────

def test_empty_text_passes():
    assert enforce("") == ""


def test_word_boundary_prevents_false_positives():
    """'viable' contains 'liable' but should NOT trigger (word boundary)."""
    spans = check_generated_prose("This approach is viable and reasonable.")
    assert len(spans) == 0, "'viable' should not trigger 'liable'"


def test_illegality_not_blocked():
    """Word boundary: 'illegality' is not exactly 'illegal'."""
    # Note: 'illegal' IS a substring at a word boundary in 'illegality'
    # because 'illegal' + 'ity' — \b matches between 'l' and 'i' only at edges.
    # Actually \billegal\b would NOT match 'illegality' because 'l' is followed by 'i'.
    # Let's verify:
    spans = check_generated_prose("The illegality was debated.")
    # 'illegality' contains 'illegal' but word boundary prevents match
    # because after 'illegal' there's 'ity' (not a boundary)
    assert len(spans) == 0, "'illegality' should not match \\billegal\\b"
