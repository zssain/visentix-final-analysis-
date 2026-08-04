"""SEC-008 — RLS policy ledger-drift guard.

The live schema dump showed the three notice-table SELECT policies from
migration 0011 were ABSENT despite 0011 being marked applied (ledger drift). The
corrective migration 0046 re-applies them. These static checks guard the
migration set so the policies can't silently disappear again; the LIVE
verification (does pg_policies actually contain them) is a BLOCKED-EXTERNAL step —
the exact query is asserted here as documentation.
"""

from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "db" / "migrations"

EXPECTED_POLICIES = {
    "privacy_notice_select",
    "notice_section_select",
    "disclosure_clause_select",
}


def _all_migration_sql() -> str:
    return "\n".join(p.read_text() for p in MIGRATIONS.glob("*.sql"))


def test_notice_rls_policies_declared_in_migration_set():
    """Every expected notice-table policy must be CREATE'd somewhere in the set
    (0011 originally, 0046 corrective) — guards against accidental removal."""
    sql = _all_migration_sql()
    for policy in EXPECTED_POLICIES:
        assert f'"{policy}"' in sql, f"RLS policy {policy} missing from migration set"


def test_corrective_migration_present_and_registered():
    """SEC-008 corrective migration exists and re-declares all three policies."""
    corrective = MIGRATIONS / "0046_reapply_notice_rls_policies.sql"
    assert corrective.exists(), "SEC-008 corrective migration 0046 missing"
    body = corrective.read_text()
    for policy in EXPECTED_POLICIES:
        assert f'"{policy}"' in body

    # It must be in the apply manifest so it actually gets applied.
    from scripts.db.apply_and_record import APPLY_NOW
    assert "0046_reapply_notice_rls_policies.sql" in APPLY_NOW


# LIVE verification (BLOCKED-EXTERNAL — needs a live DB session). After applying
# 0046, this query MUST return all three rows:
LIVE_VERIFY_QUERY = """
SELECT tablename, policyname FROM pg_policies
WHERE schemaname = 'public'
  AND policyname IN ('privacy_notice_select','notice_section_select','disclosure_clause_select')
ORDER BY tablename;
-- Expect 3 rows (privacy_notice, notice_section, disclosure_clause). 0 rows = drift persists.
"""


def test_live_verify_query_is_documented():
    """Sanity: the live drift-check query names all three policies + pg_policies."""
    for policy in EXPECTED_POLICIES:
        assert policy in LIVE_VERIFY_QUERY
    assert "pg_policies" in LIVE_VERIFY_QUERY
