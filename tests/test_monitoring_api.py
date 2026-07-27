"""Monitoring API tests (F07 — M-06/M-07/M-08).

Covers the trend / events / alerts routes across empty, baseline, and populated
states, F10 org isolation, and the WS1 hard rules:
- deltas come from the versioned F-012 formula (never fabricated),
- unresolved enforcement never surfaces on alerts,
- every scored payload carries a formula_version + VCI.

The Supabase layer is patched with an in-memory dispatcher, so tests are
deterministic and hit no network.
"""

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import monitoring

_ORG = str(uuid4())
_OTHER_ORG = str(uuid4())


def _token(role="customer", org=_ORG):
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": org},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


class _Resp:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.headers = {}
        self.text = ""

    def json(self):
        return self._data


def _dispatcher(tables):
    """Build an AsyncMock side-effect that returns rows per (table, filter substr)."""
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        for (t, needle), rows in tables.items():
            if t == table and (needle == "" or needle in filters):
                return _Resp(rows)
        return _Resp([])
    return _get


# ── trend (M-06 / F-012) ─────────────────────────────────────


@pytest.mark.anyio
async def test_trend_no_history():
    with patch.object(monitoring, "supabase_rest_get", _dispatcher({("derived_data_item", ""): []})):
        out = await monitoring.get_trend(_ORG)
    assert out["state"] == "no_history"
    assert out["series"] == []
    assert out["deltas"] is None


@pytest.mark.anyio
async def test_trend_baseline_single_snapshot():
    rows = [
        {"object_type": "overall_intelligence", "score": 40.0, "confidence_score": 0.6,
         "source_snapshot_id": "S1", "generated_at": "2026-07-01T00:00:00+00:00",
         "formula_version_id": "F-010_v1"},
    ]
    with patch.object(monitoring, "supabase_rest_get", _dispatcher({("derived_data_item", ""): rows})):
        out = await monitoring.get_trend(_ORG)
    assert out["state"] == "baseline_established"
    assert len(out["series"]) == 1
    assert out["deltas"] is None  # never a fabricated trend from one point
    assert out["series"][0]["vci"] == 60.0  # 0.6 * 100


@pytest.mark.anyio
async def test_trend_populated_delta_from_f012():
    rows = [
        {"object_type": "overall_intelligence", "score": 50.0, "confidence_score": 0.7,
         "source_snapshot_id": "S1", "generated_at": "2026-07-01T00:00:00+00:00"},
        {"object_type": "regulatory_exposure", "score": 80.0, "confidence_score": 0.7,
         "source_snapshot_id": "S1", "generated_at": "2026-07-01T00:00:00+00:00"},
        {"object_type": "overall_intelligence", "score": 40.0, "confidence_score": 0.7,
         "source_snapshot_id": "S2", "generated_at": "2026-07-15T00:00:00+00:00"},
        {"object_type": "regulatory_exposure", "score": 60.0, "confidence_score": 0.7,
         "source_snapshot_id": "S2", "generated_at": "2026-07-15T00:00:00+00:00"},
    ]
    with patch.object(monitoring, "supabase_rest_get", _dispatcher({("derived_data_item", ""): rows})):
        out = await monitoring.get_trend(_ORG)
    assert out["state"] == "populated"
    ov = out["deltas"]["overall"]
    # F-012 = (40-50)/50 * 100 = -20.0
    assert ov["from"] == 50.0 and ov["to"] == 40.0
    assert ov["delta_pct"] == -20.0
    assert ov["formula_version_id"] == "F-012_v1"
    # domain delta present + versioned
    reg = out["deltas"]["domains"]["regulatory_exposure"]
    assert reg["delta_pct"] == -25.0  # (60-80)/80*100
    assert reg["formula_version_id"] == "F-012_v1"


# ── events (M-07) ────────────────────────────────────────────


@pytest.mark.anyio
async def test_events_empty_when_no_org_domain():
    tables = {
        ("organization", ""): [{"domain": None}],
        ("privacy_notice", ""): [],
    }
    with patch.object(monitoring, "supabase_rest_get", _dispatcher(tables)):
        out = await monitoring.get_events(_ORG)
    assert out["state"] == "no_events"
    assert out["events"] == []


