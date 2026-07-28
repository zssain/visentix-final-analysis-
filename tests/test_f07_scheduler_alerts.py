"""F07 — scheduler jobs + alert delivery tests.

Guards the MUST-NOTs: threshold-unset suppresses with ZERO sends; admin job
endpoints are admin-only; org A never receives org B's events; jobs are
idempotent (unchanged hash = zero writes); webhook HMAC is verifiable.
"""

import json
import time

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import alerts
from app.services.jobs import monitor_notices, pull_regulators, refresh_benchmarks


class _Resp:
    def __init__(self, status_code=200, data=None):
        self.status_code, self._data, self.text = status_code, data or [], ""

    def json(self):
        return self._data


def _token(role="customer", org="ORG-A"):
    now = int(time.time())
    return pyjwt.encode({"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
                         "app_role": role, "organization_id": org},
                        settings.supabase_jwt_secret, algorithm="HS256")


def _hdr(role="customer", org="ORG-A"):
    return {"Authorization": f"Bearer {_token(role, org)}"}


# ── Pure cores (no DB) ───────────────────────────────────────

def test_monitor_unchanged_hash_zero_writes():
    import hashlib
    h = hashlib.sha256("hello world text".encode()).hexdigest()
    same = monitor_notices.plan_change(h, {}, "hello world text")
    assert same["changed"] is False and same["notice_changed"] is False and same["score_moved"] == []


def test_monitor_change_reports_only_moved_domains():
    plan = monitor_notices.plan_change(
        "old", {"data_sharing": 45, "retention": 30},
        "# S\n\nWe share your personal data with third party service providers and partners.")
    assert plan["changed"] is True
    moved = {m["domain"] for m in plan["score_moved"]}
    assert "retention" in moved            # retention dropped to 0 (no retention clause now)


def test_match_orgs_deterministic_intersection():
    weak = {"ORG-A": {"data_sharing", "retention"}, "ORG-B": {"ai_automated_decisions"}}
    out = pull_regulators.match_orgs({"data_sharing", "tracking_cookies"}, weak)
    assert out == [{"org_id": "ORG-A", "matched_domain": "data_sharing"}]


def test_diff_membership():
    assert refresh_benchmarks.diff_membership({"c1": 25}, {"c1": 27, "c2": 5}) == [
        {"cluster_id": "c1", "old_n": 25, "new_n": 27},
        {"cluster_id": "c2", "old_n": 0, "new_n": 5}]


def test_webhook_hmac_verifiable():
    body = {"event_id": "e1", "org_id": "o1", "type": "score_moved"}
    sig = alerts.sign_webhook("secret", body)
    assert alerts.sign_webhook("secret", body) == sig       # deterministic
    assert alerts.sign_webhook("other", body) != sig        # secret-bound


# ── Alert suppression (MUST NOT send when thresholds unset) ──

@pytest.mark.anyio
async def test_threshold_unset_suppresses_and_sends_nothing(monkeypatch):
    posted, calls = [], {"smtp": 0, "http": 0}

    async def fake_get_setting(k):
        return None  # F-013 thresholds UNSET

    async def fake_post(table, payload, **kw):
        posted.append(payload)
        return _Resp(201)

    monkeypatch.setattr(alerts, "get_setting", fake_get_setting)
    monkeypatch.setattr(alerts, "supabase_rest_post", fake_post)

    def smtp(*a, **k):
        calls["smtp"] += 1

    def http(*a, **k):
        calls["http"] += 1
        return 200

    ev = {"event_id": "e1", "organization_id": "o1", "event_type": "score_moved",
          "payload": {"from": 41, "to": 38, "domain": "data_sharing"}}
    res = await alerts.deliver_for_event(ev, smtp_send=smtp, http_post=http)

    assert calls == {"smtp": 0, "http": 0}                       # nothing sent
    assert res[0]["status"] == "suppressed_no_threshold"
    assert any(p["status"] == "suppressed_no_threshold" for p in posted)


@pytest.mark.anyio
async def test_delivers_only_to_events_own_org(monkeypatch):
    """When thresholds ARE set, delivery loads ONLY the event's org settings."""
    async def fake_get_setting(k):
        return json.dumps({"high": 0.0, "platform_min_severity": "low"})

    loaded_orgs = []

    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        loaded_orgs.append(filters)
        return _Resp(200, [{"org_id": "ORG-A", "email_to": "a@a.com",
                            "webhook_url": "https://hook.a", "webhook_secret": "sekret",
                            "min_severity": "low"}])

    async def fake_post(table, payload, **kw):
        return _Resp(201)

    monkeypatch.setattr(alerts, "get_setting", fake_get_setting)
    monkeypatch.setattr(alerts, "supabase_rest_get", fake_get)
    monkeypatch.setattr(alerts, "supabase_rest_post", fake_post)

    sent = {}

    def smtp(to, subj, body):
        sent["email"] = to

    def http(url, body, sig):
        sent["hook"] = (url, body, sig)
        return 200

    ev = {"event_id": "e1", "organization_id": "ORG-A", "event_type": "score_moved",
          "payload": {"from": 90, "to": 10, "domain": "data_sharing"}, "ts": "2026-07-28"}
    await alerts.deliver_for_event(ev, smtp_send=smtp, http_post=http)

    assert sent["email"] == "a@a.com"
    assert all("ORG-A" in f for f in loaded_orgs)               # only the event's org queried
    url, body, sig = sent["hook"]
    assert alerts.sign_webhook("sekret", body) == sig           # HMAC verifiable
    assert body["org_id"] == "ORG-A"


# ── Endpoint auth / scoping (MUST NOT expose to non-admin / cross-org) ─

@pytest.mark.anyio
async def test_admin_jobs_forbidden_for_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for path in ["/admin/jobs", "/admin/status"]:
            r = await c.get(path, headers=_hdr("customer"))
            assert r.status_code == 403, path
        r = await c.post("/admin/jobs/monitor_notices/run", headers=_hdr("customer"))
        assert r.status_code == 403


@pytest.mark.anyio
async def test_customer_cannot_read_other_orgs_notifications():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/orgs/ORG-B/notifications", headers=_hdr("customer", org="ORG-A"))
    assert r.status_code == 403


@pytest.mark.anyio
async def test_manual_trigger_creates_manual_job_run(monkeypatch):
    captured = {}

    async def fake_trigger(name, body, triggered_by="manual"):
        captured["name"], captured["triggered_by"] = name, triggered_by
        return "run-123"

    monkeypatch.setattr("app.services.jobs.framework.trigger_background", fake_trigger)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/admin/jobs/monitor_notices/run", headers=_hdr("admin"))
    assert r.status_code == 202
    assert r.json()["job_run_id"] == "run-123"
    assert captured["triggered_by"] == "manual"
