"""DATA-002 — content_hash must be a PURE content hash (tamper-evidence).

The report content_hash must depend ONLY on meaningful, immutable content
(scores, findings, approved narrative, config, formula/version refs) and MUST
NOT depend on volatile fields — the build date, snapshot_id, or any `_*`
runtime/envelope metadata.

Two reports identical in scores/findings/narrative but built on different days
(different `date`/`cohort_date`) and in different snapshots (different
`snapshot_id`, `_snapshot_id`, `_content_hash`, ...) must hash IDENTICALLY.
A report whose score actually changed must hash DIFFERENTLY.
"""

from dataclasses import asdict

from app.services.report.assembly import assemble_report
from app.routers.reports import _content_hash, _canonicalize_for_hash


# ── Fixture: a full report, parameterised on the volatile fields ─────────────

def _make_report(cohort_date: str, snapshot_id: str):
    return assemble_report(
        assessment_id="test-001",
        org_name="TestCo",
        scores={
            "f002": {"score": 45.0, "tier": "moderate", "band": "", "lineage": {}},
            "f010": {"score": 62.5, "tier": "", "band": "Developing", "lineage": {}},
            "f011": {"score": 71.0, "tier": "", "band": "", "lineage": {}},
        },
        findings=[
            {"code": "AI-004", "domain": "ai_automated_decisions", "severity": "high", "score": 70.0},
            {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 45.0},
            {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
        ],
        vci={"score": 58.0, "label": "Low", "guidance": "Present with clear confidence limitations"},
        narrative_exec="TestCo presents an overall score of 62.5 out of 100 (Developing).",
        narrative_takeaways=["AI exposure elevated.", "Data sharing exposure elevated."],
        narrative_recommendations=[
            {"severity": "high", "code": "AI-004", "title": "Address AI-004", "prose": "Review AI disclosures."},
            {"severity": "high", "code": "SH-002", "title": "Address SH-002", "prose": "Review data sharing."},
        ],
        exemplars=[],
        enforcement_heatmap=[],
        cohort_size=25,
        cohort_date=cohort_date,
        snapshot_id=snapshot_id,
    )


# ── Volatile fields must NOT affect the hash ────────────────────────────────

def test_hash_ignores_date_and_snapshot_id():
    """Identical content, DIFFERENT date + snapshot_id → EQUAL content_hash."""
    r_day1 = _make_report(cohort_date="2026-01-15", snapshot_id="snap-aaaaaaaa")
    r_day2 = _make_report(cohort_date="2026-08-04", snapshot_id="snap-bbbbbbbb")

    # Sanity: the raw dicts really do differ on the volatile fields.
    d1, d2 = asdict(r_day1), asdict(r_day2)
    assert d1 != d2, "fixture bug: dicts should differ on date/snapshot_id"

    assert _content_hash(d1) == _content_hash(d2), (
        "content_hash changed across days/snapshots for byte-identical content — "
        "it is not a pure content hash (weakens tamper-evidence)."
    )


def test_hash_ignores_runtime_underscore_metadata():
    """Injected `_*` envelope metadata (snapshot id, content hash, version,
    generated_at) must not affect the hash."""
    base = asdict(_make_report(cohort_date="2026-01-15", snapshot_id="snap-aaaaaaaa"))

    with_meta = dict(base)
    with_meta["_snapshot_id"] = "snap-zzzzzzzz"
    with_meta["_report_version"] = 7
    with_meta["_content_hash"] = "deadbeef" * 8
    with_meta["_generated_at"] = "2026-08-04T12:00:00Z"

    assert _content_hash(base) == _content_hash(with_meta), (
        "runtime `_*` metadata leaked into the content hash."
    )


def test_canonicalize_strips_volatile_keys_recursively():
    """The canonicalizer removes excluded/`_*` keys at every nesting depth."""
    raw = {
        "generated_date": "2026-01-15",
        "cohort_size": 25,
        "_content_hash": "x",
        "sections": [
            {
                "number": 1,
                "content": {
                    "overall_score": 62.5,
                    "date": "2026-01-15",
                    "snapshot_id": "snap-aaaa",
                    "_leaked": "runtime",
                },
            }
        ],
    }
    clean = _canonicalize_for_hash(raw)
    assert "generated_date" not in clean
    assert "_content_hash" not in clean
    assert clean["cohort_size"] == 25  # meaningful content preserved
    sec_content = clean["sections"][0]["content"]
    assert sec_content == {"overall_score": 62.5}, (
        f"volatile keys not stripped recursively: {sec_content}"
    )


# ── A real content change MUST change the hash ──────────────────────────────

def test_hash_changes_when_a_score_changes():
    """Changing a score (meaningful content) → DIFFERENT hash, even with the
    same date + snapshot_id."""
    r_base = _make_report(cohort_date="2026-01-15", snapshot_id="snap-aaaaaaaa")

    r_changed = assemble_report(
        assessment_id="test-001",
        org_name="TestCo",
        # f010 overall score changed 62.5 -> 99.0
        scores={
            "f002": {"score": 45.0, "tier": "moderate", "band": "", "lineage": {}},
            "f010": {"score": 99.0, "tier": "", "band": "Leading", "lineage": {}},
            "f011": {"score": 71.0, "tier": "", "band": "", "lineage": {}},
        },
        findings=[
            {"code": "AI-004", "domain": "ai_automated_decisions", "severity": "high", "score": 70.0},
            {"code": "RT-003", "domain": "retention", "severity": "medium", "score": 45.0},
            {"code": "SH-002", "domain": "data_sharing", "severity": "high", "score": 65.0},
        ],
        vci={"score": 58.0, "label": "Low", "guidance": "Present with clear confidence limitations"},
        narrative_exec="TestCo presents an overall score of 62.5 out of 100 (Developing).",
        narrative_takeaways=["AI exposure elevated.", "Data sharing exposure elevated."],
        narrative_recommendations=[
            {"severity": "high", "code": "AI-004", "title": "Address AI-004", "prose": "Review AI disclosures."},
            {"severity": "high", "code": "SH-002", "title": "Address SH-002", "prose": "Review data sharing."},
        ],
        exemplars=[],
        enforcement_heatmap=[],
        cohort_size=25,
        cohort_date="2026-01-15",
        snapshot_id="snap-aaaaaaaa",
    )

    assert _content_hash(asdict(r_base)) != _content_hash(asdict(r_changed)), (
        "content_hash did not change when a score changed — no tamper-evidence."
    )
