"""CPPA newsroom connector — golden parse, enforcement-vs-announcement routing,
idempotency, and verdict containment. No network, no live DB."""
from pathlib import Path

from app.services.guardrail import check_guardrail
from app.services.ingestion import runner
from app.services.ingestion.base import RawItem
from app.services.ingestion.connectors.cppa import (
    CPPAConnector, _company_from_title, parse_cppa_detail, parse_cppa_listing,
)
from app.services.ingestion.connectors._enforcement import RAW_SOURCE_FIELDS
from tests.ingestion_fakes import FakeEnforcementWriter
from tests.ingestion_fakes import TypedFakeBackend as FakeBackend

FIX = Path(__file__).parent / "fixtures"
LISTING = (FIX / "cppa_newsroom_sample.html").read_text()
ENF_DETAIL = (FIX / "cppa_enforcement_detail.html").read_text()
ANN_DETAIL = (FIX / "cppa_announcement_detail.html").read_text()
ENF_URL = "https://privacy.ca.gov/2026/07/cppa-settles-datavault/"
ANN_URL = "https://privacy.ca.gov/2026/06/cppa-board-appointment/"


class _Resp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


class FakeFetcher:
    def __init__(self):
        self.pages = {
            "https://privacy.ca.gov/about-us/newsroom/": LISTING,
            ENF_URL: ENF_DETAIL, ANN_URL: ANN_DETAIL,
        }

    def get(self, url):
        return _Resp(self.pages.get(url, "<html></html>"))


def _conn(writer, **kw):
    return CPPAConnector({"config": {"base_url": "https://privacy.ca.gov/about-us/newsroom/",
                                     "archive_only": True}},
                         fetcher=FakeFetcher(), writer=writer, include_archive=False, **kw)


# ── Golden parse ─────────────────────────────────────────────────────

def test_listing_parse():
    items = parse_cppa_listing(LISTING)
    assert len(items) == 2
    enf = [i for i in items if "datavault" in i["url"].lower()][0]
    assert enf["date"] == "2026-07-15"
    assert enf["categories"] == ["enforcement"]        # CPPA category, verbatim


def test_detail_parse_pdf():
    d = parse_cppa_detail(ENF_DETAIL)
    assert d["pdf_links"] == ["https://privacy.ca.gov/wp-content/uploads/2026/07/DataVault-Order.pdf"]
    assert _company_from_title("California Privacy Protection Agency Settles with DataVault Inc. for $1.2 Million") \
        == "DataVault Inc."


# ── Routing: enforcement vs announcement ─────────────────────────────

def test_enforcement_vs_announcement_routing():
    w = FakeEnforcementWriter(resolve={"DataVault Inc.": "org-dv"})
    conn = _conn(w)
    res = runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert res.outcome == "ok"
    # exactly one enforcement_record (DataVault); the appointment is source_record only
    assert len(w.enforcement) == 1
    row = w.enforcement[0]
    assert row["regulator_id"] == "CPPA" and row["source_type"] == "CPPA"
    assert row["target_company"] == "DataVault Inc."
    assert row["penalty_usd"] == 1_200_000.0
    assert row["issue_tags"] == ["enforcement"]        # verbatim CPPA category
    assert row["organization_id"] == "org-dv" and row["resolution_status"] == "resolved"
    assert w.pdfs == ["https://privacy.ca.gov/wp-content/uploads/2026/07/DataVault-Order.pdf"]
    assert conn.metrics == {"items": 2, "enforcement_written": 1, "announcements_only": 1,
                            "pdfs_stored": 1, "orgs_resolved": 1}


# ── Idempotency ──────────────────────────────────────────────────────

def test_idempotent_rerun():
    be = FakeBackend()
    w1 = FakeEnforcementWriter()
    runner.run(be, CPPAConnector({"config": {"archive_only": True}}, fetcher=FakeFetcher(),
                                 writer=w1, include_archive=False), politeness_seconds=0)
    assert len(w1.enforcement) == 1
    w2 = FakeEnforcementWriter()
    res2 = runner.run(be, CPPAConnector({"config": {"archive_only": True}}, fetcher=FakeFetcher(),
                                        writer=w2, include_archive=False), politeness_seconds=0)
    assert res2.new == 0 and len(w2.enforcement) == 0   # unchanged pages skipped


# ── Verdict containment ──────────────────────────────────────────────

def test_verdict_language_confined_to_raw():
    conn = _conn(FakeEnforcementWriter())
    conn.parse(RawItem(ENF_DETAIL.encode(), "text/html", ENF_URL, "datavault"))
    conn._meta[ENF_URL] = {"title": "CPPA Settles with DataVault Inc.", "date": "2026-07-15",
                           "categories": ["enforcement"]}
    rec = conn.parse(RawItem(ENF_DETAIL.encode(), "text/html", ENF_URL, "datavault"))[0]
    row = conn._enforcement_row(rec, None)
    assert "violated" in row["summary"].lower()          # RAW keeps verdict language
    for field, val in row.items():
        if field in RAW_SOURCE_FIELDS or not isinstance(val, str):
            continue
        assert check_guardrail(val) == [], f"banned term leaked into derived field {field!r}"


def test_connector_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("cppa") is CPPAConnector
