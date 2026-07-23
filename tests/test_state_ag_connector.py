"""State AG connector — generic/heuristic parsing with honest confidence,
privacy-enforcement routing, per-site failure isolation, idempotency, containment."""
from pathlib import Path

from app.services.guardrail import check_guardrail
from app.services.ingestion import runner
from app.services.ingestion.connectors._enforcement import RAW_SOURCE_FIELDS
from app.services.ingestion.connectors.state_ag import (
    StateAGConnector, parse_generic_list,
)
from tests.ingestion_fakes import FakeEnforcementWriter
from tests.ingestion_fakes import TypedFakeBackend as FakeBackend

FIX = Path(__file__).parent / "fixtures"
GENERIC = (FIX / "ag_generic_sample.html").read_text()
WORDPRESS = (FIX / "ag_wordpress_sample.html").read_text()


class _Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


class FakeFetcher:
    """Serves per-URL HTML; a URL mapped to None raises (simulates a broken site)."""

    def __init__(self, pages):
        self.pages = pages

    def get(self, url):
        v = self.pages.get(url)
        if v is None:
            raise RuntimeError("boom")
        return _Resp(v)


def _sites(*specs):
    return [{"state": s, "url": u, "parser_hint": h} for s, u, h in specs]


# ── Parsing + honest confidence ──────────────────────────────────────

def test_generic_structured_confidence():
    cards = parse_generic_list(GENERIC, "https://ag.example.gov/")
    assert len(cards) == 2
    assert all(c["confidence"] == 1.0 for c in cards)     # <article>+<time> → structured
    assert cards[0]["date"] == "2026-05-20"


def test_wordpress_heuristic_confidence():
    cards = parse_generic_list(WORDPRESS, "https://ag.example.gov/")
    assert len(cards) == 2
    assert all(c["confidence"] == 0.6 for c in cards)     # no <article>/<time> → heuristic
    assert cards[0]["date"] == "2026-04-10"


# ── Routing: privacy-enforcement vs everything else ──────────────────

def test_privacy_enforcement_routing():
    pages = {"https://ca.gov/news": GENERIC}
    w = FakeEnforcementWriter(resolve={"AdTracker LLC": "org-adt"})
    conn = StateAGConnector({"config": {}}, sites=_sites(("CA", "https://ca.gov/news", "generic_list")),
                            fetcher=FakeFetcher(pages), writer=w)
    res = runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert res.outcome in ("ok", "partial")
    # only the CCPA settlement becomes enforcement_record; the road-safety item does not
    assert len(w.enforcement) == 1
    row = w.enforcement[0]
    assert row["regulator_id"] == "CA-AG" and row["source_type"] == "STATE_AG"
    assert row["target_company"] == "AdTracker LLC"
    assert row["organization_id"] == "org-adt"
    assert "CA-AG" in w.regulators
    assert conn.metrics["announcements_only"] == 1


def test_low_confidence_flagged_not_dropped():
    pages = {"https://co.gov/pr": WORDPRESS}
    w = FakeEnforcementWriter()
    conn = StateAGConnector({"config": {}}, sites=_sites(("CO", "https://co.gov/pr", "wordpress_list")),
                            fetcher=FakeFetcher(pages), writer=w)
    res = runner.run(FakeBackend(), conn, politeness_seconds=0)
    # both wordpress items are low-confidence → stored + flagged, never dropped
    assert conn.metrics["items"] == 2 and conn.metrics["low_confidence"] == 2
    assert any("low-confidence" in wn for wn in res.warnings)
    assert res.outcome == "partial"                       # flagged → partial
    assert len(w.enforcement) == 1                        # DataBroker settlement still routed


# ── Per-site failure isolation ───────────────────────────────────────

def test_per_site_failure_isolation():
    pages = {"https://ok1.gov": GENERIC, "https://broken.gov": None, "https://ok2.gov": WORDPRESS}
    w = FakeEnforcementWriter()
    conn = StateAGConnector(
        {"config": {}},
        sites=_sites(("CA", "https://ok1.gov", "generic_list"),
                     ("XX", "https://broken.gov", "generic_list"),
                     ("CO", "https://ok2.gov", "wordpress_list")),
        fetcher=FakeFetcher(pages), writer=w)
    res = runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert res.outcome == "partial"                       # one broken site
    assert conn.metrics["site_failures"] == 1
    assert any("XX" in wn and "failed" in wn for wn in res.warnings)
    # the two working sites still produced enforcement rows (AdTracker + DataBroker)
    assert len(w.enforcement) == 2


# ── Idempotency ──────────────────────────────────────────────────────

def test_idempotent_rerun():
    pages = {"https://ca.gov/news": GENERIC}
    be = FakeBackend()
    s = _sites(("CA", "https://ca.gov/news", "generic_list"))
    w1 = FakeEnforcementWriter()
    runner.run(be, StateAGConnector({"config": {}}, sites=s, fetcher=FakeFetcher(pages), writer=w1),
               politeness_seconds=0)
    assert len(w1.enforcement) == 1
    w2 = FakeEnforcementWriter()
    res2 = runner.run(be, StateAGConnector({"config": {}}, sites=s, fetcher=FakeFetcher(pages), writer=w2),
                      politeness_seconds=0)
    assert res2.new == 0 and len(w2.enforcement) == 0     # unchanged cards skipped


# ── Verdict containment + raw folder ─────────────────────────────────

def test_verdict_containment_and_raw_folder():
    assert StateAGConnector.raw_folder == "ag_actions"    # schema §2 family↔folder
    cards = parse_generic_list(GENERIC, "https://ag.example.gov/")
    conn = StateAGConnector({"config": {}}, sites=[], writer=FakeEnforcementWriter())
    rec = {"url": cards[0]["url"], "state": "CA", "title": cards[0]["title"],
           "date": cards[0]["date"], "body": cards[0]["body"], "confidence": 1.0,
           "is_privacy_enforcement": True, "signals": ["settlement"], "penalty_usd": 500000.0,
           "company": "AdTracker LLC"}
    row = conn._enforcement_row(rec, "CA-AG", None)
    assert "violations" in rec["body"].lower()            # RAW keeps verdict language
    for field, val in row.items():
        if field in RAW_SOURCE_FIELDS or not isinstance(val, str):
            continue
        assert check_guardrail(val) == [], f"banned term leaked into derived field {field!r}"


def test_connector_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("state_ag") is StateAGConnector
