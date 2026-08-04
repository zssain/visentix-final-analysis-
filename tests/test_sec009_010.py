"""SEC-009 (peppered HMAC partner key storage, migration-safe verify) +
SEC-010 (typed request bodies with 422 on bad/missing fields).

Client + JWT pattern mirrors tests/test_org_isolation.py. Partner routes are
role-gated to partner_admin/admin; quarterly.build + eval.gold-label to
admin/sme.
"""

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

import app.services.partner as P
from app.config import settings
from app.main import app

PARTNER = str(uuid4())


def _token(role="partner_admin", org=None, partner=PARTNER):
    now = int(time.time())
    claims = {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
              "app_role": role, "organization_id": org, "partner_id": partner}
    return pyjwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def _hdr(role="partner_admin", partner=PARTNER):
    return {"Authorization": f"Bearer {_token(role, partner=partner)}"}


# ── SEC-009: hashing scheme ──────────────────────────────────

def test_hmac_hash_deterministic_and_differs_from_legacy():
    plaintext = "vsx_example_key_123"
    with patch.object(settings, "partner_key_pepper", "s3cr3t-pepper"):
        h1 = P._hmac_hash_key(plaintext)
        h2 = P._hmac_hash_key(plaintext)
    assert h1 == h2, "HMAC must be deterministic for the same key + pepper"
    legacy = P._legacy_hash_key(plaintext)
    assert h1 != legacy, "HMAC digest must differ from the unsalted sha256"
    # sanity: pepper actually participates
    with patch.object(settings, "partner_key_pepper", "different"):
        assert P._hmac_hash_key(plaintext) != h1


def test_hash_key_prefers_hmac_when_pepper_set_else_legacy():
    plaintext = "vsx_scheme_selection"
    with patch.object(settings, "partner_key_pepper", "pep"):
        assert P._hash_key(plaintext) == P._hmac_hash_key(plaintext)
    with patch.object(settings, "partner_key_pepper", ""):
        assert P._hash_key(plaintext) == P._legacy_hash_key(plaintext)


@pytest.mark.anyio
async def test_verify_accepts_legacy_sha256_stored_key():
    """A key stored with the OLD unsalted sha256 still verifies after SEC-009."""
    plaintext = "vsx_legacy_key"
    legacy_digest = P._legacy_hash_key(plaintext)
    captured = {}

    class _Resp:
        status_code = 200
        def __init__(self, rows): self._rows = rows
        def json(self): return self._rows

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        captured["filters"] = filters
        # DB holds the legacy digest.
        if legacy_digest in filters:
            return _Resp([{"id": "k1", "partner_id": PARTNER, "revoked_at": None}])
        return _Resp([])

    async def _patch(*a, **k):
        return _Resp([])

    with patch.object(settings, "partner_key_pepper", "pep"), \
         patch.object(P, "supabase_rest_get", _get), \
         patch.object(P, "supabase_rest_patch", _patch):
        out = await P.verify_api_key(plaintext)
    assert out == {"partner_id": PARTNER, "api_key_id": "k1"}
    # verify must offer BOTH candidate digests when a pepper is set
    assert legacy_digest in captured["filters"]
    with patch.object(settings, "partner_key_pepper", "pep"):
        assert P._hmac_hash_key(plaintext) in captured["filters"]


@pytest.mark.anyio
async def test_verify_accepts_new_hmac_stored_key():
    """A key stored with the NEW HMAC scheme verifies."""
    plaintext = "vsx_new_key"

    class _Resp:
        status_code = 200
        def __init__(self, rows): self._rows = rows
        def json(self): return self._rows

    def _make_get(hmac_digest):
        async def _get(table, *, select="*", filters="", limit=1000, count=False):
            if hmac_digest in filters:
                return _Resp([{"id": "k2", "partner_id": PARTNER, "revoked_at": None}])
            return _Resp([])
        return _get

    async def _patch(*a, **k):
        return _Resp([])

    with patch.object(settings, "partner_key_pepper", "pep"):
        hmac_digest = P._hmac_hash_key(plaintext)
        with patch.object(P, "supabase_rest_get", _make_get(hmac_digest)), \
             patch.object(P, "supabase_rest_patch", _patch):
            out = await P.verify_api_key(plaintext)
    assert out == {"partner_id": PARTNER, "api_key_id": "k2"}


# ── SEC-010: typed bodies reject bad/missing required fields (422) ──

@pytest.mark.anyio
async def test_create_workspace_missing_field_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # missing client_org entirely
        r = await c.post("/partner/workspaces", json={"name": "Acme"}, headers=_hdr())
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_api_key_bad_type_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # label must be a string, not a list
        r = await c.post("/partner/api-keys", json={"label": ["not", "a", "string"]},
                         headers=_hdr())
    assert r.status_code == 422


@pytest.mark.anyio
async def test_quarterly_build_missing_quarter_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/admin/quarterly/build", json={}, headers=_hdr(role="admin"))
    assert r.status_code == 422


@pytest.mark.anyio
async def test_gold_label_missing_required_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # missing clause_id + gold_domain
        r = await c.post("/eval/gold-label", json={"verdict": "correct"},
                         headers=_hdr(role="admin"))
    assert r.status_code == 422


# Model-level 422 sanity (independent of routing/role gates).

def test_models_reject_missing_required():
    from pydantic import ValidationError
    from app.routers.partner import CreateWorkspaceIn
    from app.routers.quarterly import BuildIn
    from app.routers.eval import GoldLabelIn

    for model, bad in [
        (CreateWorkspaceIn, {"name": "Acme"}),          # no client_org
        (BuildIn, {}),                                   # no quarter
        (GoldLabelIn, {"verdict": "correct"}),           # no clause_id/gold_domain
    ]:
        with pytest.raises(ValidationError):
            model(**bad)
