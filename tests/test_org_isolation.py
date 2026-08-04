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


# ── SEC-001 / SEC-003: cross-tenant contract on org-filtered collection routes ──
# The permanent guard that converts SEC-001 from a fixed bug into a closed bug
# class. For every customer-scoped LIST route we assert: (1) customer A's query
# carries ONLY A's org filter, (2) never B's, (3) admin/sme are platform-wide,
# and (4) a customer with no org gets an empty result WITHOUT issuing a query
# (never a platform-wide read — that was the leak). To extend coverage to a new
# route, add it to CAPTURE_ROUTES below.

ORG_A = str(uuid4())
ORG_B = str(uuid4())


def _hdr_org(org):
    return {"Authorization": f"Bearer {_token('customer', org)}"}


async def _capture_findings(headers):
    """Drive GET /findings/ and return the list of PostgREST paths it issued."""
    import app.routers.findings as F
    paths: list[str] = []
    transport = ASGITransport(app=app)
    with patch.object(F, "_sb_get", lambda p: paths.append(p) or []):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/findings/", headers=headers)
    return r, paths


async def _capture_assessments(headers):
    """Drive GET /assessments/ and return the PostgREST filter strings it issued."""
    import app.routers.assessments as A

    class _Resp:
        status_code = 200
        def json(self): return []

    filters_list: list[str] = []

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        filters_list.append(filters)
        return _Resp()

    transport = ASGITransport(app=app)
    with patch.object(A, "supabase_rest_get", _get):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/assessments/", headers=headers)
    return r, filters_list


# CAPTURE_ROUTES: (id, capture_fn, needle_fmt) — needle_fmt.format(org=...) is the
# per-org marker that must appear only for the caller's own org.
CAPTURE_ROUTES = [
    ("findings_list", _capture_findings, "organization_id=eq.{org}"),
    ("assessments_list", _capture_assessments, "organization_id=eq.{org}"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("route_id,capture,needle_fmt", CAPTURE_ROUTES)
@pytest.mark.parametrize("caller_org", [ORG_A, ORG_B])
async def test_customer_list_scoped_to_own_org(route_id, capture, needle_fmt, caller_org):
    other_org = ORG_B if caller_org == ORG_A else ORG_A
    r, queries = await capture(_hdr_org(caller_org))
    assert r.status_code == 200, f"{route_id} returned {r.status_code}"
    assert queries, f"{route_id} issued no query to inspect"
    mine = needle_fmt.format(org=caller_org)
    theirs = needle_fmt.format(org=other_org)
    assert all(mine in q for q in queries), f"{route_id}: caller org filter missing: {queries}"
    assert all(theirs not in q for q in queries), f"{route_id}: leaked other-org filter: {queries}"


@pytest.mark.anyio
@pytest.mark.parametrize("route_id,capture,needle_fmt", CAPTURE_ROUTES)
async def test_admin_list_platform_wide(route_id, capture, needle_fmt):
    r, queries = await capture(_hdr("admin", org=ORG_A))
    assert r.status_code == 200
    # admin/sme oversee all orgs → no org filter on any query
    assert all("organization_id=eq." not in q for q in queries), \
        f"{route_id}: admin query was unexpectedly org-scoped: {queries}"


@pytest.mark.anyio
async def test_findings_list_no_org_customer_returns_empty_without_query():
    """A customer with no org must get [] and MUST NOT issue a platform-wide query."""
    import app.routers.findings as F
    called = {"n": 0}
    transport = ASGITransport(app=app)
    now = int(time.time())
    tok = pyjwt.encode({"sub": "u", "aud": "authenticated", "iat": now - 60,
                        "exp": now + 3600, "app_role": "customer",
                        "organization_id": None},
                       settings.supabase_jwt_secret, algorithm="HS256")
    with patch.object(F, "_sb_get", lambda p: called.__setitem__("n", called["n"] + 1) or []):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/findings/", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == []
    assert called["n"] == 0, "no-org customer must not issue any risk_finding query"


# ── FUNC-001: SME review endpoints reject a customer role ─────────
# The workbench writes decisions via these routes; a customer must never reach
# them (role boundary — extends the Phase-1 tenant work).

@pytest.mark.anyio
@pytest.mark.parametrize("method,path,body", [
    ("get", "/review/queue", None),
    ("get", "/review/some-assessment", None),
    ("post", "/review/some-assessment/approve", None),
    ("post", "/review/finding/a1/f1", {"action": "confirm"}),
])
async def test_customer_rejected_from_sme_review_endpoints(method, path, body):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        if method == "get":
            r = await c.get(path, headers=_hdr("customer"))
        else:
            r = await c.post(path, json=body, headers=_hdr("customer"))
    assert r.status_code == 403, f"{method} {path} should 403 for a customer"
