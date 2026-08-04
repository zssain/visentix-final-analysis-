"""BACK-002 — monitor_notices alert idempotency + durable hash advance.

Regression guards for the reorder in app/services/jobs/monitor_notices.py:

  1. crash-after-delivery replay: a run that delivered an alert but crashed before
     the content_hash patch (so the notice is re-detected as "changed" next run)
     must NOT re-deliver the SAME (notice_id, new_hash) — the durable event log
     dedupe (`_already_alerted`) catches it, and the hash is re-asserted.

  2. delivery exception: if deliver_for_event raises, the content_hash advance
     must STILL happen (durable, ordered first) and the loop must not abort — no
     infinite re-alert, and the event is left on the log for a retry mechanism.

All DB / delivery is mocked; ZERO real IO. We patch exactly the names imported
into the monitor_notices module: supabase_rest_get, supabase_rest_patch,
emit_event, deliver_for_event, extract_from_url, _prior_maturity.
"""

from __future__ import annotations

import hashlib

import pytest

from app.services.jobs import monitor_notices


class _Resp:
    def __init__(self, data=None, status_code=200):
        self.status_code, self._data = status_code, data if data is not None else []

    def json(self):
        return self._data


NOTICE_ID = "11111111-1111-1111-1111-111111111111"
ORG_ID = "22222222-2222-2222-2222-222222222222"
NEW_TEXT = "brand new privacy notice body that differs from the stored hash"
NEW_HASH = hashlib.sha256(NEW_TEXT.encode()).hexdigest()
OLD_HASH = hashlib.sha256(b"the previous stored notice body").hexdigest()


def _install(monkeypatch, *, event_log, patches, delivered, deliver_side_effect=None):
    """Wire monitor_notices to an in-memory fake DB + delivery layer.

    - event_log: list of stored monitoring_event rows (mutated as events emit),
      also drives the _already_alerted dedupe GET.
    - patches: list of (filters, payload) recording every content_hash patch.
    - delivered: list recording each deliver_for_event call.
    """

    async def fake_extract(url):
        return NEW_TEXT, {}

    async def fake_prior(notice_id):
        return {}

    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp([{
                "notice_id": NOTICE_ID, "organization_id": ORG_ID,
                "url": "https://example.test/privacy", "content_hash": OLD_HASH,
            }])
        if table == "monitoring_event":
            # Emulate the dedupe query: event_type=notice_changed &
            # current_value=eq.<hash> & payload->>notice_id=eq.<id>
            hit = [
                e for e in event_log
                if e.get("event_type") == "notice_changed"
                and e.get("current_value") == NEW_HASH
                and (e.get("payload") or {}).get("notice_id") == NOTICE_ID
            ]
            return _Resp(hit[:1])
        return _Resp([])

    async def fake_patch(table, filters, payload):
        if table == "privacy_notice":
            patches.append((filters, payload))
        return _Resp(status_code=204)

    async def fake_emit(organization_id, event_type, *, prior=None, current=None,
                        payload=None, severity=None, source_id=None):
        eid = f"ev-{len(event_log)}"
        event_log.append({
            "event_id": eid, "event_type": event_type, "organization_id": organization_id,
            "current_value": None if current is None else str(current), "payload": payload,
        })
        return eid

    calls = {"n": 0}

    async def fake_deliver(event, **kw):
        delivered.append(event)
        if deliver_side_effect is not None:
            calls["n"] += 1
            deliver_side_effect(calls["n"], event)
        return [{"status": "sent"}]

    monkeypatch.setattr(monitor_notices, "extract_from_url", fake_extract)
    monkeypatch.setattr(monitor_notices, "_prior_maturity", fake_prior)
    monkeypatch.setattr(monitor_notices, "supabase_rest_get", fake_get)
    monkeypatch.setattr(monitor_notices, "supabase_rest_patch", fake_patch)
    monkeypatch.setattr(monitor_notices, "emit_event", fake_emit)
    monkeypatch.setattr(monitor_notices, "deliver_for_event", fake_deliver)


