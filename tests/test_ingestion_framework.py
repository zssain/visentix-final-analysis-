"""F02 connector framework — lifecycle proven against an in-memory fake backend.

No live DB: the framework depends on the Backend port, so these are fast and
deterministic. Proves idempotency, change-detection/versioning, per-item failure
isolation, dry-run writes-nothing, and the raw-artifact path convention.
"""
import re
from uuid import uuid4

import pytest

from app.services.ingestion.base import (
    Backend, Connector, RawItem, derive_source_id, ext_for_content_type, raw_artifact_path,
)
from app.services.ingestion import runner


# ── In-memory Backend + fake Connector ──────────────────────────────

class FakeBackend(Backend):
    def __init__(self):
        self.source_records: dict[str, dict] = {}
        self.source_versions: dict[str, list[dict]] = {}
        self.raw_objects: dict[str, bytes] = {}
        self.parser_versions: dict[tuple, str] = {}
        self.runs: dict[str, dict] = {}

    def find_source_record(self, source_id):
        return self.source_records.get(source_id)

    def latest_version_hash(self, source_id):
        vs = self.source_versions.get(source_id) or []
        return vs[-1]["hash"] if vs else None

    def version_count(self, source_id):
        return len(self.source_versions.get(source_id) or [])

    def store_raw(self, path, data, content_type):
        if path in self.raw_objects:
            return "reused"                     # never overwrite
        self.raw_objects[path] = data
        return "created"

    def create_source_record(self, row):
        self.source_records[row["source_id"]] = row

    def create_source_version(self, row):
        self.source_versions.setdefault(row["source_id"], []).append(row)

    def register_parser_version(self, family, version, description):
        key = (family, version)
        self.parser_versions.setdefault(key, f"pv-{family}-{version}")
        return self.parser_versions[key]

    def create_ingestion_run(self, row):
        rid = str(uuid4())
        self.runs[rid] = {**row}
        return rid

    def finish_ingestion_run(self, run_id, updates):
        self.runs[run_id].update(updates)


class FakeConnector(Connector):
    family = "faketest"
    source_type = "dataset"
    parser_version = "v1"
    parser_description = "fake test parser"
    default_extraction_confidence = 0.9

    def __init__(self, items, fail_keys=()):
        self._items = items
        self._fail = set(fail_keys)
        self.upserted: list[dict] = []

    def fetch(self):
        return self._items

    def parse(self, item):
        if item.natural_key in self._fail:
            raise ValueError("parse boom")
        return [{"body_len": len(item.data), "natural_key": item.natural_key}]

    def upsert(self, records):
        self.upserted.extend(records)


def _item(key: str, body: str) -> RawItem:
    return RawItem(data=body.encode("utf-8"), content_type="application/json",
                   source_url=f"https://config.example/{key}", natural_key=key, title=key)


# ── Pure helpers ────────────────────────────────────────────────────

def test_raw_artifact_path_convention():
    import datetime
    p = raw_artifact_path("hhs_ocr", "abc123", "html", when=datetime.date(2026, 3, 9))
    assert p == "raw-artifacts/hhs_ocr/2026/03/abc123.html"
    assert ext_for_content_type("application/pdf") == "pdf"
    assert ext_for_content_type("text/html; charset=utf-8") == "html"


# ── Lifecycle ───────────────────────────────────────────────────────

def test_first_run_ingests_all_new():
    be = FakeBackend()
    conn = FakeConnector([_item("k1", "v1"), _item("k2", "v1")])
    res = runner.run(be, conn, politeness_seconds=0)
    assert (res.outcome, res.new, res.changed, res.skipped) == ("ok", 2, 0, 0)
    assert len(be.source_records) == 2
    # every parsed record carries the required lineage
    for r in conn.upserted:
        assert r["source_record_id"] and r["capture_date"]
        assert r["parser_version_id"] == "pv-faketest-v1"
        assert r["extraction_confidence"] == 0.9


def test_idempotent_rerun_zero_new():
    be = FakeBackend()
    items = [_item("k1", "v1"), _item("k2", "v1")]
    runner.run(be, FakeConnector(items), politeness_seconds=0)
    res2 = runner.run(be, FakeConnector(items), politeness_seconds=0)
    assert (res2.new, res2.changed, res2.skipped) == (0, 0, 2)   # unchanged → skipped
    # no duplicate source_records or extra versions
    assert len(be.source_records) == 2
    assert all(len(v) == 1 for v in be.source_versions.values())


def test_changed_content_makes_new_source_version():
    be = FakeBackend()
    runner.run(be, FakeConnector([_item("k1", "v1")]), politeness_seconds=0)
    sid = derive_source_id("faketest", "k1")
    assert be.version_count(sid) == 1
    # same natural key, different bytes → CHANGED + a new source_version
    res = runner.run(be, FakeConnector([_item("k1", "v2-different")]), politeness_seconds=0)
    assert (res.new, res.changed, res.skipped) == (0, 1, 0)
    assert be.version_count(sid) == 2
    assert be.source_versions[sid][-1]["hash"] != be.source_versions[sid][0]["hash"]
    assert len(be.source_records) == 1                          # not duplicated


def test_per_item_failure_is_partial_others_ingested():
    be = FakeBackend()
    conn = FakeConnector([_item("ok1", "a"), _item("bad", "b"), _item("ok2", "c")],
                         fail_keys=["bad"])
    res = runner.run(be, conn, politeness_seconds=0)
    assert res.outcome == "partial"
    assert res.seen == 3 and res.new == 2 and len(res.errors) == 1
    assert res.errors[0]["natural_key"] == "bad"
    # the two good items were ingested despite the failure
    assert len(be.source_records) == 2
    assert {r["natural_key"] for r in conn.upserted} == {"ok1", "ok2"}
    # the run was recorded with a partial outcome
    assert list(be.runs.values())[0]["outcome"] == "partial"


def test_dry_run_writes_nothing():
    be = FakeBackend()
    conn = FakeConnector([_item("k1", "v1"), _item("k2", "v1")])
    res = runner.run(be, conn, dry_run=True, politeness_seconds=0)
    assert res.new == 2                                          # diff counted
    # ...but NOTHING was written
    assert be.source_records == {} and be.source_versions == {}
    assert be.raw_objects == {} and be.runs == {} and be.parser_versions == {}
    assert conn.upserted == []


def test_raw_object_stored_at_convention_path():
    be = FakeBackend()
    runner.run(be, FakeConnector([_item("k1", "hello")]), politeness_seconds=0)
    assert len(be.raw_objects) == 1
    path = next(iter(be.raw_objects))
    assert re.fullmatch(r"raw-artifacts/faketest/\d{4}/\d{2}/[0-9a-f]{64}\.json", path)
