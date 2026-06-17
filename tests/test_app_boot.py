"""Phase 2 boot tests — verify the app starts and /health works."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_health_returns_200():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_health_has_required_keys():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    data = r.json()
    assert "status" in data
    assert "row_counts" in data
    assert "ollama" in data
    assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_health_row_counts_are_ints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    counts = r.json()["row_counts"]
    assert isinstance(counts, dict)
    assert len(counts) > 0
    for table, count in counts.items():
        assert isinstance(count, int), f"{table} count is {type(count)}, not int"


@pytest.mark.anyio
async def test_health_no_secrets_in_response():
    """Ensure /health response never leaks secrets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    body = r.text
    assert "sb_" not in body
    assert "eyJ" not in body
    assert "sk-" not in body
    assert "postgresql://" not in body


@pytest.mark.anyio
async def test_stub_routers_require_auth():
    """Verify protected routers reject unauthenticated requests (not 404)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ["/assessments/", "/findings/", "/reports/", "/admin/status"]:
            r = await client.get(path)
            assert r.status_code == 401, f"{path} should be 401 without auth"
