"""Phase 2 auth tests — JWT verification, role enforcement, RLS posture."""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app

# ---------- helpers ----------

_TEST_USER_ID = str(uuid4())
_TEST_ORG_ID = str(uuid4())


def _make_token(
    sub: str = _TEST_USER_ID,
    email: str = "test@example.com",
    expired: bool = False,
) -> str:
    """Mint a valid Supabase-shaped JWT for testing."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iat": now - 60,
        "exp": (now - 120) if expired else (now + 3600),
        "role": "authenticated",
    }
    return pyjwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_profile(role: str = "customer", org_id: str | None = _TEST_ORG_ID):
    """Return a mock for _load_profile that returns the given role."""
    profile = {"role": role, "organization_id": org_id}
    return patch("app.auth._load_profile", new_callable=AsyncMock, return_value=profile)


# ---------- 1. Unauthenticated → 401 ----------

@pytest.mark.anyio
async def test_no_token_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for path in ["/assessments/", "/findings/", "/reports/", "/admin/status"]:
            r = await c.get(path)
            assert r.status_code == 401, f"{path} should be 401 without token"


@pytest.mark.anyio
async def test_invalid_token_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/assessments/", headers=_auth_header("garbage.token.here"))
        assert r.status_code == 401


@pytest.mark.anyio
async def test_expired_token_returns_401():
    token = _make_token(expired=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/assessments/", headers=_auth_header(token))
        assert r.status_code == 401


# ---------- 2. Wrong role → 403 ----------

@pytest.mark.anyio
async def test_customer_cannot_access_admin():
    token = _make_token()
    with _mock_profile("customer"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/admin/status", headers=_auth_header(token))
            assert r.status_code == 403


@pytest.mark.anyio
async def test_sme_cannot_access_admin():
    token = _make_token()
    with _mock_profile("sme"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/admin/status", headers=_auth_header(token))
            assert r.status_code == 403


# ---------- 3. Correct role → 200 ----------

@pytest.mark.anyio
async def test_customer_can_access_assessments():
    token = _make_token()
    with _mock_profile("customer"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/assessments/", headers=_auth_header(token))
            assert r.status_code == 200


@pytest.mark.anyio
async def test_sme_can_access_findings():
    token = _make_token()
    with _mock_profile("sme"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/findings/", headers=_auth_header(token))
            assert r.status_code == 200


@pytest.mark.anyio
async def test_admin_can_access_admin():
    token = _make_token()
    with _mock_profile("admin"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/admin/status", headers=_auth_header(token))
            assert r.status_code == 200


@pytest.mark.anyio
async def test_admin_can_access_all_routes():
    token = _make_token()
    with _mock_profile("admin"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            for path in ["/assessments/", "/findings/", "/reports/", "/admin/status"]:
                r = await c.get(path, headers=_auth_header(token))
                assert r.status_code == 200, f"Admin should access {path}"


# ---------- 4. Health remains public ----------

@pytest.mark.anyio
async def test_health_is_public():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health")
        assert r.status_code == 200


# ---------- 5. RLS posture — anon key cannot bypass ----------

@pytest.mark.anyio
async def test_rls_blocks_anon_read_on_risk_finding():
    """The anon key with no JWT should get zero rows from RLS-protected tables."""
    import httpx as real_httpx

    anon_headers = {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {settings.supabase_anon_key}",
        "Prefer": "count=exact",
    }
    async with real_httpx.AsyncClient(timeout=10) as client:
        for table in ["risk_finding", "report_snapshot", "derived_data_item"]:
            r = await client.get(
                f"{settings.supabase_url}/rest/v1/{table}?select=*&limit=1",
                headers=anon_headers,
            )
            # RLS should either return 0 rows or a permission error
            if r.status_code == 200:
                assert len(r.json()) == 0, (
                    f"Anon key should see 0 rows from RLS-protected {table}, "
                    f"got {len(r.json())}"
                )


# ---------- 6. Service-role key bypasses RLS ----------

@pytest.mark.anyio
async def test_service_key_bypasses_rls():
    """The service-role key should be able to read RLS-protected tables."""
    import httpx as real_httpx

    from app.db import get_service_headers

    headers = {**get_service_headers(), "Prefer": "count=exact"}
    async with real_httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{settings.supabase_url}/rest/v1/risk_finding?select=*&limit=0",
            headers=headers,
        )
        # Service key should get through (status 200/206), even if 0 rows
        assert r.status_code in (200, 206)
