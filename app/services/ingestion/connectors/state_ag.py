"""State Attorney-General press-release connector (family `state_ag`).

ONE config-driven class, N sites. The site list lives in `source_registry.config.sites`
as an array of `{state, url, parser_hint, verified}`. Each site's parser is selected
by `parser_hint`; all hints currently route to a generic press-release-list parser
(title, date, link, body), with a dispatch table ready for per-site overrides.

Design principles (task):
- Heterogeneous quality is expected → `extraction_confidence` is set HONESTLY per
  parse (1.0 for clean structured markup, lower for heuristic extraction). Low-
  confidence items are stored + flagged, NEVER silently dropped or promoted.
- Only items matching privacy-ENFORCEMENT keywords become `enforcement_record`
  candidates (regulator `{STATE}-AG`); everything else is `source_record` only
  (source_type='regulator_announcement').
- Per-site failure isolation: one broken site → that site is skipped with a warning
  (partial run); the other sites still succeed.
- Raw bytes go under the `ag_actions` folder (schema §2 family↔folder mapping),
  even though the registry family is `state_ag`.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.ingestion.base import Connector, RawItem
from app.services.ingestion.connectors._enforcement import (
    LiveEnforcementWriter, enforcement_id_for, enforcement_signals, is_privacy_enforcement,
)
from app.services.ingestion.connectors.ftc import PoliteFetcher
from scripts.ingest.ingest_enforcement import extract_penalty

log = logging.getLogger(__name__)

_DATE_RE = re.compile(
    r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4}"
    r"|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b")

# Confidence tiers — honest about how the item was extracted.
CONF_STRUCTURED = 1.0      # <article>/<time datetime> present
CONF_HEURISTIC = 0.6       # link + nearby date text, inferred


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _looks_like_release(href: str, text: str) -> bool:
    if not href or href.startswith(("#", "mailto:", "javascript:")):
        return False
    if any(seg in href.lower() for seg in ("/news", "/press", "/release", "/media", "/20")):
        return True
    return len(_clean(text)) >= 25          # a headline-length link


def parse_generic_list(html: str, base_url: str) -> list[dict]:
    """Generic press-release list → [{title, url, date, body, confidence}].

    Prefers structured <article>/<time> markup (confidence 1.0); falls back to
    dated headline links (confidence 0.6). Deterministic; never guesses a date it
    can't find (leaves it None)."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()

    # 1) structured: <article> cards
    for art in soup.find_all("article"):
        link = art.find("a", href=True)
        if not link:
            continue
        title = _clean(link.get_text() or (art.find(["h1", "h2", "h3"]) or art).get_text())
        if not title:
            continue
        t = art.find("time")
        date = _norm_date(t.get("datetime") or t.get_text()) if t else _first_date(art.get_text())
        body = _clean(art.get_text(" "))[:800]
        url = _abs(link["href"], base_url)
        if url in seen:
            continue
        seen.add(url)
        out.append({"title": title, "url": url, "date": date, "body": body,
                    "confidence": CONF_STRUCTURED if t else CONF_HEURISTIC})

    if out:
        return out

    # 2) heuristic fallback: dated headline links
    for link in soup.find_all("a", href=True):
        text = _clean(link.get_text())
        if not _looks_like_release(link["href"], text):
            continue
        url = _abs(link["href"], base_url)
        if url in seen:
            continue
        container = link.find_parent(["li", "div", "p"]) or link
        date = _first_date(container.get_text(" "))
        seen.add(url)
        out.append({"title": text, "url": url, "date": date,
                    "body": _clean(container.get_text(" "))[:800],
                    "confidence": CONF_HEURISTIC})
    return out


# parser_hint → parser. All hints start on the generic parser; add overrides here.
AG_PARSERS = {
    "generic_list": parse_generic_list,
    "wordpress_list": parse_generic_list,
    "drupal_list": parse_generic_list,
    "ct_year_subpages": parse_generic_list,
    "massgov_list": parse_generic_list,
    "legacy_asp": parse_generic_list,
}


def _abs(href: str, base: str) -> str:
    return href if href.startswith("http") else urljoin(base, href)


def _norm_date(s: str) -> str | None:
    s = _clean(s)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    return _first_date(s)


