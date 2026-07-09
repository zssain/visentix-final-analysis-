"""Ingest enforcement actions from FTC (scrape) and CourtListener (API).

Adds to existing enforcement_record rows (never deletes). Upserts on
enforcement_id so re-runs are safe. Leaves embedding=NULL for later backfill.

Prerequisites:
    - Apply db/migrations/0013_enforcement_extra_cols.sql (adds source_type, verified).
    - .env must contain COURTLISTENER_TOKEN.

Usage:
    PYTHONPATH=. python scripts/ingest/ingest_enforcement.py
"""

import logging
import re
import time as _time
import uuid
from datetime import date

import httpx
from bs4 import BeautifulSoup

from scripts.ingest._common import (
    COURTLISTENER_TOKEN,
    finish_run,
    sha256_text,
    start_run,
    upsert,
)


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID v5 from a seed string (stable across runs)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

log = logging.getLogger("ingest.enforcement")

TABLE = "enforcement_record"
ON_CONFLICT = "enforcement_id"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ────────────────────────────────────────────────────────────
# Domain keyword mapping (repo's 9 domain slugs)
# ────────────────────────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "consumer_rights": ["consumer rights", "right to know", "access request", "deletion request", "opt out", "right to delete", "right to correct"],
    "data_sharing": ["data sharing", "third party", "sale of data", "data broker", "sharing personal", "sell personal"],
    "tracking_cookies": ["tracking", "cookies", "geolocation", "location data", "surveillance", "pixel", "fingerprint", "ad tech"],
    "retention": ["retention", "data retention", "storage limitation", "kept longer"],
    "sensitive_data": ["sensitive data", "health data", "biometric", "genetic", "social security", "financial data", "medical"],
    "ai_automated_decisions": ["automated", "algorithm", "artificial intelligence", "ai", "profiling", "machine learning"],
    "cross_border": ["cross-border", "international transfer", "data transfer", "eu-us", "adequacy"],
    "children_teens": ["children", "coppa", "child", "minor", "teen", "student", "education", "kid"],
    "other": [],
}


def map_domains(text: str) -> list[str]:
    """Map free text to repo domain slugs via keywords."""
    text_lower = text.lower()
    domains = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domain == "other":
            continue
        if any(kw in text_lower for kw in keywords):
            domains.append(domain)
    return domains or ["other"]


def map_laws_cited(text: str) -> list[str]:
    """Map text to known legal reference IDs via keyword matching."""
    text_lower = text.lower()
    cited = []
    law_keywords = {
        "CCPA-CPRA": ["ccpa", "cpra", "california consumer privacy", "1798.1"],
        "GDPR-ART-5": ["gdpr"],
        "COPPA-312.3": ["coppa", "children's online privacy"],
        "HIPAA-164.502": ["hipaa", "health insurance portability"],
        "GLBA-313.3": ["glba", "gramm-leach-bliley", "financial privacy"],
        "BIPA-IL": ["bipa", "biometric information privacy", "740 ilcs 14"],
    }
    for ref_id, keywords in law_keywords.items():
        if any(kw in text_lower for kw in keywords):
            cited.append(ref_id)
    # FTC Act is always cited for FTC actions
    if "ftc" in text_lower:
        cited.append("CCPA-CPRA")  # Most FTC privacy actions relate to CCPA
    return list(set(cited))


