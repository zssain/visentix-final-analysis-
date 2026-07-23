"""CPPA (California Privacy Protection Agency) newsroom connector (family `cppa`).

Primary source: https://privacy.ca.gov/about-us/newsroom/ (announcements moved here
2026-01-26). Also does ONE archival pass of the legacy cppa.ca.gov/announcements for
history (guarded by `archive_only` in registry config).

Routing:
- ENFORCEMENT-relevant items (decisions, settlements, fines, subpoena actions,
  sweeps) → an `enforcement_record` row (regulator CPPA) + any order/decision PDF
  stored as a tier-1 `source_record`.
- Non-enforcement news (appointments, advisories, legislation) → the announcement
  page is captured as a `source_record` ONLY (source_type='regulator_announcement'),
  with NO enforcement_record.

Same rules as the FTC connector: verdict language confined to RAW source fields;
additive org resolution; idempotent enforcement upsert on enforcement_id.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.ingestion.base import Connector, RawItem
from app.services.ingestion.connectors._enforcement import (
    LiveEnforcementWriter, RAW_SOURCE_FIELDS, enforcement_id_for, is_enforcement,
)
from app.services.ingestion.connectors.ftc import PoliteFetcher
from scripts.ingest.ingest_enforcement import extract_penalty

log = logging.getLogger(__name__)

NEWSROOM_DEFAULT = "https://privacy.ca.gov/about-us/newsroom/"
ARCHIVE_DEFAULT = "https://cppa.ca.gov/announcements/"
_BASE = "https://privacy.ca.gov"


def _classes(el) -> list[str]:
    c = el.get("class")
    return c if isinstance(c, list) else ([c] if c else [])


def parse_cppa_listing(html: str, base: str = _BASE) -> list[dict]:
    """Newsroom listing → [{title, url, date, categories}]. Divi/WordPress:
    article.et_pb_post, h2.entry-title>a, span.published, category-* article classes."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for art in soup.find_all("article"):
        a = art.find(["h2", "h3", "h1"], class_=lambda c: c and "entry-title" in " ".join(
            c if isinstance(c, list) else [c]))
        link = a.find("a", href=True) if a else None
        if not link:
            continue
        url = link["href"] if link["href"].startswith("http") else urljoin(base, link["href"])
        # only real post permalinks (privacy.ca.gov/YYYY/MM/slug or /announcements/...)
        if not re.search(r"/20\d\d/\d\d/|/announcements?/.+", url) or url in seen:
            continue
        seen.add(url)
        pub = art.find(class_="published") or art.find("time")
        date = _parse_date(pub.get_text(strip=True) if pub else "") or _date_from_url(url)
        cats = [c.replace("category-", "") for c in _classes(art)
                if c.startswith("category-")]
        out.append({"title": link.get_text(strip=True), "url": url,
                    "date": date, "categories": cats})
    return out


def parse_cppa_detail(html: str) -> dict:
    """Detail page → {body, pdf_links}. Body scoped to the post content region."""
    soup = BeautifulSoup(html, "html.parser")
    content = (soup.find("div", class_=lambda c: c and "entry-content" in " ".join(
        c if isinstance(c, list) else [c]))
        or soup.find("article") or soup)
    body = content.get_text(" ", strip=True)
    pdfs, seen = [], set()
    for a in content.find_all("a", href=True):         # scoped to content (skip nav/footer PDFs)
        if a["href"].lower().split("?")[0].endswith(".pdf"):
            full = a["href"] if a["href"].startswith("http") else urljoin(_BASE, a["href"])
            if full not in seen:
                seen.add(full)
                pdfs.append(full)
    return {"body": body, "pdf_links": pdfs}


