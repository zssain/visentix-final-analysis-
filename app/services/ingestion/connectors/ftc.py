"""FTC enforcement connector (family `ftc`).

Scrapes the FTC Legal Library cases-proceedings listing filtered to
privacy/data-security topics, plus its press-release RSS for incremental updates,
and writes `enforcement_record` rows + per-PDF `source_record` rows on the F02
connector framework.

Politeness & compliance (task + AGENTS.md §3):
- Honest User-Agent identifying Visentix; robots.txt honored (the FTC robots.txt
  sets Crawl-delay: 5 and Disallows `items_per_page`/`combine` params — this
  connector paginates with `?page=N`/`search_api_fulltext` only and waits >= the
  crawl-delay between requests).
- Fetched HTML/PDF bytes are UNTRUSTED: parsed with BeautifulSoup, never eval'd.

Boundaries this connector RESPECTS:
- issue_tags = the FTC's OWN topic tags, VERBATIM. It does NOT map them to Visentix
  domains — that crosswalk (`ftc_topic_domain_map`) is an empty, expert-owned
  scaffold (migration 0026). domains/violation_types/laws_cited are left NULL.
- Verdict language ("violation", …) from FTC text is confined to RAW source fields
  (summary, tags, respondent names, remedy excerpt). No DERIVED field carries it
  (asserted by the guardrail containment test).
- It creates NO obligation rows — order-derived obligations need expert review
  (TODO: F02 v2).
- The FTC regulator row's priority/topic-weight fields are NEVER written here
  (computed later by a versioned job).
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.db import get_service_headers
from app.services.ingestion.base import Connector, RawItem
from app.services.ingestion.entity_resolution import build_name_index
# Reuse the baseline enforcement parser's penalty extractor (AC-G5: reuse, don't reimplement).
from scripts.ingest.ingest_enforcement import extract_penalty

log = logging.getLogger(__name__)

FTC_BASE = "https://www.ftc.gov"
FTC_LISTING_PATH = "/legal-library/browse/cases-proceedings"
FTC_RSS_DEFAULT = "https://www.ftc.gov/feeds/press-release-consumer-protection.xml"
UA = "Visentix-ingest/1.0 (+https://visentix.ai; contact ingestion@visentix.ai)"

# Case-listing hrefs to exclude (non-case sections under the same path prefix).
HREF_EXCLUDE = {"closing-letters", "public-statements", "advisory-opinions",
                "banned-debt-collectors", "adjudicative-proceedings"}

# A case qualifies as privacy/data-security if any of its FTC topic tags matches.
_PRIVACY_TAG_HINTS = ("privacy", "data security", "biometric", "health data")

# enforcement_record columns this connector writes (guards against stray keys).
ENFORCEMENT_COLUMNS = {
    "enforcement_id", "regulator_id", "source_id", "source_type", "jurisdiction",
    "target_company", "target_industry", "entity_name", "entity_industry",
    "issue_tags", "penalty_usd", "fine_amount_usd", "action_date", "summary",
    "remedy", "remedies", "official_url", "source_name", "content_hash", "verified",
    "matter_number", "civil_action_number", "retrieved_at",
    "organization_id", "resolution_status",
}
# Fields whose values are copied VERBATIM from FTC source text (verdict language
# allowed). Every OTHER text field the connector writes must be banned-term-free.
RAW_SOURCE_FIELDS = {
    "target_company", "entity_name", "issue_tags", "summary", "remedy", "remedies",
    "official_url", "source_name",
}


# ── polite, robots-aware fetcher ─────────────────────────────────────

class PoliteFetcher:
    """Honest-UA HTTP getter that honors robots.txt allow-rules and crawl-delay,
    and spaces requests by at least `min_delay` seconds."""

    def __init__(self, base: str = FTC_BASE, ua: str = UA, min_delay: float = 2.0):
        self._ua = ua
        self._min_delay = min_delay
        self._last = 0.0
        self._rp = RobotFileParser()
        # Fetch robots.txt with our HONEST UA via httpx — FTC's CDN 403s urllib's
        # default UA, which would make RobotFileParser disallow-all (a false block).
        try:
            r = httpx.get(urljoin(base, "/robots.txt"),
                          headers={"User-Agent": ua}, timeout=20, follow_redirects=True)
            if r.status_code == 200:
                self._rp.parse(r.text.splitlines())
            else:
                self._rp.allow_all = True             # unreadable → don't false-block
            cd = self._rp.crawl_delay(ua) or self._rp.crawl_delay("*")
            if cd:
                self._min_delay = max(self._min_delay, float(cd))
        except Exception as e:  # noqa: BLE001 — if robots unreadable, stay polite but don't block
            log.warning("robots.txt unreadable (%s); using min_delay=%.1fs", type(e).__name__, self._min_delay)
            self._rp.allow_all = True

    def allowed(self, url: str) -> bool:
        try:
            return self._rp.can_fetch(self._ua, url)
        except Exception:  # noqa: BLE001
            return True

    def _pace(self):
        wait = self._min_delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        self._pace()
        return httpx.get(url, headers={"User-Agent": self._ua}, timeout=30, follow_redirects=True)

    def get_bytes(self, url: str) -> tuple[bytes, str]:
        r = self.get(url)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "")


# ── HTML parsing (pure, unit-testable) ───────────────────────────────

def _field(article, name: str):
    return article.find("div", class_=lambda c: c and f"field--name-{name}" in " ".join(
        c if isinstance(c, list) else [c]))


def _field_text(article, name: str) -> str | None:
    el = _field(article, name)
    if not el:
        return None
    item = el.find("div", class_="field__item") or el
    txt = item.get_text(" ", strip=True)
    return txt or None


def is_privacy_case(tags: list[str]) -> bool:
    low = " | ".join(t.lower() for t in tags)
    return any(h in low for h in _PRIVACY_TAG_HINTS)


def _respondents(long_title: str | None, h1: str | None) -> list[str]:
    """Best-effort respondent name(s) from the case title. Deterministic, no fuzz."""
    if long_title:
        # "... Plaintiff, v. RENTGROW, INC., a Delaware Corporation, Defendant"
        m = re.search(r"\bv\.?\s+(.+?),?\s+(?:a\b.*)?Defendants?\.?$", long_title, re.I)
        if m:
            return [re.sub(r",?\s+a\s+.*$", "", m.group(1)).strip().strip(",").strip()]
    if h1:
        # "RentGrow, Inc., U.S. v." / "In the Matter of Acme, Inc."
        base = re.split(r",?\s+(?:U\.?S\.?|FTC|United States)\b", h1)[0]
        base = re.sub(r"^In the Matter of\s+", "", base, flags=re.I)
        return [base.strip(" ,.")]
    return []


def parse_case(html: str, url: str) -> dict | None:
    """Parse an FTC case page into a normalized record. Case fields are read from
    the `article.node--type-case` region(s) — a case renders as MORE THAN ONE such
    article (one carries matter/tags/date, another the documents) and the page <h1>
    sits outside them, so we search across all case articles (which also keeps
    sidebar/blog date-noise out). Returns None if the page isn't a case node."""
    soup = BeautifulSoup(html, "html.parser")
    arts = soup.find_all("article", class_=lambda c: c and "node--type-case" in " ".join(
        c if isinstance(c, list) else [c]))
    if not arts:
        return None

    def field_text(name: str) -> str | None:
        for a in arts:
            t = _field_text(a, name)
            if t:
                return t
        return None

    def field_divs(name: str):
        out = []
        for a in arts:
            out += a.find_all("div", class_=lambda c: c and f"field--name-{name}" in " ".join(
                c if isinstance(c, list) else [c]))
        return out

    h1 = soup.find("h1")                                  # page title lives outside the articles
    title = h1.get_text(strip=True) if h1 else None
    long_title = field_text("field-long-title")

    matter_raw = field_text("field-matter-number")
    matter_number = None
    if matter_raw:
        digits = re.sub(r"\D", "", matter_raw)           # "FTC Matter/File Number 222 3002" -> "2223002"
        matter_number = digits or None

    civil_raw = field_text("field-civil-action-number")
    civil_action = None
    if civil_raw:
        m = re.search(r"([0-9]{1,2}:[0-9]{2}-[a-z]{1,4}-[0-9]{3,6})", civil_raw, re.I)
        civil_action = m.group(1) if m else civil_raw.replace("Civil Action Number", "").strip() or None

    # tags: the FTC's own topic tags, VERBATIM (anchor texts)
    topic_tags = []
    for d in field_divs("field-tags-view"):
        topic_tags = [a.get_text(strip=True) for a in d.find_all("a") if a.get_text(strip=True)]
        if topic_tags:
            break

    # action date: first time[datetime] within the case articles (sidebar dates excluded)
    action_date = None
    for d in field_divs("field-date"):
        t = d.find("time")
        if t and t.get("datetime"):
            action_date = t["datetime"][:10]
            break

    # PDF document links
    pdf_links, seen_pdf = [], set()
    for d in field_divs("field-media-document"):
        for a in d.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf") or "/pdf/" in href.lower():
                full = href if href.startswith("http") else urljoin(FTC_BASE, href)
                if full not in seen_pdf:
                    seen_pdf.add(full)
                    pdf_links.append(full)

    body_el = None
    for a in arts:
        body_el = _field(a, "body")
        if body_el:
            break
    body = body_el.get_text(" ", strip=True) if body_el else ""
    summary = body[:1000] if body else (title or "")

    # remedy: a RAW verbatim sentence mentioning remedy language (kept as source text).
    remedy = None
    for sent in re.split(r"(?<=[.!?])\s+", body):
        if re.search(r"\b(required to|must|order requires|prohibited from|pay|establish|delete)\b", sent, re.I):
            remedy = sent.strip()[:500]
            break

    penalty = extract_penalty(f"{title or ''} {body}")

    return {
        "case_url": url,
        "natural_key": _case_natural_key(url),
        "title": title,
        "long_title": long_title,
        "respondents": _respondents(long_title, title),
        "matter_number": matter_number,
        "civil_action_number": civil_action,
        "enforcement_type": field_text("field-enforcement-type"),
        "case_status": field_text("field-case-status"),
        "action_date": action_date,
        "topic_tags": topic_tags,
        "pdf_links": pdf_links,
        "penalty_usd": penalty,
        "summary": summary,
        "remedy": remedy,
    }


