"""Rehearsal-artifact labeling + smoke-test junk removal (Stage-3).

Owner decision (2026-07-28): KEEP the 1-800-Flowers rehearsal artifacts for
comparison, but (a) label the rehearsal org so it is filterable and clearly not
production data, and (b) delete the one bogus `assessment_review` row the
pre-fix shadowed-route smoke test created (`assessment_id='gate-mode'`).

Already-verified exclusions (no action needed — kept for the record):
  • the rehearsal org has only a `live_assessment` notice (no `open_web`), so the
    CQS gate (F03 AC-5) excludes it from every dynamic benchmark population;
  • it is in no `benchmark_membership` demo cohort.

This labels `organization.origin='rehearsal'` (reversible — was NULL) and hard-
deletes the single junk review row. Idempotent.

Run:  PYTHONPATH=. .venv/bin/python scripts/rehearsal_cleanup.py [--apply]
"""

from __future__ import annotations

import sys

import httpx

from app.config import settings
from app.db import get_service_headers

REHEARSAL_ORG = "066745ed-3a22-48bb-94e4-e3f002787bdb"
BOGUS_REVIEW = "gate-mode"  # junk assessment_id from the smoke test
SB = settings.supabase_url


def main(apply: bool) -> None:
    hdr = {**get_service_headers(), "Content-Type": "application/json", "Prefer": "return=representation"}
    with httpx.Client(timeout=20) as c:
        # (a) label the rehearsal org (reversible)
        print(f"label organization {REHEARSAL_ORG[:8]} origin='rehearsal'")
        if apply:
            r = c.patch(f"{SB}/rest/v1/organization?organization_id=eq.{REHEARSAL_ORG}",
                        headers=hdr, json={"origin": "rehearsal"})
            print(f"  -> HTTP {r.status_code}")

        # (b) delete the bogus smoke-test review row (owner pre-approved)
        print(f"delete assessment_review assessment_id='{BOGUS_REVIEW}' (smoke-test junk)")
        if apply:
            r = c.delete(f"{SB}/rest/v1/assessment_review?assessment_id=eq.{BOGUS_REVIEW}",
                         headers={**get_service_headers(), "Prefer": "return=representation"})
            print(f"  -> HTTP {r.status_code} removed={len(r.json()) if r.status_code < 300 and r.text else '?'}")

    print("\n" + ("APPLIED." if apply else "DRY RUN — pass --apply to write."))


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
