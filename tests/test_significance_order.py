"""Observations are ordered by significance, not by code (F05 / assurance skeleton).

The report's executive takeaways and recommendations were built from
`findings[:5]` over a list sorted alphabetically by finding code, so the report
led with whichever findings happened to sort first. A reader assumes the first
thing named is the most important one; alphabetical order silently broke that.
"""
import pytest

from app.routers.reports import _significance_key


def _f(code, severity, score):
    return {"code": code, "severity": severity, "score": score}


def test_severity_beats_alphabetical_order():
    """The bug in one assertion: SH-002 (high) must outrank AI-004 (low)."""
    findings = [_f("AI-004", "low", 30.0), _f("SH-002", "high", 65.0)]
    ordered = sorted(findings, key=_significance_key)
    assert [f["code"] for f in ordered] == ["SH-002", "AI-004"]


def test_within_a_severity_the_higher_score_leads():
    findings = [_f("AA-001", "high", 40.0), _f("ZZ-999", "high", 90.0)]
    ordered = sorted(findings, key=_significance_key)
    assert [f["code"] for f in ordered] == ["ZZ-999", "AA-001"]


def test_full_severity_ladder():
    findings = [
        _f("D", "low", 10.0), _f("B", "high", 10.0),
        _f("A", "critical", 10.0), _f("C", "medium", 10.0),
    ]
    assert [f["code"] for f in sorted(findings, key=_significance_key)] == ["A", "B", "C", "D"]


def test_ordering_is_total_and_deterministic():
    """Hard Rule 6: two renders of one snapshot must be byte-identical, which a
    non-total ordering would break. Equal severity AND equal score must still
    resolve to a stable order via the code."""
    findings = [_f("B-002", "high", 50.0), _f("A-001", "high", 50.0)]
    once = [f["code"] for f in sorted(findings, key=_significance_key)]
    twice = [f["code"] for f in sorted(list(reversed(findings)), key=_significance_key)]
    assert once == twice == ["A-001", "B-002"]


def test_unknown_severity_sorts_last_but_does_not_crash():
    """An unrecognised severity must not be silently promoted to the top of a
    customer's report."""
    findings = [_f("X", "not_a_severity", 99.0), _f("Y", "low", 1.0)]
    assert [f["code"] for f in sorted(findings, key=_significance_key)] == ["Y", "X"]


def test_missing_score_is_treated_as_zero_not_as_an_error():
    findings = [{"code": "A", "severity": "high"}, _f("B", "high", 10.0)]
    assert [f["code"] for f in sorted(findings, key=_significance_key)] == ["B", "A"]