def _case_natural_key(url: str) -> str:
    """Stable identity for a case = its listing slug."""
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or path


def enforcement_id_for(url: str) -> str:
    """Deterministic enforcement_id (uuid5 of the case URL) — idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"FTC:{url}"))


def extract_listing_case_urls(html: str) -> list[str]:
    """Case-detail URLs from a listing page (excludes non-case sections)."""
    soup = BeautifulSoup(html, "html.parser")
    urls, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if FTC_LISTING_PATH + "/" not in href:
            continue
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        if any(ex in href for ex in HREF_EXCLUDE):
            continue
        full = href if href.startswith("http") else urljoin(FTC_BASE, href)
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def extract_rss_case_links(xml: str) -> list[str]:
    """Case-proceeding links referenced from an RSS feed (incremental mode)."""
    soup = BeautifulSoup(xml, "xml")
    links = []
    for item in soup.find_all("item"):
        for tag in item.find_all(["link", "guid"]):
            href = (tag.get_text() or "").strip()
            if FTC_LISTING_PATH + "/" in href:
                links.append(href)
    return links


# ── writer port (PDF source_records + org resolution + enforcement upsert) ──

class FTCWriter:
    """Side-effect port. LiveFTCWriter hits Supabase; tests inject a fake."""

    def ensure_regulator(self) -> None: ...
    def store_pdf(self, pdf_url: str) -> dict | None: ...
    def resolve_org(self, name: str) -> str | None: ...
    def upsert_enforcement(self, row: dict) -> bool: ...


class LiveFTCWriter(FTCWriter):
    def __init__(self, fetcher: PoliteFetcher | None = None, backend=None):
        self._url = settings.supabase_url
        self._fetcher = fetcher or PoliteFetcher()
        self._backend = backend                           # injectable (tests); else SupabaseBackend
        self._index = None                                # lazy org-name index

    def _h(self, **extra):
        return {**get_service_headers(), **extra}

    def _rest(self, p):
        return f"{self._url}/rest/v1/{p}"

    def ensure_regulator(self) -> None:
        """Create the FTC regulator row if absent. NEVER touches priority/topic
        weight fields (computed later by a versioned job)."""
        r = httpx.get(self._rest("regulator?select=regulator_id&regulator_id=eq.FTC&limit=1"),
                      headers=self._h(), timeout=20)
        if r.status_code < 300 and r.json():
            return
        httpx.post(self._rest("regulator"),
                   headers=self._h(**{"Content-Type": "application/json",
                                      "Prefer": "resolution=ignore-duplicates,return=minimal"}),
                   json={"regulator_id": "FTC", "name": "Federal Trade Commission",
                         "jurisdiction": "US-FED", "authority": "FTC Act"}, timeout=20)

    def store_pdf(self, pdf_url: str) -> dict | None:
        """Download a PDF (polite) → raw-artifacts + a source_record
        (source_type='enforcement', tier 1). Idempotent by content hash."""
        from app.services.ingestion.base import (
            derive_source_id, ext_for_content_type, raw_artifact_path, sha256_bytes,
        )
        if self._backend is None:
            from app.services.ingestion.backend import SupabaseBackend
            self._backend = SupabaseBackend()
        be = self._backend
        try:
            data, ctype = self._fetcher.get_bytes(pdf_url)
        except Exception as e:  # noqa: BLE001 — a missing PDF must not sink the case
            log.warning("PDF fetch failed %s: %s", pdf_url, type(e).__name__)
            return None
        sha = sha256_bytes(data)
        source_id = derive_source_id("ftc", f"pdf:{pdf_url}")
        path = raw_artifact_path("ftc", sha, ext_for_content_type(ctype or "application/pdf"))
        be.store_raw(path, data, ctype or "application/pdf")
        if be.find_source_record(source_id) is None:
            now = datetime.now(timezone.utc).isoformat()
            be.create_source_record({
                "source_id": source_id, "family": "ftc", "source_type": "enforcement",
                "url": pdf_url, "title": pdf_url.rsplit("/", 1)[-1], "jurisdiction": "US-FED",
                "sha256": sha, "storage_path": path, "extraction_confidence": 1.0,
                "retrieval_ts": now, "version_id": 1,
            })
            be.create_source_version({"version_id": f"{source_id}#1", "source_id": source_id,
                                      "hash": sha, "captured_at": now, "diff_summary": "initial capture"})
        return {"source_id": source_id, "path": path, "sha256": sha}

    def _load_index(self):
        if self._index is not None:
            return self._index
        pairs = []
        for path in ("organization_alias?select=value,organization_id&alias_type=eq.legal_name",
                     "organization?select=name,organization_id"):
            rows, off = [], 0
            while True:
                r = httpx.get(self._rest(path), headers=self._h(**{"Range": f"{off}-{off+999}"}), timeout=60)
                b = r.json() if r.status_code < 300 else []
                rows.extend(b)
                if len(b) < 1000:
                    break
                off += 1000
            key = "value" if "alias" in path else "name"
            pairs += [(x[key], x["organization_id"]) for x in rows]
        self._index = build_name_index(pairs)
        return self._index

    def resolve_org(self, name: str) -> str | None:
        return self._load_index().lookup(name)

    def upsert_enforcement(self, row: dict) -> bool:
        payload = {k: v for k, v in row.items() if k in ENFORCEMENT_COLUMNS}
        r = httpx.post(self._rest("enforcement_record?on_conflict=enforcement_id"),
                       headers=self._h(**{"Content-Type": "application/json",
                                          "Prefer": "resolution=merge-duplicates,return=minimal"}),
                       json=[payload], timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"enforcement_record upsert failed: HTTP {r.status_code}")
        return True


# ── the connector ────────────────────────────────────────────────────

class FTCConnector(Connector):
    family = "ftc"
    source_type = "enforcement"
    parser_version = "ftc-legal-library-v1"
    parser_description = "FTC Legal Library cases-proceedings (privacy/data-security) -> enforcement_record"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, *,
                 limit: int | None = None, start_page: int = 0, max_pages: int = 40,
                 mode: str = "full", search_term: str = "privacy",
                 fetcher: PoliteFetcher | None = None, writer: FTCWriter | None = None):
        cfg = (registry_row or {}).get("config") or {}
        self._limit = limit
        self._start_page = start_page
        self._max_pages = max_pages
        self._mode = mode
        self._search_term = search_term
        self._rss_url = cfg.get("rss_url") or FTC_RSS_DEFAULT
        self._fetcher = fetcher                            # constructed lazily (avoids network in tests)
        self._writer = writer
        # metrics
        self._cases = 0
        self._enforcement_written = 0
        self._pdfs_stored = 0
        self._orgs_resolved = 0
        self._last_page_crawled = start_page - 1
        self._records: list[dict] = []                     # dry-run preview

    def _f(self) -> PoliteFetcher:
        if self._fetcher is None:
            self._fetcher = PoliteFetcher()
        return self._fetcher

    def _w(self) -> FTCWriter:
        if self._writer is None:
            self._writer = LiveFTCWriter(self._f())
        return self._writer

    # ── fetch: discover + download privacy case pages ────────────────
    def fetch(self) -> list[RawItem]:
        case_urls = (self._rss_case_urls() if self._mode == "incremental"
                     else self._listing_case_urls())
        items: list[RawItem] = []
        for url in case_urls:
            if self._limit is not None and len(items) >= self._limit:
                break
            try:
                r = self._f().get(url)
                if r.status_code != 200:
                    continue
            except Exception as e:  # noqa: BLE001 — skip a bad case page, keep crawling
                log.warning("case fetch failed %s: %s", url, type(e).__name__)
                continue
            html = r.text
            rec = parse_case(html, url)
            if rec is None or not is_privacy_case(rec["topic_tags"]):
                continue                                   # not a privacy/data-security case
            items.append(RawItem(
                data=html.encode("utf-8"), content_type="text/html",
                source_url=url, natural_key=rec["natural_key"],
                title=rec["title"] or url, jurisdiction="US-FED"))
        log.info("ftc fetch: %d privacy cases (mode=%s, pages %d..%d, limit=%s)",
                 len(items), self._mode, self._start_page, self._last_page_crawled, self._limit)
        return items

    def _listing_case_urls(self) -> list[str]:
        """Paginate the privacy-filtered listing (robots-safe: page + search_api_fulltext,
        NO items_per_page). Supports resume via start_page; records last page crawled."""
        urls, seen = [], set()
        for page in range(self._start_page, self._start_page + self._max_pages):
            listing = (f"{FTC_BASE}{FTC_LISTING_PATH}"
                       f"?search_api_fulltext={self._search_term}&page={page}")
            try:
                r = self._f().get(listing)
                if r.status_code != 200:
                    break
            except Exception as e:  # noqa: BLE001
                log.warning("listing page %d failed: %s", page, type(e).__name__)
                break
            self._last_page_crawled = page
            page_urls = [u for u in extract_listing_case_urls(r.text) if u not in seen]
            for u in page_urls:
                seen.add(u)
            urls.extend(page_urls)
            if not page_urls:
                break                                      # end of results
            if self._limit is not None and len(urls) >= self._limit:
                break
        return urls

    def _rss_case_urls(self) -> list[str]:
        try:
            r = self._f().get(self._rss_url)
            links = extract_rss_case_links(r.text)
        except Exception as e:  # noqa: BLE001
            log.warning("RSS fetch failed: %s", type(e).__name__)
            return []
        # normalize to absolute + de-dup
        out, seen = [], set()
        for h in links:
            full = h if h.startswith("http") else urljoin(FTC_BASE, h)
            if full not in seen:
                seen.add(full)
                out.append(full)
        return out

    # ── parse: one case record ───────────────────────────────────────
    def parse(self, item: RawItem) -> list[dict]:
        rec = parse_case(item.data.decode("utf-8", "replace"), item.source_url)
        if rec is None:
            raise ValueError(f"ftc: not a case page ({item.source_url})")
        self._records.append(rec)
        return [rec]

    # ── upsert: PDFs -> source_records, resolve org, write enforcement ──
    def upsert(self, records: list[dict]) -> None:
        w = self._w()
        w.ensure_regulator()
        for rec in records:
            self._cases += 1
            for pdf in rec["pdf_links"]:
                if w.store_pdf(pdf):
                    self._pdfs_stored += 1
            respondent = rec["respondents"][0] if rec["respondents"] else (rec["title"] or "")
            org_id = w.resolve_org(respondent) if respondent else None
            if org_id:
                self._orgs_resolved += 1
            row = self._enforcement_row(rec, respondent, org_id)
            if w.upsert_enforcement(row):
                self._enforcement_written += 1

    def _enforcement_row(self, rec: dict, respondent: str, org_id: str | None) -> dict:
        return {
            "enforcement_id": enforcement_id_for(rec["case_url"]),
            "regulator_id": "FTC",
            "source_id": rec.get("source_record_id"),      # case source_record (framework-attached)
            "source_type": "FTC",
            "jurisdiction": "US-FED",
            "target_company": respondent or None,          # RAW (from title)
            "entity_name": respondent or None,             # RAW
            "issue_tags": rec["topic_tags"],               # RAW — FTC's own tags, verbatim
            "penalty_usd": rec["penalty_usd"],
            "fine_amount_usd": rec["penalty_usd"],
            "action_date": rec["action_date"],
            "summary": rec["summary"],                     # RAW — FTC body excerpt
            "remedy": rec["remedy"],                       # RAW — verbatim sentence
            "official_url": rec["case_url"],
            "source_name": "FTC Legal Library",
            "content_hash": None,                          # set by framework lineage if needed
            "verified": True,
            "matter_number": rec["matter_number"],
            "civil_action_number": rec["civil_action_number"],
            # domains / violation_types / laws_cited intentionally NULL:
            # FTC-topic -> domain mapping is expert-owned (ftc_topic_domain_map).
            # TODO(F02 v2): obligation rows are NOT created here — order-derived
            # obligations need expert review.
            "organization_id": org_id,
            "resolution_status": "resolved" if org_id else "unresolved",
        }

    def record_counts(self) -> dict:
        return {"seen": self._cases, "new": self._enforcement_written,
                "changed": 0, "skipped": 0}

    @property
    def metrics(self) -> dict:
        return {"cases": self._cases, "enforcement_written": self._enforcement_written,
                "pdfs_stored": self._pdfs_stored, "orgs_resolved": self._orgs_resolved,
                "last_page_crawled": self._last_page_crawled}

    @property
    def parsed_records(self) -> list[dict]:
        return list(self._records)
