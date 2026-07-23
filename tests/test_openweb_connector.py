"""Open-web crawler — link discovery (fixtures), robots respect, per-domain rate
limit, hash-skip change detection, and crawl_target status transitions. No browser,
no network, no live DB (fake renderer + fake writer + fake policy)."""
import time
from pathlib import Path
from urllib.robotparser import RobotFileParser

import pytest
from bs4 import BeautifulSoup

from app.services.ingestion import runner
from app.services.ingestion.connectors import openweb as mod
from app.services.ingestion.connectors.openweb import (
    DomainPolicy, HardHTTPError, OpenWebConnector, RenderResult, find_privacy_links,
    is_consent_wall,
)
from tests.ingestion_fakes import TypedFakeBackend as FakeBackend

FIX = Path(__file__).parent / "fixtures"
HOMEPAGE = (FIX / "openweb_homepage_footer.html").read_text()
NESTED = (FIX / "openweb_nested_legal.html").read_text()
NO_NOTICE = (FIX / "openweb_no_notice.html").read_text()
NOTICE = (FIX / "openweb_privacy_notice.html").read_text()
NOTICE_TEXT = BeautifulSoup(NOTICE, "html.parser").get_text(" ", strip=True)


@pytest.fixture(autouse=True)
def _no_ssrf_dns(monkeypatch):
    # bypass real DNS/SSRF resolution in unit tests (validation logic tested elsewhere)
    monkeypatch.setattr(mod, "validate_url", lambda u: u)


# ── Link discovery (committed fixtures) ──────────────────────────────

def test_find_footer_link():
    assert find_privacy_links(HOMEPAGE, "https://acme.com") == ["https://acme.com/privacy"]


def test_find_nested_legal_link():
    assert find_privacy_links(NESTED, "https://beta.com") == \
        ["https://beta.com/company/legal/privacy-policy"]


def test_find_no_notice():
    assert find_privacy_links(NO_NOTICE, "https://gamma.com") == []


def test_consent_wall_detection():
    assert is_consent_wall("We value your privacy. Accept all cookies to continue.") is True
    assert is_consent_wall("short") is True
    assert is_consent_wall(NOTICE_TEXT) is False


# ── robots.txt respect ───────────────────────────────────────────────

def test_robots_respect():
    pol = DomainPolicy(ua="Visentix-ingest/1.0", min_delay=0)
    rp = RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /privacy"])
    pol._robots["blocked.com"] = rp                        # inject parsed robots (no network)
    assert pol.allowed("https://blocked.com/privacy") is False
    assert pol.allowed("https://blocked.com/") is True


# ── per-domain rate limit ────────────────────────────────────────────

def test_rate_limit_spacing():
    pol = DomainPolicy(min_delay=0.15)
    t0 = time.monotonic()
    pol.wait("a.com"); pol.wait("a.com")                   # 2 requests same domain
    assert time.monotonic() - t0 >= 0.15                   # spaced by >= min_delay
    # a different domain is not throttled by a.com's clock
    t1 = time.monotonic(); pol.wait("b.com")
    assert time.monotonic() - t1 < 0.15


# ── fakes for full-crawl tests ───────────────────────────────────────

class FakeRenderer:
    """Serves fixtures by URL; unmapped URLs raise HardHTTPError(404). Counts calls."""

    def __init__(self, pages, hard=None):
        self.pages = pages                                 # url -> (html, text)
        self.hard = hard or {}                             # url -> status (hard 4xx)
        self.calls = []

    def render(self, url):
        self.calls.append(url)
        if url in self.hard:
            raise HardHTTPError(self.hard[url])
        if url not in self.pages:
            raise HardHTTPError(404)
        html, text = self.pages[url]
        return RenderResult(html, text, 200, url)


class FakePolicy:
    def __init__(self, allowed=True):
        self._allowed = allowed
        self.waits = []

    def allowed(self, url):
        return self._allowed

    def wait(self, domain):
        self.waits.append(domain)


