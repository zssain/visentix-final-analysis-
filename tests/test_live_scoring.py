"""Live scoring pipeline tests — versioning quintet, object_types, population."""

import json
from collections import Counter
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.intake.decompose import DecomposedClause, DecomposedNotice, DecomposedSection
from app.services.live_scoring import (
    _FORMULA_OBJECT_TYPE,
    score_and_persist,
)


# ── Fixtures ──────────────────────────────────────────────────

def _make_notice() -> DecomposedNotice:
    """Create a minimal notice with clauses across several domains."""
    notice = DecomposedNotice()
    notice.sections.append(DecomposedSection(
        section_id="s1", title="Test", section_type="general", sequence=0, text="test",
    ))
    for i, (cat, ct) in enumerate([
        ("data_sharing", "Service Providers"),
        ("consumer_rights", "Access"),
        ("retention", "Specific Period"),
        ("tracking_cookies", "Cookies"),
        ("ai_automated_decisions", "AI Transparency"),
    ]):
        notice.clauses.append(DecomposedClause(
            clause_id=f"c{i}",
            section_id="s1",
            raw_text=f"Test clause about {cat} topic number {i} with enough words to classify.",
            normalized_text=f"test clause about {cat}",
            category=cat,
            ambiguity_score=0.02,
            readability_score=0.7,
            nlp_confidence=0.8,
            domain_id="SH" if cat == "data_sharing" else "CR",
            clause_type=ct,
            transparency_score=0.6,
        ))
    return notice


def _mock_httpx_client():
    """Create a mock httpx.AsyncClient that returns empty arrays for GET
    and 201 for POST."""
    client = AsyncMock()

    async def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        # Order matters: most-specific URL patterns first
        if "organization_intelligence_profile" in url:
            resp.json.return_value = []
        elif "recommendation_library" in url:
            resp.json.return_value = []
        elif "finding_type" in url:
            resp.json.return_value = [
                {"code": "SH-002", "title": "Data Sharing", "default_severity": "high", "domain": "data_sharing"},
            ]
        elif "formula_version" in url:
            resp.json.return_value = []
        elif "regulator?" in url:
            resp.json.return_value = [{
                "regulator_id": "FTC",
                "name": "FTC",
                "jurisdiction": "US-FED",
                "priority_weights": json.dumps({"data_sharing": 0.9, "tracking_cookies": 0.8}),
                "enforcement_frequency_weight": 0.9,
            }]
        elif "source_record" in url:
            resp.json.return_value = [{"source_reliability": 0.7}]
        elif "/organization?" in url:
            resp.json.return_value = [{
                "organization_id": "org-test",
                "name": "Test Org",
                "industry": "technology",
                "size": "medium",
                "geography": "US",
            }]
        else:
            resp.json.return_value = []
        return resp

    async def mock_post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 201
        resp.text = "Created"
        resp.json.return_value = []
        return resp

    client.get = mock_get
    client.post = mock_post

    return client


# ── Object type mapping ──────────────────────────────────────

def test_object_type_mapping_covers_all_formulas():
    """Every formula in the pipeline produces a known object_type."""
    expected = {
        "f002", "f003", "f005", "f006", "f007", "f008", "f009", "f010", "f011",
    }
    assert set(_FORMULA_OBJECT_TYPE.keys()) == expected


def test_object_types_are_valid():
    """object_type strings match the report system expectations."""
    expected_types = {
        "regulatory_exposure", "benchmark_deviation", "disclosure_maturity",
        "transparency", "ai_transparency", "compound_risk",
        "confidence_weighted", "overall_intelligence", "benchmark_percentile",
    }
    actual_types = {ot for ot, _ in _FORMULA_OBJECT_TYPE.values()}
    assert actual_types == expected_types


def test_formula_version_ids_are_valid():
    """Each formula has a correctly formatted version ID."""
    for fkey, (_, fv_id) in _FORMULA_OBJECT_TYPE.items():
        fnum = fkey.replace("f0", "F-0").replace("f", "F-")
        # F-002_v1, F-010_v1, etc.
        assert fv_id.startswith("F-"), f"Invalid version ID: {fv_id}"
        assert fv_id.endswith("_v1"), f"Invalid version ID: {fv_id}"


# ── End-to-end scoring (mocked DB) ───────────────────────────

@pytest.mark.anyio
async def test_score_and_persist_returns_scores():
    """Full pipeline produces scores, findings, VCI, and summary."""
    notice = _make_notice()
    mock_client = _mock_httpx_client()

    with patch("app.services.live_scoring.httpx.AsyncClient") as MockClass:
        MockClass.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClass.return_value.__aexit__ = AsyncMock(return_value=False)

        # Also mock the population builder to return a small cohort
        with patch("app.services.benchmark.population.build_population", new_callable=AsyncMock) as mock_pop:
            mock_pop.return_value = {
                "population_key": "IND-07|Moderate|Developing|Developing|Low|Minimal|Clean",
                "members": [
                    {"organization_id": f"peer-{i}", "pgms": 40 + i * 5,
                     "benchmark_weight": 0.8, "similarity": 0.7, "name": f"Peer {i}"}
                    for i in range(15)
                ],
                "cohort_size": 15,
                "relaxations": ["broader_industry_cohort"],
                "benchmark_population_version": 1720000000,
                "confidence_penalty": 0.15,
                "band": "broad",
            }

            result = await score_and_persist("org-test", "notice-test", notice)

    assert "scores" in result
    assert "vci" in result
    assert "findings" in result
    assert "summary" in result


