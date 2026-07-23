"""FTC enforcement connector — golden-file parse, pagination resume, idempotent
re-run, PDF raw-storage path, and verdict-language containment. No network, no live
DB (fake fetcher + fake writer + typed fake backend)."""
import re
from pathlib import Path

import pytest

from app.services.guardrail import check_guardrail
from app.services.ingestion import runner
from app.services.ingestion.base import RawItem, sha256_bytes
from app.services.ingestion.connectors import ftc as mod
from app.services.ingestion.connectors.ftc import (
    FTCConnector, LiveFTCWriter, RAW_SOURCE_FIELDS, enforcement_id_for,
    extract_listing_case_urls, extract_rss_case_links, is_privacy_case, parse_case,
)
from tests.ingestion_fakes import TypedFakeBackend

FIXDIR = Path(__file__).parent / "fixtures"
CASE_HTML = (FIXDIR / "ftc_case_sample.html").read_text()
CASE_URL = "https://www.ftc.gov/legal-library/browse/cases-proceedings/222-3002-rentgrow-inc-us-v"


# ── fakes ────────────────────────────────────────────────────────────

class FakeResp:
    def __init__(self, text=b"", ct="text/html", status=200):
        self._t = text if isinstance(text, str) else text.decode()
        self.content = text.encode() if isinstance(text, str) else text
        self.status_code = status
        self.headers = {"content-type": ct}

    @property
    def text(self):
        return self._t

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _listing_html(case_paths):
    links = "".join(
        f'<a href="/legal-library/browse/cases-proceedings/{p}">{p}</a>' for p in case_paths)
    return f"<html><body><div class='view'>{links}</div></body></html>"


class FakeFetcher:
    """Records requested URLs; serves listing pages + the golden case page. No net, no sleep."""

    def __init__(self, pages: dict[int, list[str]] | None = None, case_html=CASE_HTML,
                 pdf_bytes=b"%PDF-1.4 fake"):
        self.requested = []
        self._pages = pages if pages is not None else {0: ["222-3002-rentgrow-inc-us-v"]}
        self._case_html = case_html
        self._pdf = pdf_bytes

    def get(self, url):
        self.requested.append(url)
        if "search_api_fulltext" in url:                  # listing page
            m = re.search(r"[?&]page=(\d+)", url)
            page = int(m.group(1)) if m else 0
            return FakeResp(_listing_html(self._pages.get(page, [])))
        if url.lower().endswith(".pdf"):
            return FakeResp(self._pdf, ct="application/pdf")
        return FakeResp(self._case_html)                  # case page

    def get_bytes(self, url):
        r = self.get(url)
        return r.content, r.headers["content-type"]


class FakeWriter:
    def __init__(self, resolve=None):
        self.regulator_ensured = False
        self.pdfs = []
        self.enforcement = []
        self._resolve = resolve or {}

    def ensure_regulator(self):
        self.regulator_ensured = True

    def store_pdf(self, pdf_url):
        self.pdfs.append(pdf_url)
        return {"source_id": f"ftc:{pdf_url}", "path": "x", "sha256": "y"}

    def resolve_org(self, name):
        return self._resolve.get(name)

    def upsert_enforcement(self, row):
        self.enforcement.append(row)
        return True


def _run(connector):
    return runner.run(TypedFakeBackend(), connector, politeness_seconds=0)


# ── Golden-file parse ────────────────────────────────────────────────

def test_golden_case_parse():
    rec = parse_case(CASE_HTML, CASE_URL)
    assert rec is not None
    assert rec["title"] == "RentGrow, Inc., U.S. v."
    assert rec["respondents"] == ["RENTGROW, INC."]
    assert rec["matter_number"] == "2223002"              # digits only
    assert rec["civil_action_number"] == "1:26-cv-02415"
    assert rec["action_date"] == "2026-07-09"             # scoped: NOT the 2019 sidebar noise
    assert rec["case_status"] == "Pending"
    assert rec["penalty_usd"] == 2_250_000.0
    # FTC's OWN topic tags, verbatim (not mapped to Visentix domains)
    assert rec["topic_tags"] == [
        "Consumer Protection", "Bureau of Consumer Protection", "housing",
        "Fair Credit Reporting Act (FCRA)", "Privacy and Security", "Credit Reporting"]
    assert is_privacy_case(rec["topic_tags"]) is True
    # PDF links resolved to absolute FTC URLs
    assert rec["pdf_links"] == [
        "https://www.ftc.gov/system/files/ftc_gov/pdf/RentGrow-Complaint.pdf",
        "https://www.ftc.gov/system/files/ftc_gov/pdf/RentGrow-OrderMtn.pdf"]


def test_non_privacy_case_filtered():
    assert is_privacy_case(["Merger", "Competition", "Antitrust"]) is False
    assert is_privacy_case(["Data Security"]) is True


def test_listing_and_rss_link_extraction():
    html = _listing_html(["222-3002-rentgrow-inc-us-v", "closing-letters", "182-3000-acme-matter"])
    urls = extract_listing_case_urls(html)
    assert any("rentgrow" in u for u in urls)
    assert any("acme-matter" in u for u in urls)
    assert not any("closing-letters" in u for u in urls)      # excluded section
    rss = ("<rss><channel><item><link>https://www.ftc.gov/legal-library/browse/"
           "cases-proceedings/222-3002-rentgrow-inc-us-v</link></item>"
           "<item><link>https://www.ftc.gov/news-events/x</link></item></channel></rss>")
    assert extract_rss_case_links(rss) == [
        "https://www.ftc.gov/legal-library/browse/cases-proceedings/222-3002-rentgrow-inc-us-v"]


