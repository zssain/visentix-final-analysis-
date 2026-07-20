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
# Test 4: Corpus tables stay populated (live invariant, not hardcoded counts)
#
# The old test hardcoded the 2026-06 inventory (organization==30,
# disclosure_clause==3655, …). Those numbers drift every time the corpus grows,
# so the assertion became noise. Replaced with live-query invariants that still
# fail loudly if a table is emptied or the category data is corrupted — without
# pinning a number that is guaranteed to go stale.
# ------------------------------------------------------------------
CORPUS_TABLES = [
    "organization", "source_record", "privacy_notice", "notice_section",
    "disclosure_clause", "obligation", "enforcement_record", "regulator",
    "litigation_event", "monitoring_event", "formula_version", "benchmark_membership",
]


@pytest.mark.parametrize("table", CORPUS_TABLES)
def test_corpus_tables_nonempty(table):
    """Each pre-existing corpus table must stay populated. Fails if emptied."""
    assert _count(table) > 0, f"{table} is empty — corpus data lost"


def test_disclosure_clause_category_reconciles():
    """Data-integrity invariant: the `category` histogram must sum to the table
    total, and there must be more than one category. Fails if rows are lost or
    category values are corrupted — no hardcoded magnitude."""
    total = _count("disclosure_clause")
    assert total > 0
    from collections import Counter
    hist = Counter()
    page = 1000
    offset = 0
    while offset < total:
        r = httpx.get(
            f"{URL}/rest/v1/disclosure_clause?select=category",
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + page - 1}"},
            timeout=30,
        )
        rows = r.json()
        if not rows:
            break
        hist.update(row["category"] for row in rows)
        offset += len(rows)
    assert sum(hist.values()) == total, f"category histogram {sum(hist.values())} != total {total}"
    assert len(hist) >= 2, "expected multiple categories — corpus looks degenerate"


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
def test_finding_type_no_stubs():
    """Findings were de-stubbed by update_findings.py. Flipped from the old
    assert-stubs-exist: no finding_type row may still carry a STUB marker.
    Fails if a stub returns."""
    r = _get("finding_type", select="code,title", limit=200)
    rows = r.json()
    assert len(rows) > 0, "finding_type is empty"
    stubs = [row["code"] for row in rows if "STUB" in (row.get("title") or "")]
    assert not stubs, f"finding_type rows still marked STUB: {stubs}"


def test_recommendation_library_no_stubs():
    """No recommendation_library row may still carry a STUB source_note.
    Fails if a stub returns."""
    r = _get("recommendation_library", select="finding_type_code,source_note", limit=200)
    rows = r.json()
    assert len(rows) > 0, "recommendation_library is empty"
    stubs = [row["finding_type_code"] for row in rows if "STUB" in (row.get("source_note") or "")]
    assert not stubs, f"recommendation_library rows still marked STUB: {stubs}"


def test_exemplar_stubs():
    r = _get("exemplar", select="source_internal_ref,clause_text,sme_cleaned", limit=100)
    rows = r.json()
    assert len(rows) >= 3  # 3 stubs + 40 auto-candidates + demo cleaned
    # Most should be sme_cleaned=false (stubs + candidates); some may be demo-cleaned
    uncleaned = [row for row in rows if not row["sme_cleaned"]]
    assert len(uncleaned) >= 40


# ------------------------------------------------------------------
# Test 7: organization_intelligence_profile populated (Phase 4)
# ------------------------------------------------------------------
def test_oip_populated():
    """Profiles exist. Live invariant (not a hardcoded 30, which drifts as the
    pipeline persists new org profiles). Fails if the table is emptied."""
    assert _count("organization_intelligence_profile") > 0
