"""Offline contracts for the Supabase-backed application login cutover."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.authentication import LoginIdentity, authenticate_with_supabase


class _Response:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _SupabaseClient:
    def __init__(self, auth_response: _Response, profile_response: _Response):
        self.auth_response = auth_response
        self.profile_response = profile_response
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return self.auth_response

    async def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return self.profile_response


@pytest.mark.anyio
async def test_credential_verification_loads_profile_as_authority():
    user_id = str(uuid4())
    workspace_id = str(uuid4())
    client = _SupabaseClient(
        _Response(200, {"user": {"id": user_id, "email": "demo@example.com"}}),
        _Response(200, [{
            "role": "customer",
            "organization_id": workspace_id,
            "partner_id": None,
            "third_party_assessment_enabled": True,
        }]),
    )
    with patch("app.services.authentication.httpx.AsyncClient", return_value=client):
        identity = await authenticate_with_supabase(" Demo@Example.com ", "test-only-value")

    assert identity == LoginIdentity(
        user_id=user_id,
        email="demo@example.com",
        role="customer",
        organization_id=workspace_id,
        partner_id=None,
        third_party_assessment_enabled=True,
    )
    assert len(client.post_calls) == 1
    assert len(client.get_calls) == 1
    assert client.get_calls[0][1]["params"]["user_id"] == f"eq.{user_id}"


@pytest.mark.anyio
async def test_auth_rejection_never_attempts_profile_lookup():
    client = _SupabaseClient(_Response(400, {}), _Response(200, []))
    with patch("app.services.authentication.httpx.AsyncClient", return_value=client):
        identity = await authenticate_with_supabase("unknown@example.com", "test-only-value")
    assert identity is None
    assert client.get_calls == []


@pytest.mark.anyio
async def test_login_route_issues_application_session_from_verified_identity():
    import app.routers.auth as auth_router

    auth_router._rl_fail.clear()
    identity = LoginIdentity(
        user_id=str(uuid4()),
        email="demo@example.com",
        role="customer",
        organization_id=str(uuid4()),
        partner_id=None,
        third_party_assessment_enabled=True,
    )
    with patch(
        "app.routers.auth.authenticate_with_supabase",
        new_callable=AsyncMock,
        return_value=identity,
    ), patch("app.middleware.audit.supabase_rest_post", new_callable=AsyncMock):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/auth/login",
                json={"email": "demo@example.com", "password": "test-only-value"},
            )

    assert response.status_code == 200
    assert response.json()["user_id"] == identity.user_id
    assert response.json()["organization_id"] == identity.organization_id
    assert response.json()["access_token"]
    auth_router._rl_fail.clear()
