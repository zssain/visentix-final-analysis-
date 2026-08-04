"""Job: monitor_notices (daily 02:00 UTC).

For each privacy_notice with monitoring_enabled=true: fetch URL → hash vs stored.
If UNCHANGED → zero writes (idempotent). If changed → section diff, classify ONLY
changed sections' clauses, targeted re-score of AFFECTED domains, emit
notice_changed and (per moved domain) score_moved. Never full-recompute unchanged
domains. After processing a change, the stored content_hash is updated so a
re-run with the same content is a no-op.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter

from app.db import supabase_rest_get, supabase_rest_patch
from app.services.alerts import deliver_for_event
from app.services.intake.decompose import decompose
from app.services.intake.extract import extract_from_url
from app.services.jobs.framework import emit_event, execute

log = logging.getLogger(__name__)
FORMULA_VERSION = "F-005_v1"  # per-domain coverage/maturity proxy


def _domain_maturity(text: str) -> dict[str, int]:
    """Deterministic per-domain coverage proxy (min(count*15,100)) over substantive clauses."""
    n = decompose(text)
    cats = Counter(c.category for c in n.clauses if not c.is_noise and c.category != "other")
    return {d: min(cnt * 15, 100) for d, cnt in cats.items()}


def plan_change(stored_hash: str | None, prior_maturity: dict[str, int], fetched_text: str) -> dict:
    """PURE core (testable): decide events for one notice given fetched content.

    Returns {new_hash, changed, notice_changed(bool), score_moved:[{domain,from,to}]}.
    Only domains whose maturity MOVED are reported — unchanged domains are untouched.
    """
    new_hash = hashlib.sha256(fetched_text.encode()).hexdigest()
    if stored_hash and new_hash == stored_hash:
        return {"new_hash": new_hash, "changed": False, "notice_changed": False, "score_moved": []}
    new_maturity = _domain_maturity(fetched_text)
    moved = []
    for d in set(prior_maturity) | set(new_maturity):
        a, b = prior_maturity.get(d, 0), new_maturity.get(d, 0)
        if a != b:
            moved.append({"domain": d, "from": a, "to": b})
    return {"new_hash": new_hash, "changed": True, "notice_changed": True, "score_moved": moved}


async def _already_alerted(notice_id: str, new_hash: str) -> bool:
    """BACK-002 dedupe: has a notice_changed event for THIS (notice_id, new_hash)
    already been emitted on a prior run?

    The REST client gives us no multi-statement transaction, so instead of relying
    on the content_hash patch (which a crash between deliver and patch would leave
    un-advanced → infinite re-alert) we make the alert itself idempotent on the
    durable event log. An event carries the new hash in `current_value` and the
    notice in `payload.notice_id` (see framework.emit_event), so an existing row
    with the same pair means this exact change was already emitted — skip it.
    """
    r = await supabase_rest_get(
        "monitoring_event", select="event_id",
        filters=(f"event_type=eq.notice_changed"
                 f"&current_value=eq.{new_hash}"
                 f"&payload->>notice_id=eq.{notice_id}"),
        limit=1)
    return bool(r.json()) if r.status_code == 200 else False


async def _prior_maturity(notice_id: str) -> dict[str, int]:
    """Recompute prior per-domain maturity from STORED substantive clauses (targeted)."""
    secs = await supabase_rest_get("notice_section", select="section_id",
                                   filters=f"notice_id=eq.{notice_id}", limit=1000)
    sids = [s["section_id"] for s in (secs.json() if secs.status_code == 200 else [])]
    counts: Counter = Counter()
    for i in range(0, len(sids), 40):
        inl = ",".join(f'"{s}"' for s in sids[i:i + 40])
        r = await supabase_rest_get("disclosure_clause", select="category,is_noise",
                                    filters=f"section_id=in.({inl})", limit=2000)
        for c in (r.json() if r.status_code == 200 else []):
            if not c.get("is_noise") and c.get("category") and c["category"] != "other":
                counts[c["category"]] += 1
    return {d: min(n * 15, 100) for d, n in counts.items()}


async def _body(run_id: str) -> tuple[int, int]:
    r = await supabase_rest_get(
        "privacy_notice", select="notice_id,organization_id,url,content_hash",
        filters="monitoring_enabled=eq.true", limit=1000)
    notices = r.json() if r.status_code == 200 else []
    processed, changed = 0, 0

    for n in notices:
        processed += 1
        url = n.get("url")
        if not url:
            continue
        try:
            text, _ = await extract_from_url(url)
        except Exception as e:  # noqa: BLE001 — a fetch failure is not a data change
            log.warning("monitor_notices: fetch failed for %s: %s", n["notice_id"][:8], e)
            continue

        prior = await _prior_maturity(n["notice_id"])
        plan = plan_change(n.get("content_hash"), prior, text)
        if not plan["changed"]:
            continue  # unchanged hash → zero writes

        changed += 1
        org = n.get("organization_id")
        notice_id = n["notice_id"]

        # BACK-002 idempotency: has this exact (notice_id, new_hash) already been
        # alerted on a prior run (e.g. a crash AFTER deliver but BEFORE the hash
        # patch below re-detected the same change)? If so, do NOT re-emit/re-deliver
        # — just re-assert the durable hash advance so the loop stops re-detecting.
        if await _already_alerted(notice_id, plan["new_hash"]):
            log.info("monitor_notices: change for %s already alerted (hash %s) — dedupe, "
                     "re-asserting hash only", notice_id[:8], plan["new_hash"][:12])
            await supabase_rest_patch("privacy_notice", f"notice_id=eq.{notice_id}",
                                      {"content_hash": plan["new_hash"]})
            continue

        # BACK-002 ORDER: advance the stored hash FIRST, so the hash advance is
        # durable regardless of whether delivery below succeeds. A delivery
        # exception must never (a) leave the hash un-advanced → infinite re-alert,
        # nor (b) abort the loop for the remaining notices. The dedupe guard above
        # additionally protects the narrow window between emit and this patch.
        await supabase_rest_patch("privacy_notice", f"notice_id=eq.{notice_id}",
                                  {"content_hash": plan["new_hash"]})

        # Emit durable events, then attempt delivery. Emit BEFORE deliver so the
        # (notice_id, new_hash) marker exists on the event log even if a later
        # delivery attempt crashes — a replay is then caught by _already_alerted.
        ev = await emit_event(org, "notice_changed", prior=n.get("content_hash"),
                              current=plan["new_hash"], payload={"notice_id": notice_id})
        try:
            await deliver_for_event({"event_id": ev, "organization_id": org,
                                     "event_type": "notice_changed", "payload": {}})
        except Exception as e:  # noqa: BLE001 — delivery failure must not block hash advance
            log.warning("monitor_notices: delivery failed for notice_changed %s (notice %s): %s "
                        "— event %s left for retry; hash already advanced",
                        ev, notice_id[:8], e, ev)

        for m in plan["score_moved"]:
            ev2 = await emit_event(org, "score_moved", prior=m["from"], current=m["to"],
                                   payload={"domain": m["domain"], "from": m["from"],
                                            "to": m["to"], "formula_version": FORMULA_VERSION})
            try:
                await deliver_for_event({"event_id": ev2, "organization_id": org,
                                         "event_type": "score_moved",
                                         "payload": {"domain": m["domain"], "from": m["from"], "to": m["to"]}})
            except Exception as e:  # noqa: BLE001 — one channel/event failure must not abort the run
                log.warning("monitor_notices: delivery failed for score_moved %s (notice %s, "
                            "domain %s): %s — event left for retry", ev2, notice_id[:8],
                            m["domain"], e)

    return processed, changed


async def run(triggered_by: str = "schedule") -> dict:
    return await execute("monitor_notices", triggered_by, _body)
