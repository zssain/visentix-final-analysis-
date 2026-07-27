"""Backfill SME review rows for completed assessments (F06, Stage-3).

The intake pipeline used to create the `assessment_review` row lazily (on first
open), so completed live assessments never appeared in the SME queue until
someone opened them by id — orphaning them under STRICT gate. `score_and_persist`
now enqueues eagerly; this backfills the ones scored before that fix.

Scope: `privacy_notice.notice_type='live_assessment'` that HAVE a `report_snapshot`
(i.e. actually completed) and LACK an `assessment_review` row. Seed/peer corpus
notices are not enqueued. Creates a DRAFT review (never touches existing rows —
so approved/in_review assessments are left alone).

Run:  PYTHONPATH=. .venv/bin/python scripts/backfill_review_queue.py [--apply]
Dry run by default.
"""

from __future__ import annotations

import asyncio
import sys

from app.db import supabase_rest_get
from app.services.review import get_or_create_review


async def _completed_missing_review() -> list[str]:
    r = await supabase_rest_get(
        "privacy_notice", select="notice_id",
        filters="notice_type=eq.live_assessment", limit=2000)
    live = {n["notice_id"] for n in r.json() if n.get("notice_id")}

    r = await supabase_rest_get("report_snapshot", select="notice_id", limit=5000)
    snapped = {s.get("notice_id") for s in r.json() if s.get("notice_id")}

    r = await supabase_rest_get("assessment_review", select="assessment_id", limit=5000)
    reviewed = {x["assessment_id"] for x in r.json()}

    return sorted((live & snapped) - reviewed)


def main(apply: bool) -> None:
    missing = asyncio.run(_completed_missing_review())
    print(f"Completed live assessments missing a review row: {len(missing)}")
    if not apply:
        for nid in missing[:10]:
            print(f"  would enqueue {nid}")
        if len(missing) > 10:
            print(f"  … and {len(missing) - 10} more")
        print("\nDRY RUN — pass --apply to create DRAFT review rows.")
        return

    created = 0
    for nid in missing:
        try:
            get_or_create_review(nid)  # persists a DRAFT row if none exists
            created += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {nid}: {exc}")
    print(f"APPLIED: created {created} DRAFT review row(s).")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
