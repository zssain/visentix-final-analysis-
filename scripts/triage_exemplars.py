"""One-time exemplar triage (Stage-3 Workstream B, 2026-07-27).

The 16 approved `is_exemplar` clauses were audited for (a) language,
(b) domain match against the platform classifier, and (c) de-identification.
All 16 pass de-id and the classifier agrees with every assigned domain, but
**6 are non-English** (Dutch / Spanish / German) and are unfit as English
best-practice exemplars for the retail/healthcare/fintech demo cohorts.

This script **deactivates** those 6 — `is_exemplar=false`,
`exemplar_status='deidentified'` (they passed de-id; they are simply not
approvable as exemplars). Rows are **never deleted**. Attribution is
`ai_reviewed`; the reason is logged to `logs/audits/exemplar-triage-2026-07-27.md`
and `logs/decision-log.md`. Human SME re-review still required (SME-REVIEW-CHECKLIST).

Idempotent: re-running only affects rows still flagged `is_exemplar=true`.

Run:  PYTHONPATH=. .venv/bin/python scripts/triage_exemplars.py [--apply]
Without --apply it is a dry run (prints what it would change).
"""

from __future__ import annotations

import sys

import httpx

from app.config import settings
from app.db import get_service_headers

# (clause_id, failure_class, note) — objective failures only (never content-fit,
# which is SME judgment). 6 non-English + 1 de-identification leak.
DEACTIVATE = [
    ("06ca5336-11ab-47c2-99c4-04fa2d9453b0", "lang", "AI domain — Dutch"),
    ("03cc0895-f894-4aaf-aa37-95b781fd84b4", "lang", "no domain — Spanish"),
    ("068b166c-380f-4198-8f72-0118f5a52f88", "lang", "XB domain — Spanish"),
    ("2fdae095-396d-4320-b7b3-1301adb5a289", "lang", "no domain — German"),
    ("a6460051-ad77-48b6-b905-6cb1ea9ac087", "lang", "DC domain — German"),
    ("81ad2b15-28cd-4e58-bed0-e5c154988784", "lang", "DC domain — Spanish"),
    # De-id leak: contains the org name "Aetna" (not in the token blocklist, so
    # validate_deidentification missed it). Also a mis-domained arbitration clause.
    ("f95bbc0b-f642-42db-8350-f70e4735a684", "deid", "RT domain — leaks org name 'Aetna'"),
]


def main(apply: bool) -> None:
    headers = {**get_service_headers(), "Content-Type": "application/json",
               "Prefer": "return=representation"}
    changed = 0
    with httpx.Client(timeout=20) as client:
        for clause_id, lang, note in DEACTIVATE:
            # Only touch rows still active — keeps the script idempotent.
            r = client.get(
                f"{settings.supabase_url}/rest/v1/disclosure_clause"
                f"?select=clause_id,is_exemplar,exemplar_status&clause_id=eq.{clause_id}&limit=1",
                headers=get_service_headers(),
            )
            rows = r.json() if r.status_code == 200 else []
            if not rows:
                print(f"  ! {clause_id[:8]} not found — skipping")
                continue
            if not rows[0].get("is_exemplar"):
                print(f"  = {clause_id[:8]} already deactivated ({lang}) — skipping")
                continue
            print(f"  - {clause_id[:8]} deactivate ({lang}: {note})")
            if apply:
                pr = client.patch(
                    f"{settings.supabase_url}/rest/v1/disclosure_clause?clause_id=eq.{clause_id}",
                    headers=headers,
                    json={"is_exemplar": False, "exemplar_status": "deidentified"},
                )
                if pr.status_code >= 400:
                    print(f"    FAILED {pr.status_code}: {pr.text[:120]}")
                    continue
                changed += 1
    mode = "APPLIED" if apply else "DRY RUN (use --apply to write)"
    print(f"\n{mode}: {changed if apply else len(DEACTIVATE)} row(s) "
          f"{'updated' if apply else 'would be updated'}.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
