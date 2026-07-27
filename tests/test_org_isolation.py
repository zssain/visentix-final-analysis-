"""F10 cross-tenant isolation tests (Stage-3 Workstream C4).

Proves a `customer` cannot read another organization's data via the API — the
primary org-isolation control is application-level (the frontend never queries
Supabase directly; every read goes through these service-role-backed routes).
Each test targets a gap the RLS audit found and fixed.
"""

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app

MINE = str(uuid4())
OTHER = str(uuid4())


def _token(role="customer", org=MINE):
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": org},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


def _hdr(role="customer", org=MINE):
    return {"Authorization": f"Bearer {_token(role, org)}"}


# ── reports: cross-tenant report + PDF blocked ───────────────

@pytest.mark.anyio
async def test_customer_cannot_read_other_orgs_report():
    import app.routers.reports as R
    transport = ASGITransport(app=app)
    with patch.object(R, "assessment_org_id", return_value=OTHER):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/some-assessment", headers=_hdr("customer"))
    assert r.status_code == 403
    assert "not permitted" in r.json()["detail"].lower()


@pytest.mark.anyio
async def test_customer_cannot_export_other_orgs_pdf():
    import app.routers.reports as R
    transport = ASGITransport(app=app)
    with patch.object(R, "assessment_org_id", return_value=OTHER):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/some-assessment/pdf", headers=_hdr("customer"))
    assert r.status_code == 403


@pytest.mark.anyio
async def test_admin_not_blocked_by_ownership_check():
    """assert_customer_owns is a no-op for admin/sme (they oversee all orgs)."""
    import app.routers.reports as R
    # Foreign org, but admin → ownership check must not 403 (it may 404/200 later).
    transport = ASGITransport(app=app)
    with patch.object(R, "assessment_org_id", return_value=OTHER), \
         patch.object(R, "_load_stored_report", return_value={"ok": True}):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/some-assessment", headers=_hdr("admin", org=OTHER))
    assert r.status_code == 200


# ── explain: cross-tenant blocked ────────────────────────────

@pytest.mark.anyio
async def test_customer_cannot_explain_other_orgs_assessment():
    import app.routers.explain as E
    transport = ASGITransport(app=app)
    with patch.object(E, "customer_can_view", return_value=(True, "")), \
         patch.object(E, "_sb_get", return_value=[{"notice_id": "n1", "organization_id": OTHER}]):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/n1/explain?type=score&key=f002", headers=_hdr("customer"))
    assert r.status_code == 403


# ── list_assessments: customer query is org-filtered ─────────

@pytest.mark.anyio
async def test_list_assessments_filters_customer_by_org():
    import app.routers.assessments as A
    seen = {}

    class _Resp:
        status_code = 200
        def json(self): return []

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        seen["filters"] = filters
        return _Resp()

    transport = ASGITransport(app=app)
    with patch.object(A, "supabase_rest_get", _get):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.get("/assessments/", headers=_hdr("customer"))
    assert f"organization_id=eq.{MINE}" in seen["filters"]

    with patch.object(A, "supabase_rest_get", _get):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.get("/assessments/", headers=_hdr("admin"))
    assert seen["filters"] == ""  # admin → platform-wide


# ── dashboard-stats: customer queries scoped to org ──────────

@pytest.mark.anyio
async def test_dashboard_stats_scopes_customer_queries():
    import app.routers.findings as F
    paths = []

    def _sb(path):
        paths.append(path)
        return []

    transport = ASGITransport(app=app)
    with patch.object(F, "_sb_get", _sb):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/findings/dashboard-stats", headers=_hdr("customer"))
    assert r.status_code == 200
    # every data query for a customer carries the org filter
    data_paths = [p for p in paths if p.startswith(("derived_data_item", "risk_finding",
                                                     "report_snapshot", "privacy_notice"))]
    assert data_paths, "expected data queries"
    assert all(f"organization_id=eq.{MINE}" in p for p in data_paths)


@pytest.mark.anyio
async def test_dashboard_stats_customer_without_org_gets_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # customer token with organization_id explicitly None
        now = int(time.time())
        tok = pyjwt.encode({"sub": "u", "aud": "authenticated", "iat": now - 60,
                            "exp": now + 3600, "app_role": "customer",
                            "organization_id": None},
                           settings.supabase_jwt_secret, algorithm="HS256")
        r = await c.get("/findings/dashboard-stats", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["assessment_count"] == 0
    assert r.json()["overall_score"] is None
