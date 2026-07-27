"""Formula-description endpoint tests (F05 — M-10)."""

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.routers import formulas


def _token(role="customer"):
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": str(uuid4())},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


class _Resp:
    def __init__(self, data):
        self._data, self.status_code, self.text = data, 200, ""

    def json(self):
        return self._data


@pytest.mark.anyio
async def test_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/formulas")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_returns_descriptions_map():
    rows = [
        {"formula_id": "F-002", "name": "Regulatory Exposure Score", "description": "plain english."},
        {"formula_id": "F-013", "name": "Alert Escalation", "description": "urgency."},
        {"formula_id": None, "name": "junk", "description": "skip"},  # skipped
    ]

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        return _Resp(rows)

    transport = ASGITransport(app=app)
    with patch.object(formulas, "supabase_rest_get", _get):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(
                "/api/formulas",
                headers={"Authorization": f"Bearer {_token()}"},
            )
    assert r.status_code == 200
    body = r.json()["formulas"]
    assert body["F-002"]["description"] == "plain english."
    assert body["F-013"]["name"] == "Alert Escalation"
    assert None not in body  # null formula_id skipped