_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def _parse_date(s: str) -> str | None:
    s = (s or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _date_from_url(url: str) -> str | None:
    m = re.search(r"/(20\d\d)/(\d\d)/", url)
    return f"{m.group(1)}-{m.group(2)}-01" if m else None


def _company_from_title(title: str) -> str | None:
    """Best-effort respondent from an enforcement headline (deterministic patterns).
    Trigger matched case-insensitively; the name is taken as the following
    Capitalized run (so we don't capture lowercase filler like 'the company')."""
    trig = re.search(r"(?:settle[sd]?\s+with|action\s+against|against|orders?|fines?|"
                     r"reaches?\s+(?:agreement|settlement)\s+with)\s+", title, re.I)
    if not trig:
        return None
    n = re.match(r"([A-Z][\w&.,'\-]*(?:\s+[A-Z][\w&.,'\-]*){0,5})", title[trig.end():])
    return (re.sub(r"[,\s]+$", "", n.group(1)).strip() or None) if n else None


class CPPAConnector(Connector):
    family = "cppa"
    source_type = "regulator_announcement"
    parser_version = "cppa-newsroom-v1"
    parser_description = "CPPA newsroom → enforcement_record (enforcement) / source_record (announcements)"
    default_extraction_confidence = 1.0

    def __init__(self, registry_row: dict | None = None, *, limit: int | None = None,
                 include_archive: bool = True, force_archive: bool = False,
                 fetcher: PoliteFetcher | None = None,
                 writer: LiveEnforcementWriter | None = None):
        cfg = (registry_row or {}).get("config") or {}
        self._base = cfg.get("base_url") or (registry_row or {}).get("base_url") or NEWSROOM_DEFAULT
        self._archive_url = cfg.get("archive_url") or ARCHIVE_DEFAULT
        self._archive_only = bool(cfg.get("archive_only"))     # True once the archival pass is done
        self._include_archive = include_archive
        self._force_archive = force_archive                    # do the one-time pass despite archive_only
        self._limit = limit
        self._fetcher = fetcher
        self._writer = writer
        self._meta: dict[str, dict] = {}                       # url -> listing metadata
        self._items = 0
        self._enforcement_written = 0
        self._announcements = 0
        self._pdfs_stored = 0
        self._orgs_resolved = 0
        self._records: list[dict] = []

    def _f(self) -> PoliteFetcher:
        if self._fetcher is None:
            self._fetcher = PoliteFetcher(base=_BASE)
        return self._fetcher

    def _w(self) -> LiveEnforcementWriter:
        if self._writer is None:
            self._writer = LiveEnforcementWriter(
                "cppa", "CPPA", "California Privacy Protection Agency", "US-CA",
                fetcher=self._f(), authority="CCPA/CPRA")
        return self._writer

    def fetch(self) -> list[RawItem]:
        listing = list(self._crawl_listing(self._base))
        # ONE archival pass of the legacy announcements page (until archive_only=true;
        # force_archive re-runs the one-time historical pass on demand).
        if self._include_archive and (not self._archive_only or self._force_archive) and self._archive_url:
            try:
                listing += list(self._crawl_listing(self._archive_url))
            except Exception as e:  # noqa: BLE001 — legacy page may be gone; don't fail the run
                log.warning("cppa archival pass failed (%s); skipping", type(e).__name__)

        items: list[RawItem] = []
        for meta in listing:
            if self._limit is not None and len(items) >= self._limit:
                break
            if meta["url"] in self._meta:
                continue
            try:
                r = self._f().get(meta["url"])
                if r.status_code != 200:
                    continue
            except Exception as e:  # noqa: BLE001
                log.warning("cppa detail fetch failed %s: %s", meta["url"], type(e).__name__)
                continue
            self._meta[meta["url"]] = meta
            items.append(RawItem(
                data=r.text.encode("utf-8"), content_type="text/html",
                source_url=meta["url"], natural_key=_natural_key(meta["url"]),
                title=meta["title"], jurisdiction="US-CA"))
        log.info("cppa fetch: %d announcement pages", len(items))
        return items

    def _crawl_listing(self, url: str):
        r = self._f().get(url)
        if r.status_code != 200:
            return []
        return parse_cppa_listing(r.text, base=_BASE)

    def parse(self, item: RawItem) -> list[dict]:
        detail = parse_cppa_detail(item.data.decode("utf-8", "replace"))
        meta = self._meta.get(item.source_url, {})
        title = meta.get("title") or item.title
        # Classify on the TITLE only: CPPA site chrome (nav has an "Enforcement" menu
        # link) pollutes full-page body text, so body-based classification false-fires.
        # CPPA headlines state the action plainly ("settlement", "fine", "decision").
        enf = is_enforcement(title)
        rec = {
            "url": item.source_url, "title": title,
            "date": meta.get("date"), "categories": meta.get("categories") or [],
            "body": detail["body"], "pdf_links": detail["pdf_links"],
            "is_enforcement": enf,
            # penalty from the title (amounts are stated there), else the scoped body
            "penalty_usd": (extract_penalty(title) or extract_penalty(detail["body"])) if enf else None,
            "company": _company_from_title(title),
        }
        self._records.append(rec)
        return [rec]

    def upsert(self, records: list[dict]) -> None:
        w = self._w()
        w.ensure_regulator()
        for rec in records:
            self._items += 1
            if not rec["is_enforcement"]:
                self._announcements += 1               # source_record only (framework already wrote it)
                continue
            for pdf in rec["pdf_links"]:
                if w.store_pdf(pdf):
                    self._pdfs_stored += 1
            org_id = w.resolve_org(rec["company"]) if rec["company"] else None
            if org_id:
                self._orgs_resolved += 1
            if w.upsert_enforcement(self._enforcement_row(rec, org_id)):
                self._enforcement_written += 1

    def _enforcement_row(self, rec: dict, org_id: str | None) -> dict:
        return {
            "enforcement_id": enforcement_id_for("CPPA", rec["url"]),
            "regulator_id": "CPPA",
            "source_id": rec.get("source_record_id"),
            "source_type": "CPPA",
            "jurisdiction": "US-CA",
            "target_company": rec["company"],          # RAW
            "entity_name": rec["company"],             # RAW
            "issue_tags": rec["categories"],           # RAW — CPPA's own categories, verbatim
            "penalty_usd": rec["penalty_usd"],
            "fine_amount_usd": rec["penalty_usd"],
            "action_date": rec["date"],
            "summary": rec["body"][:1000],             # RAW
            "official_url": rec["url"],
            "source_name": "CPPA Newsroom",
            "verified": True,
            "organization_id": org_id,
            "resolution_status": "resolved" if org_id else "unresolved",
        }

    def record_counts(self) -> dict:
        return {"seen": self._items, "new": self._enforcement_written,
                "changed": 0, "skipped": self._announcements}

    @property
    def metrics(self) -> dict:
        return {"items": self._items, "enforcement_written": self._enforcement_written,
                "announcements_only": self._announcements, "pdfs_stored": self._pdfs_stored,
                "orgs_resolved": self._orgs_resolved}

    @property
    def parsed_records(self) -> list[dict]:
        return list(self._records)


def _natural_key(url: str) -> str:
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or url
