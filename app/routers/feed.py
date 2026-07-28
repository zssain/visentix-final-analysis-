"""White-label data feed — VICBNF-009.

GET /feed/white-label returns per-cohort AGGREGATE intelligence with confidence
+ versioning + permitted-use metadata. Never exposes raw source clause text and
never any organization identity or cohort membership (F20 hardening).

Auth: a partner API key header (`X-Partner-Key`, hash-compared) OR our internal
admin JWT. Every served call is written to feed_access_log. Cohorts below the
minimum sample (OD-05 n=10 + DIR-006) are suppressed server-side.
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.auth import get_current_user
from app.services import partner as P

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/white-label")
async def white_label_feed(request: Request):
    """Per-cohort white-label feed. Partner API key OR internal admin.

    Records are aggregates by (industry × object_type) with population_n; no
    organization_id, cohort membership, or raw clause text. n<10 suppressed.
    """
    api_key = request.headers.get("X-Partner-Key")
    partner_id: str | None = None
    api_key_id: str | None = None

    if api_key:
        ctx = await P.verify_api_key(api_key)   # hash-compare; revoked → None
        if not ctx:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked partner API key.")
        partner_id, api_key_id = ctx["partner_id"], ctx["api_key_id"]
    else:
        # Internal path — our admin only (unchanged access for oversight).
        user = await get_current_user(request)
        if user.role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Partner API key required.")

    feed = await P.build_feed_aggregates()
    await P.log_feed_access(partner_id, api_key_id, "/feed/white-label", feed["record_count"])
    return feed
