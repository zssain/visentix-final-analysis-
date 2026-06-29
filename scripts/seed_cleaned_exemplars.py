"""Seed 3 de-identified, SME-cleaned exemplars for demo purposes.

These are clearly labelled as de-identified demo content.
Domains: data_sharing, retention, ai_automated_decisions.

Usage:
    PYTHONPATH=. python scripts/seed_cleaned_exemplars.py
"""

import json
import logging
from uuid import uuid4

import httpx
from dotenv import dotenv_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_exemplars")

CONFIG = dotenv_values(".env")
URL = CONFIG["SUPABASE_URL"]
KEY = CONFIG["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

EXEMPLARS = [
    {
        "domain": "data_sharing",
        "category": "data_sharing",
        "clause_text": (
            "[Organization] may share your personal information with the following "
            "categories of third parties: (a) service providers who assist with payment "
            "processing, customer support, and analytics; (b) advertising partners for "
            "targeted marketing, subject to your opt-out preferences; and (c) business "
            "partners for joint offerings. We require contractual safeguards from all "
            "recipients and limit sharing to what is necessary for the stated purpose."
        ),
        "maturity_note": (
            "HIGH maturity — names specific third-party categories, states purposes, "
            "mentions opt-out and contractual safeguards. De-identified demo exemplar."
        ),
        "source_internal_ref": "DEMO-CLEANED-001",
        "sme_cleaned": True,
    },
    {
        "domain": "retention",
        "category": "retention",
        "clause_text": (
            "[Organization] retains personal information as follows: account data for "
            "the duration of your account plus 30 days; transaction records for 7 years "
            "as required by financial regulations; marketing preferences until withdrawn; "
            "and anonymized analytics data indefinitely. Upon account deletion, personal "
            "data is purged within 90 days except where legal retention applies."
        ),
        "maturity_note": (
            "HIGH maturity — specifies retention periods per data category, cites legal "
            "basis, defines deletion timeline. De-identified demo exemplar."
        ),
        "source_internal_ref": "DEMO-CLEANED-002",
        "sme_cleaned": True,
    },
    {
        "domain": "ai_automated_decisions",
        "category": "ai_automated_decisions",
        "clause_text": (
            "[Organization] uses automated decision-making systems for the following "
            "purposes: (a) fraud detection and prevention, (b) content personalization, "
            "and (c) credit risk assessment. For decisions that significantly affect you, "
            "you may request human review by contacting our privacy team. We regularly "
            "assess these systems for bias and accuracy."
        ),
        "maturity_note": (
            "HIGH maturity — discloses specific AI use cases, provides human review "
            "mechanism, mentions bias assessment. De-identified demo exemplar."
        ),
        "source_internal_ref": "DEMO-CLEANED-003",
        "sme_cleaned": True,
    },
]


def main():
    for ex in EXEMPLARS:
        # Check if already seeded
        r = httpx.get(
            f"{URL}/rest/v1/exemplar?select=id&source_internal_ref=eq.{ex['source_internal_ref']}&limit=1",
            headers=H, timeout=10,
        )
        if r.json():
            log.info("SKIP %s (already exists)", ex["source_internal_ref"])
            continue

        r2 = httpx.post(
            f"{URL}/rest/v1/exemplar",
            headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=ex,
            timeout=15,
        )
        log.info("SEEDED %s domain=%s sme_cleaned=%s (%d)",
                 ex["source_internal_ref"], ex["domain"], ex["sme_cleaned"], r2.status_code)

    # Verify
    r = httpx.get(f"{URL}/rest/v1/exemplar?select=domain,sme_cleaned,source_internal_ref&sme_cleaned=eq.true",
                   headers=H, timeout=15)
    log.info("Cleaned exemplars: %d", len(r.json()))
    for e in r.json():
        log.info("  %s domain=%s", e["source_internal_ref"], e["domain"])


if __name__ == "__main__":
    main()