@pytest.mark.anyio
async def test_crash_after_delivery_replay_does_not_realert(monkeypatch):
    """Simulate a prior run that emitted + delivered but crashed before the hash
    patch: the event log already holds (notice_id, NEW_HASH), and privacy_notice
    still reports OLD_HASH (so plan_change sees it as changed). The next run must
    dedupe: NO new delivery, NO new event, and the hash IS re-asserted."""
    # Pre-seed the log as if the previous run had already alerted this change.
    event_log = [{
        "event_id": "ev-prev", "event_type": "notice_changed", "organization_id": ORG_ID,
        "current_value": NEW_HASH, "payload": {"notice_id": NOTICE_ID},
    }]
    patches: list = []
    delivered: list = []
    _install(monkeypatch, event_log=event_log, patches=patches, delivered=delivered)

    processed, changed = await monitor_notices._body("run-replay")

    assert processed == 1
    assert changed == 1                       # still detected as a content change
    assert delivered == []                    # BUT no duplicate alert delivered
    # No NEW notice_changed event emitted (log unchanged from the pre-seed).
    assert len(event_log) == 1
    # Hash advance re-asserted so future runs stop re-detecting.
    assert patches == [(f"notice_id=eq.{NOTICE_ID}", {"content_hash": NEW_HASH})]


@pytest.mark.anyio
async def test_delivery_exception_still_advances_hash_and_no_infinite_realert(monkeypatch):
    """deliver_for_event raises → the content_hash advance must STILL be persisted
    (ordered first + independent of delivery), the run must not abort, and the
    event stays on the durable log so a replay is deduped (no infinite re-alert)."""
    event_log: list = []
    patches: list = []
    delivered: list = []

    def boom(n, event):
        raise RuntimeError("smtp down")

    _install(monkeypatch, event_log=event_log, patches=patches, delivered=delivered,
             deliver_side_effect=boom)

    # Run 1: delivery blows up, but must not raise out of _body.
    processed, changed = await monitor_notices._body("run-1")
    assert processed == 1 and changed == 1
    # Hash was advanced despite the delivery failure.
    assert (f"notice_id=eq.{NOTICE_ID}", {"content_hash": NEW_HASH}) in patches
    # Delivery WAS attempted (not silently dropped) — every emitted event's
    # delivery raised, but each was caught individually so the run completed.
    assert len(delivered) >= 1
    assert any(e.get("event_type") == "notice_changed" for e in delivered)
    # The durable notice_changed marker is on the log for the dedupe guard/retry.
    assert any(e["event_type"] == "notice_changed" and e["current_value"] == NEW_HASH
               for e in event_log)

    # Run 2 (replay with the SAME still-old stored hash — worst case): the dedupe
    # guard must catch the existing (notice_id, NEW_HASH) event → no re-alert.
    delivered.clear()
    patches.clear()
    events_before = len(event_log)
    processed2, changed2 = await monitor_notices._body("run-2")
    assert processed2 == 1
    assert delivered == []                    # NOT re-alerted
    assert len(event_log) == events_before    # no new event emitted
    assert patches == [(f"notice_id=eq.{NOTICE_ID}", {"content_hash": NEW_HASH})]


@pytest.mark.anyio
async def test_hash_persisted_before_delivery_is_attempted(monkeypatch):
    """Ordering invariant: the content_hash patch is issued BEFORE deliver_for_event
    runs, so a delivery-time crash can never leave the hash un-advanced."""
    event_log: list = []
    patches: list = []
    order: list = []

    async def fake_extract(url):
        return NEW_TEXT, {}

    async def fake_prior(notice_id):
        return {}

    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp([{"notice_id": NOTICE_ID, "organization_id": ORG_ID,
                           "url": "https://example.test/privacy", "content_hash": OLD_HASH}])
        return _Resp([])  # no prior event → not deduped

    async def fake_patch(table, filters, payload):
        if table == "privacy_notice":
            order.append("patch")
        return _Resp(status_code=204)

    async def fake_emit(organization_id, event_type, **kw):
        order.append(f"emit:{event_type}")
        return f"ev-{len(order)}"

    async def fake_deliver(event, **kw):
        order.append(f"deliver:{event.get('event_type')}")
        return [{"status": "sent"}]

    monkeypatch.setattr(monitor_notices, "extract_from_url", fake_extract)
    monkeypatch.setattr(monitor_notices, "_prior_maturity", fake_prior)
    monkeypatch.setattr(monitor_notices, "supabase_rest_get", fake_get)
    monkeypatch.setattr(monitor_notices, "supabase_rest_patch", fake_patch)
    monkeypatch.setattr(monitor_notices, "emit_event", fake_emit)
    monkeypatch.setattr(monitor_notices, "deliver_for_event", fake_deliver)

    await monitor_notices._body("run-order")

    # The hash patch happens before ANY deliver_for_event call.
    assert "patch" in order
    first_deliver = next((i for i, s in enumerate(order) if s.startswith("deliver")), None)
    assert first_deliver is not None
    assert order.index("patch") < first_deliver
