"""HHS OCR breach connector — golden-file parse, idempotency, malformed rows,
and the zero-enforcement-writes guarantee. No network, no live DB (fake backend
+ fake security_event writer)."""
import inspect
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.ingestion import runner
from app.services.ingestion.base import Backend, RawItem
from app.services.ingestion.connectors import hhs_ocr as mod
from app.services.ingestion.connectors.hhs_ocr import HHSOCRConnector

FIXTURE = (Path(__file__).parent / "fixtures" / "hhs_ocr_sample.csv").read_bytes()
HEADER = FIXTURE.decode().splitlines()[0]
ROWS = FIXTURE.decode().splitlines()[1:]


# ── Fakes ───────────────────────────────────────────────────────────

class FakeBackend(Backend):
    def __init__(self):
        self.source_records, self.source_versions = {}, {}
        self.raw_objects, self.parser_versions, self.runs = {}, {}, {}

    def find_source_record(self, sid): return self.source_records.get(sid)
    def latest_version_hash(self, sid):
        v = self.source_versions.get(sid) or []
        return v[-1]["hash"] if v else None
    def version_count(self, sid): return len(self.source_versions.get(sid) or [])
    def store_raw(self, path, data, ct):
        if path in self.raw_objects: return "reused"
        self.raw_objects[path] = data; return "created"
    def create_source_record(self, row): self.source_records[row["source_id"]] = row
    def create_source_version(self, row): self.source_versions.setdefault(row["source_id"], []).append(row)
    def register_parser_version(self, family, version, desc):
        self.parser_versions.setdefault((family, version), f"pv-{family}-{version}")
        return self.parser_versions[(family, version)]
    def create_ingestion_run(self, row):
        rid = str(uuid4()); self.runs[rid] = dict(row); return rid
    def finish_ingestion_run(self, rid, updates): self.runs[rid].update(updates)


class FakeEventWriter:
    """Mimics security_event upsert with ON CONFLICT (event_id) DO NOTHING."""
    def __init__(self): self.rows: dict[str, dict] = {}
    def __call__(self, rows):
        n = 0
        for r in rows:
            assert "parser_version_id" not in r          # not a security_event column
            if r["event_id"] not in self.rows:
                self.rows[r["event_id"]] = r; n += 1
        return n


def _make_csv(rows: list[str]) -> bytes:
    return ("\n".join([HEADER, *rows]) + "\n").encode()


def _run(csv_bytes: bytes, backend: FakeBackend, writer: FakeEventWriter):
    conn = HHSOCRConnector({"config": {"csv_url": "http://fixture/hhs.csv"}}, event_writer=writer)
    conn.fetch = lambda: [RawItem(csv_bytes, "text/csv", "http://fixture/hhs.csv",
                                  "hhs_ocr_breach_export_500plus", title="t")]
    return runner.run(backend, conn, politeness_seconds=0)


# ── Golden-file parse ───────────────────────────────────────────────

def test_golden_file_parse():
    be, w = FakeBackend(), FakeEventWriter()
    res = _run(FIXTURE, be, w)
    assert res.seen == 5 and res.new == 5 and res.malformed == 1
    assert res.outcome == "partial"                      # malformed rows → partial
    # AC-HHS_OCR: security_event count == records_seen
    assert len(w.rows) == list(be.runs.values())[0]["records_seen"] == 5

    by_entity = {r["entity_name_raw"]: r for r in w.rows.values()}
    acme = by_entity["Acme Health System"]
    assert acme["entity_type"] == "Healthcare Provider"
    assert acme["state"] == "CA"
    assert acme["individuals_affected"] == 50000
    assert acme["submission_date"] == "2026-03-15"
    assert acme["breach_type"] == "Hacking/IT Incident"
    assert acme["information_location"] == "Network Server"
    assert acme["extraction_confidence"] == 1.0
    # quoted comma field parsed correctly
    assert by_entity["Gamma Insurance Group"]["information_location"] == "Electronic Medical Record, Network Server"
    # every row: unresolved, no org matching, lineage present
    for r in w.rows.values():
        assert r["organization_id"] is None
        assert r["resolution_status"] == "unresolved"
        assert r["source_record_id"] and r["capture_date"]


def test_malformed_row_not_dropped():
    be, w = FakeBackend(), FakeEventWriter()
    res = _run(FIXTURE, be, w)
    bad = [r for r in w.rows.values() if r["extraction_confidence"] < 1.0]
    assert len(bad) == 1
    assert bad[0]["description"].startswith("[MALFORMED ROW]")
    assert "unknown" in bad[0]["description"]             # raw row preserved
    assert bad[0]["individuals_affected"] is None
    # counted in the run summary
    assert "malformed" in list(be.runs.values())[0]["error_summary"].lower()


# ── Idempotency ─────────────────────────────────────────────────────

def test_idempotent_rerun_zero_new():
    be, w = FakeBackend(), FakeEventWriter()
    _run(FIXTURE, be, w)
    res2 = _run(FIXTURE, be, w)                           # identical CSV
    assert res2.new == 0                                  # framework skips unchanged item
    assert len(w.rows) == 5                               # no new security_events


def test_changed_csv_five_new_rows():
    be, w = FakeBackend(), FakeEventWriter()
    base = ROWS[:4]                                       # 4 well-formed
    _run(_make_csv(base), be, w)
    assert len(w.rows) == 4
    extra = [
        "New Alpha Health,Healthcare Provider,OR,900,04/01/2026,Loss,Other Portable Electronic Device,Lost drive.",
        "New Bravo Care,Health Plan,NV,15000,04/02/2026,Hacking/IT Incident,Email,BEC incident.",
        "New Charlie Group,Business Associate,AZ,220,04/03/2026,Theft,Desktop Computer,Office theft.",
        "New Delta LLC,Healthcare Provider,CO,4300,04/04/2026,Unauthorized Access/Disclosure,Paper/Films,Misdirected mail.",
        "New Echo Systems,Healthcare Clearing House,UT,88000,04/05/2026,Hacking/IT Incident,Network Server,Server intrusion.",
    ]
    res = _run(_make_csv(base + extra), be, w)            # 9 rows, 5 new
    assert res.new == 5
    assert len(w.rows) == 9


# ── Never touches enforcement_record ────────────────────────────────

def test_zero_enforcement_record_writes():
    # static: the connector writes to security_event and NEVER to enforcement_record
    src = inspect.getsource(mod)
    assert "rest/v1/enforcement_record" not in src
    assert "rest/v1/security_event" in src
    # behavioral: the only write sink is the security_event event_writer
    be, w = FakeBackend(), FakeEventWriter()
    _run(FIXTURE, be, w)
    assert len(w.rows) == 5                               # all writes went to security_event


def test_connector_is_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("hhs_ocr") is HHSOCRConnector