def _first_date(text: str) -> str | None:
    from datetime import datetime
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    raw = m.group(1)
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%b. %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class StateAGConnector(Connector):
    family = "state_ag"
    source_type = "regulator_announcement"
    raw_folder = "ag_actions"                    # schema §2: state_ag → ag_actions folder
    parser_version = "state-ag-generic-v1"
    parser_description = "State AG press releases → enforcement_record (privacy) / source_record (rest)"
    default_extraction_confidence = 0.6          # heterogeneous; per-item confidence overrides

    def __init__(self, registry_row: dict | None = None, *, sites: list[dict] | None = None,
                 per_site_limit: int = 40, fetcher: PoliteFetcher | None = None,
                 writer: LiveEnforcementWriter | None = None):
        cfg = (registry_row or {}).get("config") or {}
        self._sites = sites if sites is not None else (cfg.get("sites") or [])
        self._per_site_limit = per_site_limit
        self._fetcher = fetcher
        self._writer = writer
        self._meta: dict[str, dict] = {}
        self._warnings: list[str] = []
        self._items = 0
        self._enforcement_written = 0
        self._announcements = 0
        self._low_conf = 0
        self._orgs_resolved = 0
        self._records: list[dict] = []

    def _f(self) -> PoliteFetcher:
        if self._fetcher is None:
            self._fetcher = PoliteFetcher(base="https://example.gov")
        return self._fetcher

    def _w(self) -> LiveEnforcementWriter:
        if self._writer is None:
            self._writer = LiveEnforcementWriter(
                "state_ag", "STATE-AG", "State Attorney General", "US",
                raw_folder="ag_actions", fetcher=self._f())
        return self._writer

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for site in self._sites:
            state, url, hint = site.get("state"), site.get("url"), site.get("parser_hint", "generic_list")
            if not url:
                continue
            try:                                    # ── per-site failure isolation ──
                r = self._f().get(url)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                parser = AG_PARSERS.get(hint, parse_generic_list)
                cards = parser(r.text, url)
            except Exception as e:  # noqa: BLE001 — one broken site must not sink the run
                self._warnings.append(f"{state or url}: crawl failed ({type(e).__name__})")
                log.warning("state_ag site %s failed: %s", state, type(e).__name__)
                continue
            for card in cards[:self._per_site_limit]:
                if card["url"] in self._meta:
                    continue
                self._meta[card["url"]] = {**card, "state": state}
                # RawItem = one release card; per-item honest confidence.
                frag = (f"<h3>{card['title']}</h3><p>{card.get('date') or ''}</p>"
                        f"<div>{card.get('body') or ''}</div>").encode("utf-8")
                items.append(RawItem(
                    data=frag, content_type="text/html", source_url=card["url"],
                    natural_key=f"{state}:{_slug(card['url'])}", title=card["title"],
                    jurisdiction=f"US-{state}" if state else "US",
                    extraction_confidence=card["confidence"]))
        log.info("state_ag fetch: %d releases across %d sites (%d site failures)",
                 len(items), len(self._sites), len(self._warnings))
        return items

    def parse(self, item: RawItem) -> list[dict]:
        meta = self._meta.get(item.source_url, {})
        text = f"{meta.get('title', item.title)} {meta.get('body', '')}"
        rec = {
            "url": item.source_url, "state": meta.get("state"),
            "title": meta.get("title") or item.title, "date": meta.get("date"),
            "body": meta.get("body", ""), "confidence": item.extraction_confidence,
            "is_privacy_enforcement": is_privacy_enforcement(text),
            "signals": enforcement_signals(text),
            "penalty_usd": extract_penalty(text),
            "company": _company_from_release(meta.get("title") or ""),
        }
        self._records.append(rec)
        return [rec]

    def upsert(self, records: list[dict]) -> None:
        w = self._w()
        for rec in records:
            self._items += 1
            if (rec["confidence"] or 1.0) < 1.0:
                self._low_conf += 1                 # flagged (stored, never dropped)
            if not rec["is_privacy_enforcement"]:
                self._announcements += 1            # source_record only
                continue
            reg = f"{rec['state']}-AG" if rec["state"] else "STATE-AG"
            w.ensure_regulator_for(reg, rec["state"])
            org_id = w.resolve_org(rec["company"]) if rec["company"] else None
            if org_id:
                self._orgs_resolved += 1
            if w.upsert_enforcement(self._enforcement_row(rec, reg, org_id)):
                self._enforcement_written += 1

    def _enforcement_row(self, rec: dict, reg: str, org_id: str | None) -> dict:
        return {
            "enforcement_id": enforcement_id_for("STATE_AG", rec["url"]),
            "regulator_id": reg,
            "source_id": rec.get("source_record_id"),
            "source_type": "STATE_AG",
            "jurisdiction": f"US-{rec['state']}" if rec["state"] else "US",
            "target_company": rec["company"],
            "entity_name": rec["company"],
            "issue_tags": rec["signals"],           # enforcement signal terms matched (from source)
            "penalty_usd": rec["penalty_usd"],
            "fine_amount_usd": rec["penalty_usd"],
            "action_date": rec["date"],
            "summary": rec["body"][:1000],          # RAW
            "official_url": rec["url"],
            "source_name": f"{rec['state']} Attorney General" if rec["state"] else "State AG",
            "verified": True,
            "organization_id": org_id,
            "resolution_status": "resolved" if org_id else "unresolved",
        }

    def record_counts(self) -> dict:
        return {"seen": self._items, "new": self._enforcement_written,
                "changed": 0, "skipped": self._announcements}

    def run_warnings(self) -> list[str]:
        w = list(self._warnings)
        if self._low_conf:
            w.append(f"{self._low_conf} low-confidence (<1.0) items stored and flagged")
        return w

    @property
    def metrics(self) -> dict:
        return {"items": self._items, "enforcement_written": self._enforcement_written,
                "announcements_only": self._announcements, "low_confidence": self._low_conf,
                "orgs_resolved": self._orgs_resolved, "site_failures": len(self._warnings)}

    @property
    def parsed_records(self) -> list[dict]:
        return list(self._records)


def _slug(url: str) -> str:
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] or url


def _company_from_release(title: str) -> str | None:
    trig = re.search(r"(?:settle[sd]?\s+with|against|sues?|orders?|fines?|reaches?\s+"
                     r"(?:agreement|settlement)\s+with)\s+", title, re.I)
    if not trig:
        return None
    n = re.match(r"([A-Z][\w&.,'\-]*(?:\s+[A-Z][\w&.,'\-]*){0,5})", title[trig.end():])
    return (re.sub(r"[,\s]+$", "", n.group(1)).strip() or None) if n else None
