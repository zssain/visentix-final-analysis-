"""Schema-typed fake guard (lesson L-007).

Proves the test doubles now reject writes whose Python type wouldn't survive the
real Postgres column — the mismatch that once passed tests but 400'd live — and
that the migration-derived type map still agrees with the live snapshot.
"""
import pytest

from tests.ingestion_fakes import (
    COLUMN_TYPES, MIGRATION_TYPES, SNAPSHOT, TypedFakeBackend, TypedFakeEventWriter,
    category, check_row,
)

_MIGRATION_TABLES = ["source_version", "ingestion_run", "security_event", "organization_alias"]


# ── the regression that motivated this ──────────────────────────────

def test_guard_rejects_text_into_integer_version_id():
    """The exact live bug: source_record.version_id is INTEGER; a text id must
    be rejected by the fake (was silently accepted before)."""
    with pytest.raises(TypeError, match="version_id"):
        check_row("source_record", {"source_id": "x", "version_id": "x#1"})
    # the corrected integer form passes
    check_row("source_record", {"source_id": "x", "version_id": 1})


def test_typed_backend_rejects_bad_source_record_write():
    be = TypedFakeBackend()
    with pytest.raises(TypeError):
        be.create_source_record({"source_id": "s", "version_id": "s#1"})   # text into INTEGER
    be.create_source_record({"source_id": "s", "version_id": 1})           # ok


def test_guard_rejects_other_type_mismatches_and_unknown_columns():
    with pytest.raises(TypeError):
        check_row("security_event", {"event_id": "e", "individuals_affected": "lots"})   # text→INTEGER
    with pytest.raises(TypeError):
        check_row("ingestion_run", {"records_seen": "5"})                                # text→INTEGER
    with pytest.raises(TypeError):
        check_row("source_record", {"source_id": "s", "no_such_column": "x"})            # unknown col
    # None is always allowed (SQL NULL); valid types pass
    check_row("security_event", {"event_id": "e", "individuals_affected": None, "extraction_confidence": 0.5})


def test_typed_event_writer_type_checks_and_dedups():
    w = TypedFakeEventWriter()
    good = {"event_id": "11111111-1111-1111-1111-111111111111", "individuals_affected": 500,
            "extraction_confidence": 1.0, "resolution_status": "unresolved"}
    assert w([good]) == 1
    assert w([good]) == 0                                   # dedup by event_id
    with pytest.raises(TypeError):
        w([{"event_id": "e2", "individuals_affected": "many"}])   # text→INTEGER


# ── can't drift silently: migrations must agree with the live snapshot ─

def test_migration_types_match_live_snapshot():
    """For every migration-defined column, the migration's type category must
    match the committed live snapshot. If a migration and live diverge (or the
    snapshot is stale), this fails — no silent drift."""
    mismatches = []
    for table in _MIGRATION_TABLES:
        for col, pgtype in MIGRATION_TYPES[table].items():
            live = SNAPSHOT[table].get(col)
            if live is None:
                mismatches.append(f"{table}.{col}: in migrations, absent from live snapshot")
            elif category(pgtype) != category(live):
                mismatches.append(f"{table}.{col}: migration {pgtype!r} vs live {live!r}")
    assert not mismatches, "migration/live type drift:\n" + "\n".join(mismatches)


def test_all_write_tables_have_a_type_map():
    for table in ["source_record", *_MIGRATION_TABLES]:
        assert COLUMN_TYPES.get(table), f"no type map for {table}"