class FakeWriter:
    def __init__(self, existing=None):
        self.existing = existing or {}
        self.statuses = {}
        self.notices = []
        self.orgs = []
        self._seq = 0

    def load_targets(self, sector, limit):
        return []

    def update_status(self, target_id, status, reason=None, content_hash=None, notice_url=None):
        self.statuses[target_id] = {"status": status, "reason": reason,
                                    "content_hash": content_hash, "notice_url": notice_url}

    def resolve_or_create_org(self, domain, sector, source_id):
        if domain in self.existing:
            return self.existing[domain], False
        self._seq += 1
        oid = f"org-{self._seq}"
        self.orgs.append({"id": oid, "domain": domain, "origin": "open_web", "source_id": source_id})
        return oid, True

    def create_notice_with_body(self, org_id, rec):
        self.notices.append({"org_id": org_id, "domain": rec["domain"],
                             "notice_url": rec["notice_url"], "clauses": len(rec["notice"].clauses)})
        return f"notice-{len(self.notices)}"


def _target(domain, sector="retail", content_hash=None):
    return {"target_id": f"ct:{domain}", "domain": domain, "sector": sector,
            "content_hash": content_hash, "organization_id": None}


def _conn(targets, renderer, writer, policy=None, **kw):
    return OpenWebConnector(targets=targets, renderer=renderer, writer=writer,
                            policy=policy or FakePolicy(), **kw)


def _acme_renderer(notice_text=NOTICE_TEXT):
    return FakeRenderer({"https://acme.com": (HOMEPAGE, "Acme home"),
                         "https://acme.com/privacy": (NOTICE, notice_text)})


# ── Status transitions ───────────────────────────────────────────────

def test_capture_happy_path():
    be = FakeBackend(); w = FakeWriter()
    conn = _conn([_target("acme.com")], _acme_renderer(), w)
    res = runner.run(be, conn, politeness_seconds=0)
    assert res.outcome == "ok"
    assert w.statuses["ct:acme.com"]["status"] == "captured"
    assert len(w.notices) == 1 and w.notices[0]["clauses"] > 0
    # tier-1 source_record stored under the open_web → notices folder
    sr = list(be.source_records.values())[0]
    assert sr["family"] == "open_web" and sr["source_type"] == "notice"
    assert list(be.raw_objects)[0].startswith("raw-artifacts/notices/")
    assert conn.metrics["captured"] == 1


def test_no_notice_status():
    w = FakeWriter()
    r = FakeRenderer({"https://gamma.com": (NO_NOTICE, "Gamma home")})   # /privacy etc. 404
    conn = _conn([_target("gamma.com")], r, w)
    runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert w.statuses["ct:gamma.com"]["status"] == "no_notice"
    assert not w.notices


def test_blocked_by_robots():
    w = FakeWriter()
    conn = _conn([_target("acme.com")], _acme_renderer(), w, policy=FakePolicy(allowed=False))
    runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert w.statuses["ct:acme.com"]["status"] == "blocked"
    assert "robots" in w.statuses["ct:acme.com"]["reason"]


def test_consent_wall_status():
    w = FakeWriter()
    r = FakeRenderer({"https://acme.com": (HOMEPAGE, "Acme home"),
                      "https://acme.com/privacy": ("<html></html>", "We value your privacy. Accept all cookies.")})
    conn = _conn([_target("acme.com")], r, w)
    runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert w.statuses["ct:acme.com"]["status"] == "consent_wall"


def test_hard_4xx_not_retried():
    w = FakeWriter()
    r = FakeRenderer({"https://acme.com": (HOMEPAGE, "Acme home")},
                     hard={"https://acme.com/privacy": 403})
    conn = _conn([_target("acme.com")], r, w)
    runner.run(FakeBackend(), conn, politeness_seconds=0)
    # 403 during discovery → no notice found; the 403 URL was requested at most once (no retry)
    assert r.calls.count("https://acme.com/privacy") <= 1
    assert w.statuses["ct:acme.com"]["status"] in ("no_notice", "error")


# ── Hash-skip change detection ───────────────────────────────────────

def test_hash_skip_unchanged():
    from app.services.ingestion.connectors.openweb import _sha
    unchanged = _target("acme.com", content_hash=_sha(NOTICE_TEXT))
    w = FakeWriter()
    conn = _conn([unchanged], _acme_renderer(), w)
    res = runner.run(FakeBackend(), conn, politeness_seconds=0)
    assert w.statuses["ct:acme.com"]["status"] == "unchanged"
    assert not w.notices and res.new == 0                  # captured nothing new


def test_connector_registered():
    from app.services.ingestion.registry import CONNECTORS
    assert CONNECTORS.get("open_web") is OpenWebConnector
