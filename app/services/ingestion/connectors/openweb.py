"""Open-web privacy-notice crawler (family `open_web`, raw folder `notices`).

Given a `crawl_target` work-list, finds and captures each company's CURRENT privacy
notice. Discovery renders the page (Playwright) so JS-only footers are seen, but the
SSRF-safe validation service (`intake.ssrf.validate_url`) and the existing intake
extraction/decomposition path are REUSED, not reimplemented.

Per target:
  robots + rate-limit → render homepage → find privacy links (≤2 hops, SSRF-validated)
  → render the notice → change-detection (unchanged hash ⇒ skip) → source_record
  (tier 1) + privacy_notice via the intake path (decompose) → crawl_target status.

Politeness: robots.txt honored; ≥1 request / 2s per domain; honest UA; a hard 4xx is
NEVER retried. Every non-capture outcome (no_notice / blocked / consent_wall / error)
is recorded on `crawl_target.status` + `status_reason` — never fabricated, never
silently skipped.

Rendering is behind a `Renderer` port so tests inject fixture HTML with no browser;
`PlaywrightRenderer` (lazy import) is the live renderer.
"""
from __future__ import annotations

import abc
import hashlib
import logging
import time
from datetime import date, datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.base import Connector, RawItem
from app.services.ingestion.connectors.edgar import normalize_domain, slugify
from app.services.intake.decompose import decompose
from app.services.intake.discover import PRIVACY_PATHS
from app.services.intake.extract import looks_like_privacy_policy
from app.services.intake.ssrf import SSRFError, validate_url

log = logging.getLogger(__name__)

UA = "Visentix-ingest/1.0 (+https://visentix.ai; contact ingestion@visentix.ai)"
_PRIVACY_LINK_TEXTS = {"privacy policy", "privacy notice", "privacy", "privacy statement",
                       "your privacy", "privacy & cookies", "privacy and cookies"}
_CONSENT_MARKERS = ("accept all cookies", "we value your privacy", "cookie preferences",
                    "manage consent", "before you continue", "enable javascript")
_MIN_NOTICE_LEN = 500


class RenderResult:
    __slots__ = ("html", "text", "status_code", "final_url")

    def __init__(self, html: str, text: str, status_code: int = 200, final_url: str = ""):
        self.html, self.text, self.status_code, self.final_url = html, text, status_code, final_url


# ── pure link discovery (unit-testable on committed fixtures) ────────

