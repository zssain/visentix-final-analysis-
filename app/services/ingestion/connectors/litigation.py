"""Litigation connector — SKELETON (F07 corpus growth).

Ingests a public CourtListener / RSS feed of privacy-related court filings into the
`litigation` table (migration 0037). **NOT wired to scoring** — these rows are a
raw corpus signal with `reliability='low'` and no weighting. Using litigation in
any score requires an EXPERT-approved weighting scheme first (see decision-log:
"litigation — expert weighting needed"). Until then this only stores rows.

Parse functions are pure + testable; the network fetch is guarded (needs
COURTLISTENER_TOKEN) and best-effort. No secrets are logged.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.config import settings
from app.db import supabase_rest_post

log = logging.getLogger(__name__)

RELIABILITY = "low"          # fixed — NOT wired to scoring; expert weighting needed
COURTLISTENER_BASE = "https://www.courtlistener.com"


def parse_courtlistener(results: list[dict]) -> list[dict]:
    """CourtListener API `results` → litigation rows (pure)."""
    rows = []
    for r in results:
        url = r.get("absolute_url") or r.get("url") or ""
        if url and url.startswith("/"):
            url = COURTLISTENER_BASE + url
        rows.append({
            "source": "courtlistener",
            "title": r.get("caseName") or r.get("case_name") or r.get("title"),
            "court": r.get("court") or r.get("court_id"),
            "filed_at": r.get("dateFiled") or r.get("date_filed"),
            "url": url or None,
            "issue_tags": None,          # NULL — no taxonomy applied (skeleton)
            "reliability": RELIABILITY,
        })
    return [r for r in rows if r["url"]]


def parse_rss(xml: str) -> list[dict]:
    """Generic RSS <item> → litigation rows (pure)."""
    soup = BeautifulSoup(xml, "lxml-xml")
    rows = []
    for item in soup.find_all("item"):
        link = item.find("link")
        title = item.find("title")
        pub = item.find("pubDate")
        url = link.get_text(strip=True) if link else None
        rows.append({
            "source": "rss",
            "title": title.get_text(strip=True) if title else None,
            "court": None,
            "filed_at": pub.get_text(strip=True) if pub else None,
            "url": url,
            "issue_tags": None,
            "reliability": RELIABILITY,
        })
    return [r for r in rows if r["url"]]


async def _fetch_courtlistener(query: str, limit: int) -> list[dict]:
    """Best-effort CourtListener search. Guarded on the token; never raises."""
    token = settings.courtlistener_token
    if not token:
        log.info("litigation: COURTLISTENER_TOKEN unset — skipping fetch (skeleton).")
        return []
    import httpx
    try:
        r = httpx.get(f"{COURTLISTENER_BASE}/api/rest/v4/search/",
                      params={"q": query, "type": "r"}, headers={"Authorization": f"Token {token}"},
                      timeout=15)
        return (r.json().get("results", []) if r.status_code == 200 else [])[:limit]
    except Exception as e:  # noqa: BLE001
        log.warning("litigation: fetch failed (non-fatal): %s", e)
        return []


async def ingest(query: str = "privacy", limit: int = 50) -> int:
    """Fetch → parse → store litigation rows (dedupe on url). Returns count stored.
    NOT wired to scoring. Safe to call with no token (stores nothing)."""
    rows = parse_courtlistener(await _fetch_courtlistener(query, limit))
    stored = 0
    for row in rows:
        r = await supabase_rest_post("litigation", row, on_conflict="url", upsert=True)
        if r.status_code < 400:
            stored += 1
    log.info("litigation: stored %d rows (reliability=low, NOT scored).", stored)
    return stored
