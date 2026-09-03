"""F26 content-free request auditing and caller-only history."""

import asyncio
import time
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


ORG = str(uuid4())
USER = str(uuid4())


def _headers(*, org: str | None = ORG, user: str = USER) -> dict[str, str]:
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user,
            "aud": "authenticated",
            "iat": now - 5,
            "exp": now + 300,
            "app_role": "customer",
            "organization_id": org,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class _Response:
    status_code = 200

    def __init__(self, body=None):
        self._body = [] if body is None else body

    def json(self):
        return self._body


@pytest.mark.anyio
async def test_authenticated_request_writes_one_content_free_event():
    captured = []

    async def _post(table, payload, **kwargs):
        captured.append((table, payload))
        return _Response()

    with patch("app.middleware.audit.supabase_rest_post", _post), \
         patch(
             "app.routers.account.supabase_rest_get",
             new_callable=AsyncMock,
             return_value=_Response(),
         ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/account/audit?offset=20&secret=must-not-appear",
                headers={**_headers(), "X-Debug-Token": "must-not-appear"},
            )
        await asyncio.sleep(0)

    assert response.status_code == 200
    assert len(captured) == 1
    table, event = captured[0]
    assert table == "audit_event"
    assert event["organization_id"] == ORG
    assert event["user_id"] == USER
    assert event["action"] == "GET /account/audit"
    assert event["resource_type"] == "account"
    UUID(event["request_id"])
    serialized = repr(event)
    for forbidden in ("must-not-appear", "query", "body", "password", "token"):
        assert forbidden not in serialized.lower()


@pytest.mark.anyio
async def test_audit_history_is_always_caller_and_org_scoped():
    seen = {}

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        seen.update(table=table, filters=filters, limit=limit)
        return _Response([{"id": "event-1", "action": "GET /reports/{assessment_id}"}])

    with patch("app.routers.account.supabase_rest_get", _get), \
         patch("app.middleware.audit.supabase_rest_post", new_callable=AsyncMock, return_value=_Response()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/account/audit?limit=25&offset=10", headers=_headers())
        await asyncio.sleep(0)

    assert response.status_code == 200
    assert seen["table"] == "audit_event"
    assert f"organization_id=eq.{ORG}" in seen["filters"]
    assert f"user_id=eq.{USER}" in seen["filters"]
    assert "order=at.desc" in seen["filters"]
    assert seen["limit"] == 25


@pytest.mark.anyio
async def test_customer_without_org_gets_empty_without_database_read():
    with patch("app.routers.account.supabase_rest_get", new_callable=AsyncMock) as get_rows:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/account/audit", headers=_headers(org=None))
        await asyncio.sleep(0)
    assert response.status_code == 200
    assert response.json()["items"] == []
    get_rows.assert_not_awaited()


@pytest.mark.anyio
async def test_audit_write_failure_never_changes_response():
    async def _fail(*args, **kwargs):
        raise RuntimeError("database unavailable")

    with patch("app.middleware.audit.supabase_rest_post", _fail):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/account/audit", headers=_headers(org=None))
        await asyncio.sleep(0)
    assert response.status_code == 200