def find_privacy_links(html: str, base_url: str) -> list[str]:
    """Return SSRF-validated privacy-policy candidate URLs from a rendered page,
    matching footer/header links by href or link text (reuses the intake patterns)."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True).lower()
        href_l = href.lower()
        is_privacy = ("privacy" in href_l or text in _PRIVACY_LINK_TEXTS
                      or any(p in href_l for p in ("/privacy", "/legal/privacy")))
        if not is_privacy or href.startswith(("#", "mailto:", "javascript:")):
            continue
        full = href if href.startswith("http") else urljoin(base_url, href)
        if full in seen:
            continue
        seen.add(full)
        try:
            validate_url(full)          # SSRF rules still apply (task §2)
        except SSRFError:
            continue
        out.append(full)
    return out


def is_consent_wall(text: str) -> bool:
    """A short page dominated by cookie-consent / JS-required chrome — not a notice."""
    low = (text or "").lower()
    if len(low.strip()) >= _MIN_NOTICE_LEN:
        return False
    return any(m in low for m in _CONSENT_MARKERS) or len(low.strip()) < 120


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _natural_key(domain: str) -> str:
    return f"open_web:{domain}"


# ── renderer port ────────────────────────────────────────────────────

class Renderer(abc.ABC):
    @abc.abstractmethod
    def render(self, url: str) -> RenderResult:
        """Render `url` (SSRF-validated by the caller) → RenderResult. Raise on a hard
        4xx (the connector never retries those). Returned bytes are untrusted."""


class PlaywrightRenderer(Renderer):
    """Live renderer. Playwright is imported LAZILY so this module imports fine
    without it (tests use a fake renderer)."""

    def __init__(self, ua: str = UA, timeout_ms: int = 20000):
        self._ua, self._timeout = ua, timeout_ms
        self._browser = None
        self._pw = None

    def _ensure(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)

    def render(self, url: str) -> RenderResult:
        from app.services.intake.extract import _html_to_text  # reuse intake's extractor
        self._ensure()
        page = self._browser.new_page(user_agent=self._ua)
        try:
            resp = page.goto(url, timeout=self._timeout, wait_until="domcontentloaded")
            status = resp.status if resp else 0
            if 400 <= status < 500:
                raise HardHTTPError(status)          # never retried
            page.wait_for_timeout(1200)              # let JS footers render
            html = page.content()
            return RenderResult(html, _html_to_text(html), status, page.url)
        finally:
            page.close()

    def close(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()


class HardHTTPError(RuntimeError):
    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


# ── per-domain politeness (robots + rate limit) ─────────────────────

class DomainPolicy:
    def __init__(self, ua: str = UA, min_delay: float = 2.0):
        self._ua, self._min_delay = ua, min_delay
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last: dict[str, float] = {}

    def _rp(self, domain: str) -> RobotFileParser | None:
        if domain not in self._robots:
            rp = RobotFileParser()
            try:
                r = httpx.get(f"https://{domain}/robots.txt", headers={"User-Agent": self._ua},
                              timeout=15, follow_redirects=True)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:
                    rp.allow_all = True
            except Exception:  # noqa: BLE001 — unreadable robots → don't false-block
                rp.allow_all = True
            self._robots[domain] = rp
        return self._robots[domain]

    def allowed(self, url: str) -> bool:
        rp = self._rp(urlparse(url).netloc)
        try:
            return rp.can_fetch(self._ua, url)
        except Exception:  # noqa: BLE001
            return True

    def wait(self, domain: str):
        gap = self._min_delay - (time.monotonic() - self._last.get(domain, 0.0))
        if gap > 0:
            time.sleep(gap)
        self._last[domain] = time.monotonic()


# ── writer (crawl_target status + org resolve + notice persistence) ──

class OpenWebWriter:
    def __init__(self):
        self._url = settings.supabase_url

    def _h(self, **e):
        return {**get_service_headers(), **e}

    def _rest(self, p):
        return f"{self._url}/rest/v1/{p}"

    def load_targets(self, sector: str | None, limit: int | None) -> list[dict]:
        q = "crawl_target?select=*&status=in.(pending,unchanged,captured)&order=priority.asc"
        if sector:
            q += f'&sector=eq."{sector}"'
        if limit:
            q += f"&limit={limit}"
        r = httpx.get(self._rest(q), headers=self._h(), timeout=30)
        return r.json() if r.status_code < 300 else []

    def update_status(self, target_id: str, status: str, reason: str | None = None,
                      content_hash: str | None = None, notice_url: str | None = None) -> None:
        patch = {"status": status, "status_reason": reason,
                 "last_crawled_at": datetime.now(timezone.utc).isoformat()}
        if content_hash is not None:
            patch["content_hash"] = content_hash
        if notice_url is not None:
            patch["notice_url"] = notice_url
        httpx.patch(self._rest(f"crawl_target?target_id=eq.{target_id}"),
                    headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                    json=patch, timeout=30)

    def resolve_or_create_org(self, domain: str, sector: str, source_id: str) -> tuple[str, bool]:
        r = httpx.get(self._rest(
            f'organization_alias?select=organization_id&alias_type=eq.domain&value=eq."{domain}"&limit=1'),
            headers=self._h(), timeout=30)
        rows = r.json() if r.status_code < 300 else []
        if rows:
            return rows[0]["organization_id"], False
        r = httpx.get(self._rest(
            f'organization?select=organization_id&or=(domain.eq."{domain}",domain.eq."www.{domain}")&limit=1'),
            headers=self._h(), timeout=30)
        rows = r.json() if r.status_code < 300 else []
        if rows:
            return rows[0]["organization_id"], False
        base = slugify(domain)
        for attempt in range(4):
            payload = {"name": domain, "slug": base if attempt == 0 else f"{base}-ow-{attempt}",
                       "domain": domain, "industry": sector or "unknown", "entity_type": "peer",
                       "tenant_id": None, "origin": "open_web"}
            resp = httpx.post(self._rest("organization"),
                              headers=self._h(**{"Content-Type": "application/json",
                                                 "Prefer": "return=representation"}), json=payload, timeout=30)
            if resp.status_code < 300:
                oid = resp.json()[0]["organization_id"]
                httpx.post(self._rest("organization_alias?on_conflict=alias_type,value"),
                           headers=self._h(**{"Content-Type": "application/json",
                                              "Prefer": "resolution=ignore-duplicates,return=minimal"}),
                           json=[{"organization_id": oid, "alias_type": "domain", "value": domain,
                                  "match_confidence": 1.0, "source_record_id": source_id}], timeout=30)
                return oid, True
            if resp.status_code == 409 and "slug" in (resp.text or ""):
                continue
            raise RuntimeError(f"organization insert failed: HTTP {resp.status_code}")
        raise RuntimeError("organization insert failed: slug collisions exhausted")

    def create_notice_with_body(self, org_id: str, rec: dict) -> str:
        from uuid import uuid4
        notice = rec["notice"]
        cats = {c.category for c in notice.clauses}
        mean_conf = (sum(c.nlp_confidence for c in notice.clauses) / len(notice.clauses)
                     if notice.clauses else 0.0)
        notice_id = str(uuid4())
        payload = {"notice_id": notice_id, "organization_id": org_id, "notice_type": "open_web",
                   "url": rec["notice_url"], "effective_date": str(date.today()),
                   "retrieval_date": str(date.today()), "content_hash": rec["content_hash"],
                   "version_id": 0, "jurisdiction_scope": ["US"], "storage_path": "",
                   "extraction_confidence": round(mean_conf, 4),
                   "ai_disclosure_presence": "ai_automated_decisions" in cats,
                   "tracking_disclosure_presence": "tracking_cookies" in cats,
                   "consumer_rights_presence": "consumer_rights" in cats,
                   "retention_disclosure_presence": "retention" in cats,
                   "cross_border_indicator": "cross_border" in cats,
                   "sensitive_data_indicator": "sensitive_data" in cats}
        r = httpx.post(self._rest("privacy_notice"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=payload, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"privacy_notice insert failed: HTTP {r.status_code}")
        sections = [{"section_id": s.section_id, "notice_id": notice_id, "title": s.title,
                     "section_type": s.section_type, "sequence": s.sequence,
                     "extracted_text": s.text[:10000]} for s in notice.sections]
        if sections:
            httpx.post(self._rest("notice_section"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=sections, timeout=60)
        clauses = [{"clause_id": c.clause_id, "section_id": c.section_id, "raw_text": c.raw_text[:5000],
                    "normalized_text": c.normalized_text[:5000], "category": c.category,
                    "ambiguity_score": c.ambiguity_score, "readability_score": c.readability_score,
                    "nlp_confidence": c.nlp_confidence, "domain_id": c.domain_id or None,
                    "clause_type": c.clause_type or None, "transparency_score": c.transparency_score}
                   for c in notice.clauses]
        if clauses:
            httpx.post(self._rest("disclosure_clause"),
                       headers=self._h(**{"Content-Type": "application/json", "Prefer": "return=minimal"}),
                       json=clauses, timeout=60)
        return notice_id


# ── the connector ────────────────────────────────────────────────────

class OpenWebConnector(Connector):
    family = "open_web"
    raw_folder = "notices"                       # schema §2 family↔folder mapping
    source_type = "notice"
    parser_version = "open-web-crawler-v1"
    parser_description = "Open-web privacy-notice crawl (Playwright render) → source_record + privacy_notice"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, *, sector: str | None = None,
                 limit: int | None = None, targets: list[dict] | None = None,
                 renderer: Renderer | None = None, writer: OpenWebWriter | None = None,
                 policy: DomainPolicy | None = None, max_hops: int = 2):
        self._sector = sector
        self._limit = limit
        self._targets_in = targets
        self._renderer = renderer
        self._writer = writer
        self._policy = policy or DomainPolicy(min_delay=settings.ingestion_politeness_seconds or 2.0)
        self._max_hops = max_hops
        self._captured: dict[str, dict] = {}     # domain -> capture payload
        # metrics
        self._crawled = 0
        self._captured_n = 0
        self._status_counts: dict[str, int] = {}
        self._samples: list[dict] = []

    def _w(self) -> OpenWebWriter:
        if self._writer is None:
            self._writer = OpenWebWriter()
        return self._writer

    def _r(self) -> Renderer:
        if self._renderer is None:
            self._renderer = PlaywrightRenderer()
        return self._renderer

    def _mark(self, target, status, reason=None, content_hash=None, notice_url=None):
        self._status_counts[status] = self._status_counts.get(status, 0) + 1
        self._w().update_status(target["target_id"], status, reason, content_hash, notice_url)

    # ── fetch: crawl each target, capture notices ────────────────────
    def fetch(self) -> list[RawItem]:
        targets = self._targets_in if self._targets_in is not None else \
            self._w().load_targets(self._sector, self._limit)
        items: list[RawItem] = []
        for target in targets:
            if self._limit is not None and self._crawled >= self._limit:
                break
            self._crawled += 1
            item = self._crawl_one(target)
            if item is not None:
                items.append(item)
        log.info("open_web fetch: %d captured of %d crawled (%s)",
                 len(items), self._crawled, self._status_counts)
        return items

    def _crawl_one(self, target: dict) -> RawItem | None:
        domain = normalize_domain(target.get("domain"))
        if not domain:
            self._mark(target, "error", "no domain")
            return None
        base = f"https://{domain}"
        # SSRF + robots
        try:
            validate_url(base)
        except SSRFError as e:
            self._mark(target, "blocked", f"ssrf:{e}")
            return None
        if not self._policy.allowed(base):
            self._mark(target, "blocked", "robots_disallow")
            return None

        # discover + render the notice (homepage + ≤max_hops); reuse the render result
        notice_url, res, kind, reason = self._discover(base, domain)
        if kind == "consent_wall":
            self._mark(target, "consent_wall", "cookie/consent or JS wall", notice_url=notice_url)
            return None
        if kind != "notice":
            self._mark(target, "no_notice", reason)
            return None

        content_hash = _sha(res.text)
        if content_hash == (target.get("content_hash") or ""):
            self._mark(target, "unchanged", "content hash unchanged", content_hash, notice_url)
            return None                                  # change-detection skip

        self._captured[domain] = {"target": target, "text": res.text, "notice_url": notice_url,
                                  "content_hash": content_hash, "sector": target.get("sector")}
        return RawItem(data=res.html.encode("utf-8"), content_type="text/html",
                       source_url=notice_url, natural_key=_natural_key(domain),
                       title=f"{domain} privacy notice", jurisdiction="US")

    def _discover(self, base: str, domain: str):
        """Render homepage, follow privacy links ≤ max_hops. Returns
        (notice_url, render_result, kind, reason) where kind ∈ {'notice','consent_wall',None}.
        A hard 4xx on a candidate is skipped, never retried."""
        try:
            self._policy.wait(domain)
            home = self._r().render(base)
        except HardHTTPError as e:
            return None, None, None, f"homepage_http_{e.status}"
        except Exception as e:  # noqa: BLE001
            return None, None, None, f"homepage_{type(e).__name__}"
        # homepage footer/header links, then intake's known privacy paths
        candidates = find_privacy_links(home.html, base)
        for path in PRIVACY_PATHS:
            full = urljoin(base, path)
            if full not in candidates:
                candidates.append(full)
        consent_fallback = None
        for cand in candidates[:self._max_hops]:          # follow at most max_hops
            try:
                validate_url(cand)
                self._policy.wait(domain)
                res = self._r().render(cand)
            except (HardHTTPError, SSRFError):
                continue                                   # 4xx never retried; SSRF blocked
            except Exception:  # noqa: BLE001
                continue
            if is_consent_wall(res.text):
                consent_fallback = (res.final_url or cand, res)
                continue                                   # keep looking for a real notice
            if looks_like_privacy_policy(res.text):
                return res.final_url or cand, res, "notice", None
        if consent_fallback:
            return consent_fallback[0], consent_fallback[1], "consent_wall", None
        return None, None, None, "no privacy link found"

    def parse(self, item: RawItem) -> list[dict]:
        domain = item.natural_key.split(":", 1)[-1]
        cap = self._captured[domain]
        notice = decompose(cap["text"])
        return [{"domain": domain, "sector": cap["sector"], "notice_url": cap["notice_url"],
                 "content_hash": cap["content_hash"], "target": cap["target"], "notice": notice}]

    def upsert(self, records: list[dict]) -> None:
        w = self._w()
        for rec in records:
            org_id, _created = w.resolve_or_create_org(rec["domain"], rec["sector"],
                                                       rec["source_record_id"])
            w.create_notice_with_body(org_id, rec)
            self._captured_n += 1
            self._status_counts["captured"] = self._status_counts.get("captured", 0) + 1
            w.update_status(rec["target"]["target_id"], "captured", None,
                            rec["content_hash"], rec["notice_url"])
            if len(self._samples) < 5:
                self._samples.append({"domain": rec["domain"], "notice_url": rec["notice_url"],
                                      "clauses": len(rec["notice"].clauses)})

    def record_counts(self) -> dict:
        return {"seen": self._crawled, "new": self._captured_n, "changed": 0,
                "skipped": self._crawled - self._captured_n}

    @property
    def metrics(self) -> dict:
        return {"crawled": self._crawled, "captured": self._captured_n,
                "status_counts": dict(self._status_counts), "samples": list(self._samples)}
