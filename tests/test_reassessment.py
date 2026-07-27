"""Admin trigger-assessment tests (F09 — M-14).

Verifies the batch re-assessment orchestration (run-id + per-notice results),
input validation, and admin gating — without running the real scoring pipeline
or touching the network.
"""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import reassessment

_ORG = str(uuid4())
_NID = str(uuid4())


def _token(role="admin", org=_ORG):
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": org},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


class _Resp:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.text = data, status_code, ""

    def json(self):
        return self._data


class _FakeHttp:
    """Stand-in for httpx.AsyncClient used for the ingestion_run writes."""
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        return _Resp({}, 201)

    async def patch(self, *a, **k):
        return _Resp({}, 204)


def _reads(notices, sections, clauses):
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp(notices)
        if table == "notice_section":
            return _Resp(sections)
        if table == "disclosure_clause":
            return _Resp(clauses)
        return _Resp([])
    return _get


@pytest.mark.anyio
async def test_requires_scope():
    with pytest.raises(ValueError):
        await reassessment.trigger_reassessment()


@pytest.mark.anyio
async def test_no_notices_resolves_raises():
    with patch.object(reassessment, "supabase_rest_get", _reads([], [], [])):
        with pytest.raises(ValueError):
            await reassessment.trigger_reassessment(org_id=_ORG)


@pytest.mark.anyio
async def test_batch_scores_and_records_run():
    notices = [{"notice_id": _NID, "organization_id": _ORG}]
    sections = [{"section_id": "SEC1", "title": "T", "section_type": "general",
                 "sequence": 0, "extracted_text": "hello"}]
    clauses = [{"clause_id": "C1", "section_id": "SEC1", "raw_text": "x",
                "normalized_text": "x", "category": "consumer_rights",
                "ambiguity_score": 0.1, "readability_score": 0.5,
                "nlp_confidence": 0.8, "domain_id": "CR", "clause_type": "",
                "transparency_score": 0.0, "classifier_version": "v2"}]

    fake_score = AsyncMock(return_value={"summary": {"snapshot_id": "SNAP-1"}})

    with patch.object(reassessment, "supabase_rest_get", _reads(notices, sections, clauses)), \
         patch.object(reassessment, "score_and_persist", fake_score), \
         patch.object(reassessment.httpx, "AsyncClient", _FakeHttp):
        out = await reassessment.trigger_reassessment(org_id=_ORG, triggered_by="admin@x")

    assert out["scored"] == 1
    assert out["failed"] == 0
    assert out["outcome"] == "ok"
    assert out["run_id"]
    assert out["notices"][0]["snapshot_id"] == "SNAP-1"
    fake_score.assert_awaited_once()


@pytest.mark.anyio
async def test_skips_notice_with_no_clauses():
    notices = [{"notice_id": _NID, "organization_id": _ORG}]
    sections = [{"section_id": "SEC1", "title": "T", "section_type": "general",
                 "sequence": 0, "extracted_text": "hello"}]
    with patch.object(reassessment, "supabase_rest_get", _reads(notices, sections, [])), \
         patch.object(reassessment.httpx, "AsyncClient", _FakeHttp):
        out = await reassessment.trigger_reassessment(org_id=_ORG)
    assert out["scored"] == 0
    assert out["notices"][0]["status"] == "skipped_no_clauses"


@pytest.mark.anyio
async def test_route_requires_admin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/admin/trigger-assessment", json={"org_id": _ORG},
            headers={"Authorization": f"Bearer {_token(role='customer')}"},
        )
    assert r.status_code == 403


@pytest.mark.anyio
async def test_route_empty_body_is_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/admin/trigger-assessment", json={},
            headers={"Authorization": f"Bearer {_token(role='admin')}"},
        )
    assert r.status_code == 400