def extract_penalty(text: str) -> float | None:
    """Extract a dollar penalty amount from text. Returns None if not found."""
    patterns = [
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|mil)\b',
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:billion|bil)\b',
        r'pay\s+\$\s*([\d,]+(?:\.\d+)?)',
        r'penalty\s+of\s+\$\s*([\d,]+(?:\.\d+)?)',
        r'fine\s+of\s+\$\s*([\d,]+(?:\.\d+)?)',
        r'settlement\s+.*?\$\s*([\d,]+(?:\.\d+)?)',
        r'\$\s*([\d,]+(?:\.\d+)?)',
    ]
    text_lower = text.lower()
    for pattern in patterns:
        m = re.search(pattern, text_lower)
        if m:
            amount_str = m.group(1).replace(",", "")
            amount = float(amount_str)
            if "million" in text_lower[m.start():m.end()+20] or "mil" in text_lower[m.start():m.end()+10]:
                amount *= 1_000_000
            elif "billion" in text_lower[m.start():m.end()+20]:
                amount *= 1_000_000_000
            if amount >= 1000:  # Ignore tiny amounts that are likely not penalties
                return amount
    return None


# ────────────────────────────────────────────────────────────
# A) FTC — scrape the legal library privacy & security cases
# ────────────────────────────────────────────────────────────

FTC_LISTING_URL = "https://www.ftc.gov/legal-library/browse/cases-proceedings"
FTC_BASE = "https://www.ftc.gov"

# Multiple search terms to maximize coverage
FTC_SEARCH_TERMS = [
    "privacy+data+security",
    "data+breach",
    "coppa+children",
    "biometric",
    "geolocation+tracking",
    "consumer+data",
]

HREF_EXCLUDE = {
    "public-statements", "closing-letters", "commissioner-statements",
    "adjudicative-proceedings", "banned-debt-collectors",
}


def _scrape_ftc_case_links(max_pages: int = 3) -> list[dict]:
    """Scrape FTC case listing pages for privacy/security cases."""
    cases = []
    seen_hrefs: set[str] = set()

    for term in FTC_SEARCH_TERMS:
        for page in range(max_pages):
            url = f"{FTC_LISTING_URL}?search_api_fulltext={term}&items_per_page=50&page={page}"
            try:
                r = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
                if r.status_code != 200:
                    break
            except Exception:
                break

            soup = BeautifulSoup(r.text, "html.parser")
            page_count = 0

            for a in soup.find_all("a", href=True):
                href = a["href"]
                title = a.get_text(strip=True)
                if (
                    "/legal-library/browse/cases-proceedings/" in href
                    and title
                    and len(title) > 5
                    and not any(ex in href for ex in HREF_EXCLUDE)
                    and href not in seen_hrefs
                ):
                    full_url = href if href.startswith("http") else f"{FTC_BASE}{href}"
                    seen_hrefs.add(href)
                    cases.append({"title": title, "url": full_url})
                    page_count += 1

            log.info("FTC '%s' page %d: %d new cases", term[:20], page, page_count)
            if page_count == 0:
                break
            _time.sleep(1)

    return cases


