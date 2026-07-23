"""Idempotent seed for source_registry (F02 v2, schema.md v1.3 §2.9).

One row per source family. Upserts on `family` (merge-duplicates), so a second
run changes nothing: it re-sends identical values and never inserts a new row.
`registry_id` (uuid default) and `created_at` are omitted from the payload so
they are preserved on conflict.

Family ↔ raw-artifacts folder mapping (F02 v2 STEP D):
    ftc              -> ftc            (existing folder)
    cppa             -> cppa           (existing folder)
    state_ag         -> ag_actions     (existing folder)
    open_web         -> notices        (existing folder)
    hhs_ocr          -> hhs_ocr        (new folder)
    sec_edgar        -> sec_edgar      (new folder)
    princeton_leuven -> princeton_leuven (new folder)
Existing folders cfpb / frameworks / litigation intentionally have NO registry
family yet (documented, not enum'd — schema.md v1.3 §2.9 OPEN QUESTION).

enabled=false for every family except hhs_ocr (the first live connector).
reliability_tier / cadence are operational source config (VICBNF §3.2 tiering +
business-logic §7 cadences), NOT formula weights — review-and-confirm seed values.

Usage:
    PYTHONPATH=. python scripts/db/seed_source_registry.py
    PYTHONPATH=. python scripts/db/seed_source_registry.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
CFG = dotenv_values(ROOT / ".env")
URL = CFG.get("SUPABASE_URL", "")
KEY = CFG.get("SUPABASE_SERVICE_ROLE_KEY", "")
EDGAR_BULK_PATH = CFG.get("EDGAR_BULK_PATH", "")  # dummy/empty until set in .env


def rows() -> list[dict]:
    return [
        {
            "family": "hhs_ocr",
            "display_name": "HHS OCR Breach Portal",
            "base_url": "https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf",
            "cadence": "weekly",
            "reliability_tier": 1,
            "parser_type": "html_table",
            "enabled": True,  # the one enabled family
            "config": {"raw_artifacts_folder": "hhs_ocr",
                       "note": "Breach reports -> security_event only; NEVER enforcement_record / F-004 (OD-06)."},
        },
        {
            "family": "sec_edgar",
            "display_name": "SEC EDGAR Corporate Filings",
            "base_url": "https://www.sec.gov/cgi-bin/browse-edgar",
            "cadence": "monthly",
            "reliability_tier": 1,
            "parser_type": "edgar_bulk",
            "enabled": False,
            "config": {"raw_artifacts_folder": "sec_edgar",
                       "edgar_bulk_path": EDGAR_BULK_PATH,
                       "note": "Populates organization_alias (cik/ticker); source_type=corporate_filing."},
        },
        {
            "family": "ftc",
            "display_name": "FTC Cases & Proceedings",
            "base_url": "https://www.ftc.gov/legal-library/browse/cases-proceedings",
            "cadence": "weekly",
            "reliability_tier": 1,
            "parser_type": "html",
            "enabled": False,
            "config": {"raw_artifacts_folder": "ftc",
                       "note": "Reuses scripts/ingest/ingest_enforcement.py parsing."},
        },
        {
            "family": "cppa",
            "display_name": "California Privacy Protection Agency",
            "base_url": "https://privacy.ca.gov/about-us/newsroom/",
            "cadence": "weekly",
            "reliability_tier": 1,
            "parser_type": "html",
            "enabled": False,
            "config": {"raw_artifacts_folder": "cppa",
                       "archive_url": "https://cppa.ca.gov/announcements/",
                       "archive_only": True,   # legacy page: one historical pass done, now skip
                       "note": "cppa.ca.gov/announcements is archive-only since 2026-01-26; "
                               "current newsroom is privacy.ca.gov/about-us/newsroom/."},
        },
        {
            "family": "state_ag",
            "display_name": "State Attorneys-General Actions",
            "base_url": None,  # varies per state
            "cadence": "weekly",
            "reliability_tier": 1,
            "parser_type": "html",
            "enabled": False,   # stays disabled until the final ~16-site list is confirmed
            "config": {"raw_artifacts_folder": "ag_actions",
                       "note": "Config-driven: one StateAGConnector, N sites. Privacy-enforcement "
                               "items -> enforcement_record ({STATE}-AG); rest -> source_record only.",
                       # Engineer-confirmed 16-site list (2026-07-23). CA/TX/CT/CO URLs
                       # verified; the rest still need per-site parser validation, so
                       # the family stays enabled=false until each is confirmed.
                       "sites": [
                           {"state": "CA", "url": "https://oag.ca.gov/media/news",
                            "parser_hint": "drupal_list", "verified": True},
                           {"state": "TX", "url": "https://www.texasattorneygeneral.gov/news/releases",
                            "parser_hint": "generic_list", "verified": True},
                           {"state": "CT", "url": "https://portal.ct.gov/ag/press-releases",
                            "parser_hint": "ct_year_subpages", "verified": True},
                           {"state": "CO", "url": "https://coag.gov/press-releases/",
                            "parser_hint": "wordpress_list", "verified": True},
                           {"state": "NY", "url": "https://ag.ny.gov/press-releases",
                            "parser_hint": "generic_list", "verified": False},
                           {"state": "WA", "url": "https://www.atg.wa.gov/media-center/news-releases",
                            "parser_hint": "generic_list", "verified": False},
                           {"state": "IL", "url": "https://www.illinoisattorneygeneral.gov/news/",
                            "parser_hint": "generic_list", "verified": False},
                           {"state": "MA", "url": "https://www.mass.gov/orgs/office-of-the-attorney-general/news",
                            "parser_hint": "massgov_list", "verified": False},
                           {"state": "NJ", "url": "https://www.njoag.gov/category/press-releases/",
                            "parser_hint": "wordpress_list", "verified": False},
                           {"state": "VA", "url": "https://www.oag.state.va.us/media-center/news-releases",
                            "parser_hint": "generic_list", "verified": False},
                           {"state": "OR", "url": "https://www.doj.state.or.us/media-home/news-media-releases/",
                            "parser_hint": "wordpress_list", "verified": False},
                           {"state": "MN", "url": "https://www.ag.state.mn.us/Office/Communications/PressReleases.asp",
                            "parser_hint": "legacy_asp", "verified": False},
                           {"state": "FL", "url": "https://www.myfloridalegal.com/newsroom",
                            "parser_hint": "generic_list", "verified": False},
                           {"state": "NH", "url": "https://www.doj.nh.gov/news",
                            "parser_hint": "generic_list", "verified": False},
                           {"state": "DE", "url": "https://news.delaware.gov/tag/attorney-general/",
                            "parser_hint": "wordpress_list", "verified": False},
                           {"state": "MD", "url": "https://www.marylandattorneygeneral.gov/press",
                            "parser_hint": "generic_list", "verified": False},
                       ]},
        },
        {
            "family": "princeton_leuven",
            "display_name": "Princeton-Leuven Longitudinal Privacy-Policy Corpus",
            "base_url": None,
            "cadence": "manual",
            "reliability_tier": 3,
            "parser_type": "dataset",
            "enabled": False,
            "config": {"raw_artifacts_folder": "princeton_leuven",
                       "note": "Bulk research dataset; source_type=dataset; feeds F01 intake."},
        },
        {
            "family": "open_web",
            "display_name": "Open-Web Peer Notice Crawl",
            "base_url": None,
            "cadence": "monthly",
            "reliability_tier": 3,
            "parser_type": "html",
            "enabled": False,
            "config": {"raw_artifacts_folder": "notices",
                       "note": "Reuses scripts/batch_assess.py intake; org resolution via organization_alias(domain)."},
        },
    ]


def seed() -> int:
    if not (URL and KEY):
        print("seed_source_registry: SUPABASE_URL / SERVICE_ROLE_KEY missing in .env", file=sys.stderr)
        return 1
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    payload = rows()
    r = httpx.post(
        f"{URL}/rest/v1/source_registry?on_conflict=family",
        headers=headers, json=payload, timeout=30,
    )
    if r.status_code >= 300:
        print(f"seed_source_registry: upsert failed {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return 1
    print(f"seed_source_registry: upserted {len(payload)} families "
          f"(enabled: {[x['family'] for x in payload if x['enabled']]}).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the rows, do not write")
    args = ap.parse_args()
    if args.dry_run:
        print(json.dumps(rows(), indent=2))
        return 0
    return seed()


if __name__ == "__main__":
    sys.exit(main())