@pytest.mark.anyio
async def test_score_and_persist_summary_has_required_fields():
    """Summary includes snapshot_id, cohort_size, and relaxations."""
    notice = _make_notice()
    mock_client = _mock_httpx_client()

    with patch("app.services.live_scoring.httpx.AsyncClient") as MockClass:
        MockClass.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClass.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.benchmark.population.build_population", new_callable=AsyncMock) as mock_pop:
            mock_pop.return_value = {
                "population_key": "test",
                "members": [{"organization_id": f"p{i}", "pgms": 50, "benchmark_weight": 0.8, "similarity": 0.7} for i in range(10)],
                "cohort_size": 10,
                "relaxations": ["broader_industry_cohort", "all_orgs_fallback"],
                "benchmark_population_version": 123,
                "confidence_penalty": 0.20,
                "band": "broad",
            }

            result = await score_and_persist("org-test", "notice-test", notice)

    summary = result["summary"]
    assert "snapshot_id" in summary
    assert "cohort_size" in summary
    assert summary["cohort_size"] == 10
    assert "relaxations" in summary
    assert "broader_industry_cohort" in summary["relaxations"]


@pytest.mark.anyio
async def test_small_population_records_confidence_penalty():
    """< 20 members should result in recorded relaxation."""
    notice = _make_notice()
    mock_client = _mock_httpx_client()

    with patch("app.services.live_scoring.httpx.AsyncClient") as MockClass:
        MockClass.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClass.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.benchmark.population.build_population", new_callable=AsyncMock) as mock_pop:
            mock_pop.return_value = {
                "population_key": "test",
                "members": [{"organization_id": "p0", "pgms": 50, "benchmark_weight": 0.7, "similarity": 0.6}],
                "cohort_size": 1,
                "relaxations": ["broader_industry_cohort", "all_orgs_fallback"],
                "benchmark_population_version": 999,
                "confidence_penalty": 0.20,
                "band": "broad",
            }

            result = await score_and_persist("org-test", "notice-test", notice)

    assert "all_orgs_fallback" in result["summary"]["relaxations"]
    assert result["summary"]["cohort_size"] == 1


@pytest.mark.anyio
async def test_vci_is_present_and_valid():
    """VCI must have score, label, and components."""
    notice = _make_notice()
    mock_client = _mock_httpx_client()

    with patch("app.services.live_scoring.httpx.AsyncClient") as MockClass:
        MockClass.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClass.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.benchmark.population.build_population", new_callable=AsyncMock) as mock_pop:
            mock_pop.return_value = {
                "population_key": "test",
                "members": [{"organization_id": f"p{i}", "pgms": 50, "benchmark_weight": 0.8, "similarity": 0.7} for i in range(25)],
                "cohort_size": 25,
                "relaxations": [],
                "benchmark_population_version": 456,
                "confidence_penalty": 0.08,
                "band": "adjacent",
            }

            result = await score_and_persist("org-test", "notice-test", notice)

    vci = result["vci"]
    assert 0 <= vci["score"] <= 100
    assert vci["label"] in ("very_high", "high", "moderate", "low", "very_low")
    assert "components" in vci


@pytest.mark.anyio
async def test_score_and_persist_eager_enqueues_for_sme_review():
    """F06 regression: completing an assessment enqueues it for SME review
    immediately (a DRAFT assessment_review row) — no by-id open required, so it
    is visible in the queue right after scoring (Stage-3 handoff fix)."""
    notice = _make_notice()
    mock_client = _mock_httpx_client()

    from unittest.mock import MagicMock
    enqueue = MagicMock()

    with patch("app.services.live_scoring.httpx.AsyncClient") as MockClass, \
         patch("app.services.review.get_or_create_review", enqueue):
        MockClass.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClass.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.benchmark.population.build_population", new_callable=AsyncMock) as mock_pop:
            mock_pop.return_value = {
                "population_key": "test",
                "members": [{"organization_id": f"p{i}", "pgms": 50, "benchmark_weight": 0.8, "similarity": 0.7} for i in range(10)],
                "cohort_size": 10, "relaxations": [], "benchmark_population_version": 1, "confidence_penalty": 0.1, "band": "broad",
            }
            await score_and_persist("org-test", "notice-eager-123", notice)

    enqueue.assert_called_once_with("notice-eager-123")