# ── Full run (fetch → parse → upsert) ────────────────────────────────

def test_full_run_writes_enforcement_and_pdfs():
    fetch, writer = FakeFetcher(), FakeWriter(resolve={"RENTGROW, INC.": "org-rentgrow"})
    conn = FTCConnector({"config": {}}, fetcher=fetch, writer=writer)
    res = _run(conn)
    assert res.outcome == "ok"
    assert writer.regulator_ensured is True
    assert len(writer.enforcement) == 1
    row = writer.enforcement[0]
    assert row["regulator_id"] == "FTC" and row["source_type"] == "FTC"
    assert row["enforcement_id"] == enforcement_id_for(CASE_URL)
    assert row["issue_tags"][4] == "Privacy and Security"    # verbatim
    assert row["matter_number"] == "2223002"
    assert row["organization_id"] == "org-rentgrow" and row["resolution_status"] == "resolved"
    assert row["source_id"] and row["source_id"].startswith("ftc:")   # case source_record lineage
    # both PDFs stored
    assert len(writer.pdfs) == 2
    assert conn.metrics["orgs_resolved"] == 1


def test_unresolved_when_no_org_match():
    fetch, writer = FakeFetcher(), FakeWriter(resolve={})     # no match
    conn = FTCConnector({"config": {}}, fetcher=fetch, writer=writer)
    _run(conn)
    row = writer.enforcement[0]
    assert row["organization_id"] is None and row["resolution_status"] == "unresolved"


# ── Pagination + resume ──────────────────────────────────────────────

def test_pagination_crawls_until_empty():
    pages = {0: ["222-3002-a-matter"], 1: ["182-3000-b-matter"], 2: []}   # page 2 empty → stop
    fetch = FakeFetcher(pages=pages)
    conn = FTCConnector({"config": {}}, fetcher=fetch, writer=FakeWriter(), max_pages=10)
    conn.fetch()
    assert conn.metrics["last_page_crawled"] == 2
    listing_hits = [u for u in fetch.requested if "search_api_fulltext" in u]
    assert any("page=0" in u for u in listing_hits) and any("page=2" in u for u in listing_hits)


def test_pagination_resume_start_page():
    pages = {5: ["222-3002-a-matter"], 6: []}
    fetch = FakeFetcher(pages=pages)
    conn = FTCConnector({"config": {}}, fetcher=fetch, writer=FakeWriter(), start_page=5, max_pages=10)
    conn.fetch()
    listing_hits = [u for u in fetch.requested if "search_api_fulltext" in u]
    assert all("page=0" not in u and "page=4" not in u for u in listing_hits)   # did NOT re-crawl
    assert any("page=5" in u for u in listing_hits)
    assert conn.metrics["last_page_crawled"] == 6


# ── Idempotency ──────────────────────────────────────────────────────

def test_idempotent_rerun_zero_new():
    be = TypedFakeBackend()
    f1, w1 = FakeFetcher(), FakeWriter()
    runner.run(be, FTCConnector({"config": {}}, fetcher=f1, writer=w1), politeness_seconds=0)
    assert len(w1.enforcement) == 1
    # second run over the SAME case HTML → framework skips the unchanged item
    f2, w2 = FakeFetcher(), FakeWriter()
    res2 = runner.run(be, FTCConnector({"config": {}}, fetcher=f2, writer=w2), politeness_seconds=0)
    assert res2.new == 0
    assert len(w2.enforcement) == 0                          # no duplicate enforcement write


# ── PDF raw-storage path convention ──────────────────────────────────

def test_pdf_raw_storage_path():
    be = TypedFakeBackend()
    writer = LiveFTCWriter(fetcher=FakeFetcher(pdf_bytes=b"%PDF-1.4 hello"), backend=be)
    out = writer.store_pdf("https://www.ftc.gov/system/files/ftc_gov/pdf/RentGrow-Complaint.pdf")
    sha = sha256_bytes(b"%PDF-1.4 hello")
    assert out["sha256"] == sha
    # raw-artifacts/ftc/{YYYY}/{MM}/{sha}.pdf
    assert re.fullmatch(rf"raw-artifacts/ftc/\d{{4}}/\d{{2}}/{sha}\.pdf", out["path"])
    assert out["path"] in be.raw_objects
    # a source_record (source_type='enforcement', tier 1) was created for the PDF
    sr = be.source_records[out["source_id"]]
    assert sr["source_type"] == "enforcement" and sr["family"] == "ftc"


# ── Verdict-language containment (guardrail) ─────────────────────────

def test_verdict_language_confined_to_raw_fields():
    rec = parse_case(CASE_HTML, CASE_URL)
    conn = FTCConnector({"config": {}}, fetcher=FakeFetcher(), writer=FakeWriter())
    row = conn._enforcement_row(rec, rec["respondents"][0], None)
    # RAW source fields MAY carry FTC verdict language; the fixture's summary does.
    assert "violated" in rec["summary"].lower()
    # Every DERIVED/structured text field must be banned-term-free.
    for field, val in row.items():
        if field in RAW_SOURCE_FIELDS or not isinstance(val, str):
            continue
        assert check_guardrail(val) == [], f"banned term leaked into derived field {field!r}: {val!r}"


def test_connector_is_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("ftc") is FTCConnector
