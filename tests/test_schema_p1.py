"""Phase 1 schema tests — verify new tables, columns, FKs, and stub data."""

import os

import httpx
import pytest
from dotenv import dotenv_values

CONFIG = dotenv_values(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Prefer": "count=exact"}


def _get(table: str, select: str = "*", filters: str = "", limit: int = 0):
    qs = f"select={select}&limit={limit}"
    if filters:
        qs += f"&{filters}"
    r = httpx.get(f"{URL}/rest/v1/{table}?{qs}", headers=HEADERS, timeout=15)
    return r


def _count(table: str) -> int:
    r = _get(table, limit=0)
    cr = r.headers.get("content-range", "*/0")
    return int(cr.split("/")[-1])


def _columns(table: str, expected: set[str] | None = None) -> set[str]:
    r = _get(table, limit=1)
    rows = r.json()
    if rows:
        return set(rows[0].keys())
    # Empty table — probe each expected column individually
    if expected is None:
        return set()
    found = set()
    for col in expected:
        r2 = _get(table, select=col, limit=0)
        if r2.status_code in (200, 206):
            found.add(col)
    return found


# ------------------------------------------------------------------
# Test 1: All new tables exist
# ------------------------------------------------------------------
NEW_TABLES = [
    "finding_type",
    "recommendation_library",
    "exemplar",
    "organization_intelligence_profile",
    "report_snapshot",
]


@pytest.mark.parametrize("table", NEW_TABLES)
def test_new_table_exists(table):
    r = _get(table, limit=0)
    assert r.status_code in (200, 206), f"{table} not accessible: {r.status_code}"


# ------------------------------------------------------------------
# Test 2: Expected columns on new tables
# ------------------------------------------------------------------
EXPECTED_COLS = {
    "finding_type": {"code", "title", "default_severity", "domain",
                     "regulator_relevance", "linked_recommendation_id", "sme_authored"},
    "recommendation_library": {"id", "finding_type_code", "severity_bucket", "title",
                               "body_template", "source_note", "sme_authored", "version"},
    "exemplar": {"id", "domain", "category", "clause_text", "maturity_note",
                 "source_internal_ref", "embedding", "sme_cleaned"},
    "organization_intelligence_profile": {"profile_id", "organization_id", "ic", "rss",
                                          "pgms", "osi", "dsi", "ehp", "aigms",
                                          "profile_version", "confidence_score", "generated_at"},
    "report_snapshot": {"snapshot_id", "organization_id", "notice_id", "payload",
                        "formula_version_set", "benchmark_population_version",
                        "source_corpus_version", "created_at"},
}


@pytest.mark.parametrize("table", EXPECTED_COLS.keys())
def test_new_table_columns(table):
    expected = EXPECTED_COLS[table]
    cols = _columns(table, expected=expected)
    missing = expected - cols
    assert not missing, f"{table} missing columns: {missing}"


# ------------------------------------------------------------------
# Test 3: Extended tables have new columns
# ------------------------------------------------------------------
def test_risk_finding_new_columns():
    for col in ["organization_id", "notice_id", "finding_type_code", "snapshot_id", "generated_at"]:
        r = _get("risk_finding", select=col, limit=0)
        assert r.status_code in (200, 206), f"risk_finding.{col} missing"


def test_clause_obligation_new_columns():
    for col in ["match_method", "similarity"]:
        r = _get("clause_obligation", select=col, limit=0)
        assert r.status_code in (200, 206), f"clause_obligation.{col} missing"


def test_benchmark_membership_new_columns():
    for col in ["normalization_score", "benchmark_weight", "inclusion_reason", "population_version"]:
        r = _get("benchmark_membership", select=col, limit=0)
        assert r.status_code in (200, 206), f"benchmark_membership.{col} missing"


def test_derived_data_item_new_columns():
    for col in ["score", "confidence_index", "source_lineage"]:
        r = _get("derived_data_item", select=col, limit=0)
        assert r.status_code in (200, 206), f"derived_data_item.{col} missing"


# ------------------------------------------------------------------
# Test 4: Pre-existing row counts unchanged
# ------------------------------------------------------------------
INVENTORY_COUNTS = {
    "organization": 30,
    "source_record": 303,
    "privacy_notice": 26,
    "notice_section": 767,
    "disclosure_clause": 3655,
    "obligation": 154,
    "enforcement_record": 172,
    "regulator": 9,
    "litigation_event": 14,
    "monitoring_event": 5,
    "formula_version": 14,
    "benchmark_membership": 30,
}


@pytest.mark.parametrize("table,expected", INVENTORY_COUNTS.items())
def test_preexisting_row_counts(table, expected):
    actual = _count(table)
    assert actual == expected, f"{table}: expected {expected}, got {actual}"


# ------------------------------------------------------------------
# Test 5: FK resolution — recommendation_library → finding_type
# ------------------------------------------------------------------
def test_fk_recommendation_to_finding_type():
    """Every recommendation_library.finding_type_code exists in finding_type."""
    r = _get("recommendation_library", select="finding_type_code", limit=100)
    rec_codes = {row["finding_type_code"] for row in r.json()}

    r2 = _get("finding_type", select="code", limit=100)
    ft_codes = {row["code"] for row in r2.json()}

    orphans = rec_codes - ft_codes
    assert not orphans, f"FK broken — recommendation codes not in finding_type: {orphans}"


# ------------------------------------------------------------------
# Test 6: Stub data integrity
# ------------------------------------------------------------------
def test_finding_type_stubs():
    r = _get("finding_type", select="code,title,sme_authored", limit=100)
    rows = r.json()
    assert len(rows) == 8
    for row in rows:
        assert row["sme_authored"] is False, f"{row['code']} sme_authored != false"
        assert "STUB" in row["title"], f"{row['code']} title missing STUB marker"


def test_recommendation_library_stubs():
    r = _get("recommendation_library", select="finding_type_code,source_note,sme_authored", limit=100)
    rows = r.json()
    assert len(rows) == 8
    for row in rows:
        assert row["sme_authored"] is False
        assert "STUB" in (row["source_note"] or "")


def test_exemplar_stubs():
    r = _get("exemplar", select="source_internal_ref,clause_text,sme_cleaned", limit=100)
    rows = r.json()
    assert len(rows) >= 3  # 3 stubs + 40 auto-candidates from Phase 3.2
    # All should be sme_cleaned=false (stubs + candidates)
    for row in rows:
        assert row["sme_cleaned"] is False


# ------------------------------------------------------------------
# Test 7: organization_intelligence_profile populated (Phase 4)
# ------------------------------------------------------------------
def test_oip_populated():
    assert _count("organization_intelligence_profile") == 30