@pytest.mark.anyio
async def test_events_scoped_and_type_normalized():
    tables = {
        ("organization", ""): [{"domain": "acme.com"}],
        ("privacy_notice", ""): [],
        ("source_record", ""): [
            {"source_id": "SRC-1", "url": "https://www.acme.com/privacy"},
            {"source_id": "SRC-2", "url": "https://other.com/privacy"},  # not ours
        ],
        ("monitoring_event", ""): [
            {"event_id": "E1", "trigger_type": "hash_change", "source_id": "SRC-1",
             "prior_value": "h1", "current_value": "h2", "material_change_indicator": 1,
             "severity": "medium", "ts": "2026-07-10T00:00:00+00:00"},
        ],
    }
    with patch.object(monitoring, "supabase_rest_get", _dispatcher(tables)):
        out = await monitoring.get_events(_ORG)
    assert out["state"] == "populated"
    assert len(out["events"]) == 1
    ev = out["events"][0]
    assert ev["type"] == "notice_changed"       # normalized from hash_change
    assert ev["raw_trigger_type"] == "hash_change"
    assert ev["source_url"] == "https://www.acme.com/privacy"
    assert "prior_hash" in ev and "from" not in ev  # notice change → no score from→to


@pytest.mark.anyio
async def test_events_score_move_carries_from_to():
    tables = {
        ("organization", ""): [{"domain": "acme.com"}],
        ("privacy_notice", ""): [],
        ("source_record", ""): [{"source_id": "SRC-1", "url": "https://acme.com/x"}],
        ("monitoring_event", ""): [
            {"event_id": "E2", "trigger_type": "score_moved", "source_id": "SRC-1",
             "prior_value": "41", "current_value": "38", "material_change_indicator": 1,
             "severity": "medium", "ts": "2026-07-11T00:00:00+00:00"},
        ],
    }
    with patch.object(monitoring, "supabase_rest_get", _dispatcher(tables)):
        out = await monitoring.get_events(_ORG)
    ev = out["events"][0]
    assert ev["type"] == "score_moved"
    assert ev["from"] == "41" and ev["to"] == "38"


# ── alerts (M-08 / F-013) ────────────────────────────────────


@pytest.mark.anyio
async def test_alerts_never_surface_unresolved_enforcement():
    tables = {
        ("derived_data_item", "alert_escalation"): [
            {"derived_data_item_id": "A1", "score": 42.0, "confidence_score": 0.6,
             "source_snapshot_id": "S1", "source_lineage": {"risk_increase": 0.3},
             "formula_version_id": "F-013_v1", "generated_at": "2026-07-01T00:00:00+00:00"},
        ],
        # Only resolved rows are returned because the service filters on
        # resolution_status=eq.resolved; assert the filter is applied.
        ("enforcement_record", "resolution_status=eq.resolved"): [
            {"enforcement_id": "ENF-1", "entity_name": "Acme", "regulator_id": "FTC",
             "official_url": "http://x", "action_date": "2025-01-01",
             "resolution_status": "resolved", "domains": ["other"]},
        ],
    }
    with patch.object(monitoring, "supabase_rest_get", _dispatcher(tables)):
        out = await monitoring.get_alerts(_ORG)
    assert out["state"] == "populated"
    a = out["alerts"][0]
    assert a["escalation_score"] == 42.0
    assert a["formula_version_id"] == "F-013_v1"
    assert a["vci"] == 60.0
    # Every attached enforcement ref is resolved — never unresolved.
    assert a["enforcement_refs"]
    assert all(e["resolution_status"] == "resolved" for e in a["enforcement_refs"])


@pytest.mark.anyio
async def test_alerts_empty_state():
    with patch.object(monitoring, "supabase_rest_get", _dispatcher({("derived_data_item", "alert_escalation"): []})):
        out = await monitoring.get_alerts(_ORG)
    assert out["state"] == "no_alerts"
    assert out["alerts"] == []


# ── auth + org isolation (F10) ───────────────────────────────


@pytest.mark.anyio
async def test_trend_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/monitoring/trend")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_customer_cannot_read_other_org():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            f"/api/monitoring/trend?org_id={_OTHER_ORG}",
            headers={"Authorization": f"Bearer {_token(role='customer')}"},
        )
    assert r.status_code == 403


@pytest.mark.anyio
async def test_sme_requires_org_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            "/api/monitoring/trend",
            headers={"Authorization": f"Bearer {_token(role='sme', org=None)}"},
        )
    assert r.status_code == 400


@pytest.mark.anyio
async def test_customer_reads_own_org_end_to_end():
    rows = [
        {"object_type": "overall_intelligence", "score": 40.0, "confidence_score": 0.6,
         "source_snapshot_id": "S1", "generated_at": "2026-07-01T00:00:00+00:00"},
    ]
    transport = ASGITransport(app=app)
    with patch.object(monitoring, "supabase_rest_get", _dispatcher({("derived_data_item", ""): rows})):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(
                "/api/monitoring/trend",
                headers={"Authorization": f"Bearer {_token(role='customer')}"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["org_id"] == _ORG
    assert body["state"] == "baseline_established"
