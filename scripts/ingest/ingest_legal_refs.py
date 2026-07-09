"""Ingest real legal reference texts from free government sources.

Populates legal_reference with COPPA, HIPAA, GLBA (eCFR), GDPR (EUR-Lex),
and 11 state comprehensive privacy laws (hardcoded metadata + fetched text).

Idempotent: upserts on reference_id. Safe to re-run.

Usage:
    PYTHONPATH=. python scripts/ingest/ingest_legal_refs.py
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from scripts.ingest._common import (
    clean_html,
    finish_run,
    sha256_text,
    start_run,
    upsert,
)

log = logging.getLogger("ingest.legal_refs")

TIMEOUT = 45
TABLE = "legal_reference"
ON_CONFLICT = "reference_id"

# ────────────────────────────────────────────────────────────
# 1. Federal regulations via eCFR (no API key required)
# ────────────────────────────────────────────────────────────

ECFR_SOURCES = [
    {
        "url": "https://www.ecfr.gov/api/versioner/v1/full/2025-01-01/title-16.xml?part=312",
        "reference_id_prefix": "COPPA",
        "jurisdiction": "US-FED",
        "framework": "COPPA",
        "law_type": "sectoral",
        "industry_scope": ["children"],
        "citation_prefix": "16 CFR §",
        "title_prefix": "COPPA — ",
        "domain": "children_teens",
        "effective_date": "2013-07-01",
        "official_url": "https://www.ecfr.gov/current/title-16/part-312",
        "source_name": "eCFR",
        "summary_prefix": "Children's Online Privacy Protection Rule. ",
        "key_sections": ["312.2", "312.3", "312.4", "312.5", "312.6", "312.8", "312.10"],
    },
    {
        "url": "https://www.ecfr.gov/api/versioner/v1/full/2025-01-01/title-45.xml?part=164",
        "reference_id_prefix": "HIPAA",
        "jurisdiction": "US-FED",
        "framework": "HIPAA",
        "law_type": "sectoral",
        "industry_scope": ["health"],
        "citation_prefix": "45 CFR §",
        "title_prefix": "HIPAA Privacy Rule — ",
        "domain": "sensitive_data",
        "effective_date": "2003-04-14",
        "official_url": "https://www.ecfr.gov/current/title-45/part-164",
        "source_name": "eCFR",
        "summary_prefix": "HIPAA Privacy Rule governing protected health information. ",
        "key_sections": [
            "164.502", "164.504", "164.506", "164.508", "164.510",
            "164.512", "164.514", "164.520", "164.522", "164.524",
            "164.526", "164.528", "164.530",
        ],
    },
    {
        "url": "https://www.ecfr.gov/api/versioner/v1/full/2025-01-01/title-16.xml?part=313",
        "reference_id_prefix": "GLBA",
        "jurisdiction": "US-FED",
        "framework": "GLBA",
        "law_type": "sectoral",
        "industry_scope": ["financial"],
        "citation_prefix": "16 CFR §",
        "title_prefix": "GLBA Privacy Rule — ",
        "domain": "data_sharing",
        "effective_date": "2000-11-13",
        "official_url": "https://www.ecfr.gov/current/title-16/part-313",
        "source_name": "eCFR",
        "summary_prefix": "Gramm-Leach-Bliley financial privacy rule. ",
        "key_sections": ["313.3", "313.4", "313.5", "313.6", "313.7", "313.10"],
    },
]


def _parse_ecfr_sections(xml_text: str) -> dict[str, tuple[str, str]]:
    """Parse eCFR XML into {section_number: (heading, full_text)}."""
    root = ET.fromstring(xml_text)
    sections = {}
    for sec in root.iter("DIV8"):
        n = sec.get("N", "")
        if not n:
            continue
        head_el = sec.find("HEAD")
        heading = head_el.text.strip() if head_el is not None and head_el.text else n
        # Strip the "§ 312.1" prefix from heading for cleaner title
        heading = re.sub(r"^§\s*[\d.]+\s*", "", heading).strip()
        full = ET.tostring(sec, encoding="unicode", method="text").strip()
        sections[n] = (heading, full)
    return sections


def fetch_ecfr(src: dict) -> list[dict]:
    """Fetch an eCFR part and return legal_reference rows for key sections."""
    log.info("Fetching eCFR: %s", src["url"][:80])
    try:
        r = httpx.get(src["url"], timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except Exception as exc:
        log.error("eCFR fetch failed for %s: %s", src["reference_id_prefix"], exc)
        return []

    sections = _parse_ecfr_sections(r.text)
    rows = []
    for sec_num in src["key_sections"]:
        if sec_num not in sections:
            log.warning("Section %s not found in %s", sec_num, src["reference_id_prefix"])
            continue
        heading, full_text = sections[sec_num]
        ref_id = f"{src['reference_id_prefix']}-{sec_num}"
        rows.append({
            "reference_id": ref_id,
            "jurisdiction": src["jurisdiction"],
            "framework": src["framework"],
            "law_type": src["law_type"],
            "industry_scope": src["industry_scope"],
            "citation": f"{src['citation_prefix']}{sec_num}",
            "title": f"{src['title_prefix']}{heading}"[:200],
            "summary": f"{src['summary_prefix']}{heading}.",
            "full_text": full_text[:50000],
            "domain": src["domain"],
            "effective_date": src["effective_date"],
            "official_url": src["official_url"],
            "source_name": src["source_name"],
            "content_hash": sha256_text(full_text),
            "sme_authored": False,
        })
    log.info("eCFR %s: %d sections extracted", src["reference_id_prefix"], len(rows))
    return rows


# ────────────────────────────────────────────────────────────
# 2. GDPR via EUR-Lex (no API key required)
# ────────────────────────────────────────────────────────────

GDPR_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679"

GDPR_ARTICLES = {
    5:  ("Principles relating to processing of personal data", "data_sharing"),
    6:  ("Lawfulness of processing", "data_sharing"),
    7:  ("Conditions for consent", "consumer_rights"),
    9:  ("Processing of special categories of personal data", "sensitive_data"),
    13: ("Information to be provided where data are collected from the data subject", "consumer_rights"),
    14: ("Information to be provided where data have not been obtained from the data subject", "consumer_rights"),
    15: ("Right of access by the data subject", "consumer_rights"),
    17: ("Right to erasure ('right to be forgotten')", "consumer_rights"),
    20: ("Right to data portability", "consumer_rights"),
    21: ("Right to object", "consumer_rights"),
    22: ("Automated individual decision-making, including profiling", "ai_automated_decisions"),
    25: ("Data protection by design and by default", "sensitive_data"),
    28: ("Processor", "data_sharing"),
    32: ("Security of processing", "sensitive_data"),
    33: ("Notification of a personal data breach to the supervisory authority", "sensitive_data"),
    35: ("Data protection impact assessment", "ai_automated_decisions"),
    44: ("General principle for transfers", "cross_border"),
    45: ("Transfers on the basis of an adequacy decision", "cross_border"),
    46: ("Transfers subject to appropriate safeguards", "cross_border"),
    49: ("Derogations for specific situations", "cross_border"),
}


def fetch_gdpr() -> list[dict]:
    """Fetch GDPR HTML from EUR-Lex and extract key articles."""
    log.info("Fetching GDPR from EUR-Lex")
    try:
        r = httpx.get(GDPR_URL, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except Exception as exc:
        log.error("EUR-Lex GDPR fetch failed: %s", exc)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    rows = []

    for art_num, (title, domain) in GDPR_ARTICLES.items():
        pattern = re.compile(rf"^Article\s+{art_num}\b")
        art_el = soup.find("p", class_="oj-ti-art", string=pattern)
        full_text = None
        if art_el and art_el.parent:
            full_text = art_el.parent.get_text(separator="\n", strip=True)

        ref_id = f"GDPR-ART-{art_num}"
        rows.append({
            "reference_id": ref_id,
            "jurisdiction": "EU",
            "framework": "GDPR",
            "law_type": "comprehensive",
            "industry_scope": ["all"],
            "citation": f"GDPR Art. {art_num}",
            "title": f"GDPR — {title}",
            "summary": f"Article {art_num} of the General Data Protection Regulation: {title}.",
            "full_text": full_text[:50000] if full_text else None,
            "domain": domain,
            "effective_date": "2018-05-25",
            "official_url": f"https://gdpr-info.eu/art-{art_num}-gdpr/",
            "source_name": "EUR-Lex",
            "content_hash": sha256_text(full_text) if full_text else sha256_text(ref_id),
            "sme_authored": False,
        })

    log.info("GDPR: %d articles extracted", len(rows))
    return rows


# ────────────────────────────────────────────────────────────
# 3. State comprehensive privacy laws (hardcoded metadata + fetched text)
# ────────────────────────────────────────────────────────────

STATE_LAWS = [
    {
        "reference_id": "CCPA-CPRA",
        "jurisdiction": "US-CA",
        "framework": "CCPA/CPRA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Cal. Civ. Code §§ 1798.100–1798.199.100",
        "title": "California Consumer Privacy Act / California Privacy Rights Act",
        "summary": "California's comprehensive consumer privacy law granting residents the right to know, delete, correct, and opt out of the sale or sharing of personal information. Amended by CPRA to add sensitive data controls and create the California Privacy Protection Agency.",
        "domain": "consumer_rights",
        "effective_date": "2023-01-01",
        "official_url": "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=3.&part=4.&lawCode=CIV&title=1.81.5.",
    },
    {
        "reference_id": "CPA-CO",
        "jurisdiction": "US-CO",
        "framework": "CPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Colo. Rev. Stat. §§ 6-1-1301 to 6-1-1313",
        "title": "Colorado Privacy Act",
        "summary": "Colorado's comprehensive privacy law providing consumers rights to access, correct, delete, and opt out of targeted advertising, sale of personal data, and certain profiling. Requires data protection assessments for high-risk processing.",
        "domain": "consumer_rights",
        "effective_date": "2023-07-01",
        "official_url": "https://leg.colorado.gov/bills/sb21-190",
    },
    {
        "reference_id": "CTDPA-CT",
        "jurisdiction": "US-CT",
        "framework": "CTDPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Conn. Pub. Act No. 22-15",
        "title": "Connecticut Data Privacy Act",
        "summary": "Connecticut's comprehensive data privacy law granting consumers rights to access, correct, delete, obtain a copy of, and opt out of the processing of personal data for targeted advertising, sale, or profiling.",
        "domain": "consumer_rights",
        "effective_date": "2023-07-01",
        "official_url": "https://www.cga.ct.gov/2022/act/Pa/pdf/2022PA-00015-R00SB-00006-PA.PDF",
    },
    {
        "reference_id": "DPDPA-DE",
        "jurisdiction": "US-DE",
        "framework": "DPDPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Del. Code tit. 6, ch. 12C",
        "title": "Delaware Personal Data Privacy Act",
        "summary": "Delaware's comprehensive privacy law granting consumers rights to access, correct, delete, and obtain personal data, and opt out of targeted advertising, sale, and profiling. Applies to controllers processing data of 35,000+ Delaware residents.",
        "domain": "consumer_rights",
        "effective_date": "2025-01-01",
        "official_url": "https://legis.delaware.gov/BillDetail?LegislationId=140388",
    },
    {
        "reference_id": "BIPA-IL",
        "jurisdiction": "US-IL",
        "framework": "BIPA",
        "law_type": "sectoral",
        "industry_scope": ["biometric"],
        "citation": "740 ILCS 14/1 et seq.",
        "title": "Illinois Biometric Information Privacy Act",
        "summary": "Illinois law regulating the collection, use, safeguarding, handling, storage, retention, and destruction of biometric identifiers and information. Requires informed written consent before collection and provides a private right of action with statutory damages.",
        "domain": "sensitive_data",
        "effective_date": "2008-10-03",
        "official_url": "https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=3004",
    },
    {
        "reference_id": "NJDPA-NJ",
        "jurisdiction": "US-NJ",
        "framework": "NJDPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "N.J. Stat. Ann. §§ 56:8-166 to 56:8-178",
        "title": "New Jersey Data Protection Act",
        "summary": "New Jersey's comprehensive data privacy law granting consumers rights to access, correct, delete, and obtain personal data. Requires consent for processing sensitive data and mandates data protection assessments.",
        "domain": "consumer_rights",
        "effective_date": "2025-01-15",
        "official_url": "https://pub.njleg.state.nj.us/Bills/2022/S0500/332_R4.PDF",
    },
    {
        "reference_id": "OCPA-OR",
        "jurisdiction": "US-OR",
        "framework": "OCPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Or. Rev. Stat. §§ 646A.570–646A.604",
        "title": "Oregon Consumer Privacy Act",
        "summary": "Oregon's comprehensive privacy law granting consumers rights to access, delete, correct, and obtain personal data. Covers nonprofit organizations and does not require a minimum processing threshold.",
        "domain": "consumer_rights",
        "effective_date": "2024-07-01",
        "official_url": "https://olis.oregonlegislature.gov/liz/2023R1/Measures/Overview/SB619",
    },
    {
        "reference_id": "TDPSA-TX",
        "jurisdiction": "US-TX",
        "framework": "TDPSA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Tex. Bus. & Com. Code §§ 541.001–541.203",
        "title": "Texas Data Privacy and Security Act",
        "summary": "Texas comprehensive privacy law granting consumers rights to access, correct, delete, and obtain personal data, and opt out of targeted advertising, data sales, and profiling. Small business carve-out from certain obligations.",
        "domain": "consumer_rights",
        "effective_date": "2024-07-01",
        "official_url": "https://capitol.texas.gov/BillLookup/History.aspx?LegSess=88R&Bill=HB4",
    },
    {
        "reference_id": "UCPA-UT",
        "jurisdiction": "US-UT",
        "framework": "UCPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Utah Code §§ 13-61-101 to 13-61-404",
        "title": "Utah Consumer Privacy Act",
        "summary": "Utah's comprehensive privacy law granting consumers rights to access, delete, and obtain personal data. Uses an opt-out model for targeted advertising and data sales. Does not require data protection assessments.",
        "domain": "consumer_rights",
        "effective_date": "2023-12-31",
        "official_url": "https://le.utah.gov/~2022/bills/static/SB0227.html",
    },
    {
        "reference_id": "VCDPA-VA",
        "jurisdiction": "US-VA",
        "framework": "VCDPA",
        "law_type": "comprehensive",
        "industry_scope": ["all"],
        "citation": "Va. Code §§ 59.1-575 to 59.1-585",
        "title": "Virginia Consumer Data Protection Act",
        "summary": "Virginia's comprehensive privacy law granting consumers rights to access, correct, delete, obtain, and opt out of processing for targeted advertising, sale, or profiling. Requires data protection assessments for high-risk activities.",
        "domain": "consumer_rights",
        "effective_date": "2023-01-01",
        "official_url": "https://lis.virginia.gov/cgi-bin/legp604.exe?212+ful+SB1392ER",
    },
    {
        "reference_id": "MHMD-WA",
        "jurisdiction": "US-WA",
        "framework": "MHMD",
        "law_type": "sectoral",
        "industry_scope": ["health"],
        "citation": "Wash. Rev. Code § 19.373",
        "title": "Washington My Health My Data Act",
        "summary": "Washington state law protecting consumer health data outside HIPAA scope. Requires consent before collection, sharing, or sale of health data, with a private right of action. Applies broadly to any entity collecting health data of Washington residents.",
        "domain": "sensitive_data",
        "effective_date": "2024-03-31",
        "official_url": "https://app.leg.wa.gov/billsummary?BillNumber=1155&Year=2023&Initiative=false",
    },
]


def fetch_state_laws() -> list[dict]:
    """Build legal_reference rows for state laws, attempting to fetch full text."""
    rows = []
    for law in STATE_LAWS:
        full_text = None
        try:
            r = httpx.get(law["official_url"], timeout=TIMEOUT, follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 200:
                cleaned = clean_html(r.text)
                if len(cleaned) > 100:
                    full_text = cleaned[:80000]
                    log.info("Fetched text for %s (%d chars)", law["reference_id"], len(full_text))
        except Exception as exc:
            log.warning("Could not fetch text for %s: %s", law["reference_id"], exc)

        rows.append({
            "reference_id": law["reference_id"],
            "jurisdiction": law["jurisdiction"],
            "framework": law["framework"],
            "law_type": law["law_type"],
            "industry_scope": law["industry_scope"],
            "citation": law["citation"],
            "title": law["title"],
            "summary": law["summary"],
            "full_text": full_text,
            "domain": law["domain"],
            "effective_date": law["effective_date"],
            "official_url": law["official_url"],
            "source_name": "state_legislature",
            "content_hash": sha256_text(full_text) if full_text else sha256_text(law["citation"]),
            "sme_authored": False,
        })
    log.info("State laws: %d rows built (%d with full text)",
             len(rows), sum(1 for r in rows if r["full_text"]))
    return rows


# ────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────

def main():
    run_id = start_run("legal_refs", "full")
    total_inserted = 0
    failures = []

    # 1. eCFR federal regulations
    for src in ECFR_SOURCES:
        rows = fetch_ecfr(src)
        if rows:
            n = upsert(TABLE, rows, ON_CONFLICT)
            total_inserted += n
            log.info("Upserted %d rows for %s", n, src["reference_id_prefix"])
        else:
            failures.append(src["reference_id_prefix"])

    # 2. GDPR articles
    gdpr_rows = fetch_gdpr()
    if gdpr_rows:
        n = upsert(TABLE, gdpr_rows, ON_CONFLICT)
        total_inserted += n
        log.info("Upserted %d GDPR rows", n)
    else:
        failures.append("GDPR")

    # 3. State laws
    state_rows = fetch_state_laws()
    if state_rows:
        n = upsert(TABLE, state_rows, ON_CONFLICT)
        total_inserted += n
        log.info("Upserted %d state law rows", n)
    else:
        failures.append("state_laws")

    # Finish
    status = "ok" if not failures else "partial"
    notes = f"failures: {failures}" if failures else ""
    finish_run(run_id, inserted=total_inserted, status=status, notes=notes)

    print(f"\n{'='*60}")
    print(f"  Inserted/updated: {total_inserted} legal_reference rows")
    print(f"  Sources: eCFR (COPPA, HIPAA, GLBA), EUR-Lex (GDPR), state legislatures")
    if failures:
        print(f"  Failures: {failures}")
    else:
        print("  Failures: none")
    print(f"  Ingestion run: {run_id}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