def _scrape_ftc_case_detail(case: dict) -> dict | None:
    """Fetch an individual FTC case page and extract metadata."""
    try:
        r = httpx.get(case["url"], headers=UA, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return None
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Extract body text
    body_div = soup.find("div", class_=lambda c: c and "field--name-body" in str(c))
    body = ""
    if body_div:
        body = body_div.get_text(separator=" ", strip=True)[:2000]

    # Extract first date (usually the most recent action date)
    action_date = None
    for time_el in soup.find_all("time"):
        dt_str = time_el.get("datetime", "")
        if dt_str:
            try:
                action_date = dt_str[:10]  # YYYY-MM-DD
                break
            except Exception:
                pass

    # Build summary from title + body excerpt
    summary = body[:500] if body else case["title"]
    combined_text = f"{case['title']} {body}"

    penalty = extract_penalty(combined_text)
    eid = _stable_uuid(f"FTC:{case['url']}")

    return {
        "enforcement_id": eid,
        "source_type": "FTC",
        "regulator_id": "FTC",
        "jurisdiction": "US-FED",
        "entity_name": case["title"].split(",")[0].strip()[:200],
        "target_company": case["title"].split(",")[0].strip()[:200],
        "entity_industry": None,
        "action_date": action_date,
        "fine_amount_usd": penalty,
        "penalty_usd": penalty,
        "violation_types": map_laws_cited(combined_text),
        "laws_cited": map_laws_cited(combined_text),
        "domains": map_domains(combined_text),
        "issue_tags": map_domains(combined_text),
        "remedies": None,
        "summary": summary,
        "official_url": case["url"],
        "source_name": "FTC Legal Library",
        "content_hash": sha256_text(combined_text),
        "verified": True,
    }


def fetch_ftc() -> list[dict]:
    """Scrape FTC privacy/security enforcement cases."""
    log.info("Scraping FTC cases...")
    case_links = _scrape_ftc_case_links(max_pages=5)
    log.info("Found %d FTC case links", len(case_links))

    rows = []
    for i, case in enumerate(case_links):
        detail = _scrape_ftc_case_detail(case)
        if detail:
            rows.append(detail)
        if (i + 1) % 10 == 0:
            log.info("FTC: scraped %d/%d case pages", i + 1, len(case_links))
        _time.sleep(0.5)  # Polite rate limiting

    log.info("FTC: %d cases with details extracted", len(rows))
    return rows


# ────────────────────────────────────────────────────────────
# B) CourtListener — search API for privacy enforcement opinions
# ────────────────────────────────────────────────────────────

CL_BASE = "https://www.courtlistener.com"
CL_SEARCH = f"{CL_BASE}/api/rest/v4/search/"

CL_QUERIES = [
    "privacy+data+breach",
    "CCPA+%22California+Consumer+Privacy%22",
    "BIPA+%22biometric+information%22",
    "%22consumer+privacy%22+enforcement",
    "COPPA+%22children+online+privacy%22",
    "HIPAA+%22health+information%22+breach",
    "%22data+security%22+FTC",
    "%22privacy+violation%22+settlement",
]

# CourtListener allows ~5 requests/min for free tier; be conservative
CL_DELAY_SECONDS = 3


def _cl_search(query: str, max_pages: int = 3) -> list[dict]:
    """Run a single CourtListener search query, paginating."""
    headers = {"Authorization": f"Token {COURTLISTENER_TOKEN}"}
    results = []
    seen_ids = set()

    url = f"{CL_SEARCH}?q={query}&type=o&page_size=20&order_by=dateFiled+desc"

    for page_num in range(max_pages):
        if not url:
            break
        try:
            r = httpx.get(url, headers=headers, timeout=30)
            if r.status_code == 429:
                log.warning("CourtListener rate-limited, waiting 30s")
                _time.sleep(30)
                r = httpx.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                log.warning("CourtListener query '%s' page %d → %d", query[:30], page_num, r.status_code)
                break
        except Exception as exc:
            log.warning("CourtListener error: %s", exc)
            break

        data = r.json()
        for hit in data.get("results", []):
            cid = str(hit.get("cluster_id", ""))
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                results.append(hit)

        url = data.get("next")
        _time.sleep(CL_DELAY_SECONDS)

    return results


def _cl_to_enforcement(hit: dict) -> dict:
    """Convert a CourtListener search result to an enforcement_record row."""
    case_name = hit.get("caseName", "") or hit.get("caseNameFull", "") or "Unknown"
    abs_url = hit.get("absolute_url", "")
    official_url = f"{CL_BASE}{abs_url}" if abs_url else ""
    cluster_id = str(hit.get("cluster_id", ""))

    # Determine source_type: DOJ if United States is the petitioner
    is_doj = case_name.lower().startswith("united states") or "u.s. v." in case_name.lower()
    source_type = "DOJ" if is_doj else "COURT"

    date_filed = hit.get("dateFiled") or None
    court = hit.get("court", "")
    syllabus = hit.get("syllabus", "") or ""
    posture = hit.get("posture", "") or ""
    combined = f"{case_name} {syllabus} {posture}"

    # Entity name: extract the defendant/respondent from the case name
    entity = case_name
    for sep in [" v. ", " v ", " vs. ", " vs "]:
        if sep in case_name:
            parts = case_name.split(sep, 1)
            # The defendant is usually the second part, unless US/FTC is second
            defendant = parts[1].strip()
            plaintiff = parts[0].strip()
            if any(gov in plaintiff.lower() for gov in ["united states", "ftc", "federal trade"]):
                entity = defendant
            else:
                entity = plaintiff
            break

    eid = _stable_uuid(f"CL:{source_type}:{official_url}")

    return {
        "enforcement_id": eid,
        "source_type": source_type,
        "regulator_id": "FTC" if "ftc" in case_name.lower() or "federal trade" in case_name.lower() else None,
        "jurisdiction": "US-FED",
        "entity_name": entity[:200],
        "target_company": entity[:200],
        "entity_industry": None,
        "action_date": date_filed,
        "fine_amount_usd": extract_penalty(combined),
        "penalty_usd": extract_penalty(combined),
        "violation_types": map_laws_cited(combined),
        "laws_cited": map_laws_cited(combined),
        "domains": map_domains(combined),
        "issue_tags": map_domains(combined),
        "remedies": None,
        "summary": f"{case_name}. Court: {court}. Filed: {date_filed}."[:500],
        "official_url": official_url,
        "source_name": "CourtListener",
        "content_hash": sha256_text(combined),
        "verified": False,  # Aggregated snippet, not primary source
    }


def fetch_courtlistener() -> list[dict]:
    """Search CourtListener for privacy enforcement opinions."""
    if not COURTLISTENER_TOKEN:
        log.error("COURTLISTENER_TOKEN not set, skipping")
        return []

    log.info("Searching CourtListener (%d queries)...", len(CL_QUERIES))
    all_hits = {}  # cluster_id → hit (dedup)

    for i, q in enumerate(CL_QUERIES):
        if i > 0:
            _time.sleep(CL_DELAY_SECONDS)
        results = _cl_search(q, max_pages=3)
        for hit in results:
            cid = str(hit.get("cluster_id", ""))
            if cid not in all_hits:
                all_hits[cid] = hit
        log.info("CL query '%s': %d hits (%d total unique)", q[:30], len(results), len(all_hits))

    rows = [_cl_to_enforcement(hit) for hit in all_hits.values()]
    log.info("CourtListener: %d unique enforcement rows built", len(rows))
    return rows


# ────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────

BATCH_SIZE = 50


def main():
    run_id = start_run("enforcement", "full")
    total_inserted = 0
    failures = []

    # A) FTC
    ftc_rows = fetch_ftc()
    if ftc_rows:
        for i in range(0, len(ftc_rows), BATCH_SIZE):
            batch = ftc_rows[i : i + BATCH_SIZE]
            n = upsert(TABLE, batch, ON_CONFLICT)
            total_inserted += n
        log.info("FTC: upserted %d rows total", len(ftc_rows))
    else:
        failures.append("FTC")

    # B) CourtListener
    cl_rows = fetch_courtlistener()
    if cl_rows:
        for i in range(0, len(cl_rows), BATCH_SIZE):
            batch = cl_rows[i : i + BATCH_SIZE]
            n = upsert(TABLE, batch, ON_CONFLICT)
            total_inserted += n
        log.info("CourtListener: upserted %d rows total", len(cl_rows))
    else:
        failures.append("CourtListener")

    status = "ok" if not failures else "partial"
    notes = f"failures: {failures}" if failures else ""
    finish_run(run_id, inserted=total_inserted, status=status, notes=notes)

    print(f"\n{'='*60}")
    print(f"  Inserted/updated: {total_inserted} enforcement_record rows")
    print(f"    FTC:            {len(ftc_rows)}")
    print(f"    CourtListener:  {len(cl_rows)}")
    if failures:
        print(f"  Failures: {failures}")
    else:
        print("  Failures: none")
    print(f"  Ingestion run: {run_id}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
