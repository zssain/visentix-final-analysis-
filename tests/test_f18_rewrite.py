"""F18 — Clause rewrite tests.

Guardrail + fabrication-verification are hard gates; any failure → exemplar
fallback (suggested_text=null). Watermark always present; clause_rewrite records
every field; cross-org 403.
"""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import rewrite as R


def _token(role="customer", org="ORG-A"):
    now = int(time.time())
    return pyjwt.encode({"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
                         "app_role": role, "organization_id": org},
                        settings.supabase_jwt_secret, algorithm="HS256")


class _Resp:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.text = data, status_code, ""

    def json(self):
        return self._data


_CLAUSE = "We keep your email address for as long as your account is active."
_EXEMPLAR = "We retain each category of personal information only for as long as needed for the stated purpose."


# ── Pure verification ────────────────────────────────────────

def test_verify_accepts_faithful_restructure():
    rw = "We retain your email address for as long as your account remains active."
    ok, _ = R.verify_rewrite(_CLAUSE, [_EXEMPLAR], rw)
    assert ok is True


def test_verify_rejects_new_recipient_purpose():
    # introduces "advertising partners" — a recipient absent from clause+exemplars
    rw = "We keep your email address and share it with advertising partners."
    ok, reason = R.verify_rewrite(_CLAUSE, [_EXEMPLAR], rw)
    assert ok is False and "advertising partners" in reason


def test_verify_rejects_new_number():
    rw = "We keep your email address for 730 days."
    ok, reason = R.verify_rewrite(_CLAUSE, [_EXEMPLAR], rw)
    assert ok is False and "number" in reason.lower()


def test_word_diff_deterministic():
    d1 = R.word_diff(_CLAUSE, _EXEMPLAR)
    d2 = R.word_diff(_CLAUSE, _EXEMPLAR)
    assert d1 == d2 and any(o["op"] == "add" for o in d1)


# ── generate_rewrite (LLM mocked) ────────────────────────────

def _reads():
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "disclosure_clause" and "is_exemplar" in filters:
            return _Resp([{"raw_text": _EXEMPLAR, "normalized_text": _EXEMPLAR}])
        if table == "disclosure_clause":
            return _Resp([{"raw_text": _CLAUSE, "normalized_text": _CLAUSE, "category": "retention"}])
        return _Resp([])
    return _get


@pytest.mark.anyio
async def test_ac1_happy_path_llm():
    good = "We retain your email address for as long as your account remains active."
    captured = {}

    async def _post(table, payload, **k):
        captured["row"] = payload
        return _Resp([], 201)
    with patch.object(R, "supabase_rest_get", _reads()), \
         patch.object(R, "supabase_rest_post", _post), \
         patch.object(R, "_llm_rewrite", AsyncMock(return_value=good)):
        out = await R.generate_rewrite("NID", "C1")
    assert out["status"] == "llm"
    assert out["suggested_text"] == good
    assert out["fallback_used"] is False
    assert out["watermark_text"] == R.WATERMARK
    # AC-5: every field recorded
    row = captured["row"]
    assert row["guardrail_passed"] and row["verification_passed"] and not row["fallback_used"]
    assert row["model_version"] and row["prompt_version"] == R.PROMPT_VERSION


@pytest.mark.anyio
async def test_ac2_fabrication_falls_back():
    # LLM invents a recipient not in clause∪exemplars
    fab = "We keep your email address and sell it to advertising partners."
    with patch.object(R, "supabase_rest_get", _reads()), \
         patch.object(R, "supabase_rest_post", AsyncMock(return_value=_Resp([], 201))), \
         patch.object(R, "_llm_rewrite", AsyncMock(return_value=fab)):
        out = await R.generate_rewrite("NID", "C1")
    assert out["status"] == "fallback"
    assert out["suggested_text"] is None
    assert out["verification_passed"] is False
    assert R.WATERMARK == out["watermark_text"]


@pytest.mark.anyio
async def test_ac3_banned_term_falls_back():
    banned = "This clause is non-compliant and violates the retention rule."
    with patch.object(R, "supabase_rest_get", _reads()), \
         patch.object(R, "supabase_rest_post", AsyncMock(return_value=_Resp([], 201))), \
         patch.object(R, "_llm_rewrite", AsyncMock(return_value=banned)):
        out = await R.generate_rewrite("NID", "C1")
    assert out["status"] == "fallback"
    assert out["guardrail_passed"] is False
    assert out["suggested_text"] is None


@pytest.mark.anyio
async def test_ac4_fallback_diffs_against_exemplar():
    with patch.object(R, "supabase_rest_get", _reads()), \
         patch.object(R, "supabase_rest_post", AsyncMock(return_value=_Resp([], 201))), \
         patch.object(R, "_llm_rewrite", AsyncMock(return_value=None)):  # LLM unavailable
        out = await R.generate_rewrite("NID", "C1")
    assert out["status"] == "fallback" and out["suggested_text"] is None
    assert out["diff"]  # clause vs best exemplar


# ── Endpoint org-scoping (AC-6) ──────────────────────────────

@pytest.mark.anyio
async def test_ac6_cross_org_403():
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp([{"organization_id": "ORG-OTHER"}])   # owned by another org
        return _Resp([])
    from app.routers import assessments as A
    with patch.object(A, "supabase_rest_get", _get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/assessments/{uuid4()}/clauses/{uuid4()}/rewrite",
                             headers={"Authorization": f"Bearer {_token('customer', 'ORG-A')}"})
    assert r.status_code == 403
