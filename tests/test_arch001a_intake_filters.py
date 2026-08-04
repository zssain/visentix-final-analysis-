"""ARCH-001A — industry + state-law filters are CONSUMED, not just stored.

The acceptance bar is behavioural: changing a filter must change the downstream
result. Tests 1–2 prove the engine consumes the values (pure functions on the
real config); the rest prove intake writes them with honest provenance, validates
them, and serves the real vocabulary.
"""

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

import app.routers.assessments as A
from app.config import settings
from app.main import app
from app.services import intake_options as iopt
from app.services.profiling.live_profile import compute_ic, compute_org_profile

CLAUSES = [
    {"category": "data_sharing", "clause_type": "sharing"},
    {"category": "retention", "clause_type": "retention"},
    {"category": "consumer_rights", "clause_type": "rights"},
]


def _org(industry, jurisdictions):
    return {
        "organization_id": str(uuid4()), "name": "Acme", "industry": industry,
        "size": "large", "geography": "US", "jurisdiction_presence": jurisdictions,
    }


# ── 1. Industry is consumed (changes IC / industry_id → benchmark cohort key) ──

def test_industry_changes_industry_id_and_cohort_key():
    retail = compute_org_profile(_org("retail", ["US-CA"]), CLAUSES)
    health = compute_org_profile(_org("healthcare", ["US-CA"]), CLAUSES)
    assert retail.industry_id != health.industry_id
    assert retail.industry_id == "IND-01" and health.industry_id == "IND-04"
    # build_population keys the cohort on industry_id (population.py:32), so a
    # different industry_id means a different cohort — the value is consumed.


# ── 2. Jurisdictions are consumed (change RSS state_exposure) ──

def test_jurisdiction_changes_rss():
    ca = compute_org_profile(_org("retail", ["US-CA"]), CLAUSES)   # CA weight 1.0
    co = compute_org_profile(_org("retail", ["US-CO"]), CLAUSES)   # CO weight 0.65
    assert ca.rss != co.rss, "RSS must reflect the selected jurisdiction"


def test_jurisdiction_none_uses_broad_default():
    """No jurisdiction → falls back to the broad default, distinct from a real state."""
    ca = compute_org_profile(_org("retail", ["US-CA"]), CLAUSES)
    default = compute_org_profile(_org("retail", []), CLAUSES)  # → [geography or US] → _default
    assert ca.rss != default.rss


# ── 3–4. Validation vocabulary (the engine's real value sets) ──

def test_valid_and_invalid_values():
    assert iopt.is_valid_industry("retail")
    assert iopt.is_valid_industry("healthcare")
    assert iopt.is_valid_industry("unknown")          # honest sentinel is valid
    assert not iopt.is_valid_industry("banana")
    assert iopt.is_valid_jurisdiction("US-CA")
    assert not iopt.is_valid_jurisdiction("US-XX")
    assert not iopt.is_valid_jurisdiction("_default")  # sentinel not selectable


def test_intake_options_payload():
    opts = iopt.intake_options()
    inds = {o["value"] for o in opts["industries"]}
    jurs = {o["value"] for o in opts["jurisdictions"]}
    assert {"retail", "healthcare", "financial_services"} <= inds
    assert "US-CA" in jurs and "US-CO" in jurs
    assert "_default" not in jurs
    assert opts["unknown_industry"] == "unknown"


# ── 5. Intake WRITES real industry + provenance + jurisdictions ──

@pytest.mark.anyio
async def test_apply_filters_writes_real_industry_and_provenance():
    captured = {}

    async def fake_patch(table, filters, payload):
        captured["table"] = table
        captured["payload"] = payload

    with patch.object(A, "supabase_rest_patch", fake_patch):
        changed = await A._apply_intake_filters("org-1", "retail", ["US-CA", "US-CO"])
    assert changed is True
    p = captured["payload"]
    assert p["industry"] == "retail"
    assert p["industry_id"] == "IND-01"
    assert p["industry_source"] == "user_provided"
    assert p["jurisdiction_presence"] == ["US-CA", "US-CO"]


@pytest.mark.anyio
async def test_apply_filters_unknown_is_honest_not_defaulted():
    captured = {}

    async def fake_patch(table, filters, payload):
        captured["payload"] = payload

    with patch.object(A, "supabase_rest_patch", fake_patch):
        changed = await A._apply_intake_filters("org-1", "unknown", [])
    assert changed is True
    assert captured["payload"]["industry"] == "unknown"
    assert captured["payload"]["industry_source"] == "unknown"
    assert "industry_id" not in captured["payload"]  # never a fabricated real industry


@pytest.mark.anyio
async def test_apply_filters_blank_does_not_touch_org():
    called = {"n": 0}

    async def fake_patch(*a, **k):
        called["n"] += 1

    with patch.object(A, "supabase_rest_patch", fake_patch):
        changed = await A._apply_intake_filters("org-1", None, [])
    assert changed is False
    assert called["n"] == 0  # blank ≠ overwrite


# ── 4 (endpoint). Invalid value → 422, not a silent pass-through ──

def _hdr(role="customer", org=None):
    now = int(time.time())
    tok = pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": org or str(uuid4())},
        settings.supabase_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [
    ("industry", "banana"),
    ("jurisdictions", "US-XX"),
])
async def test_invalid_filter_rejected_422(field, value):
    async def fake_find(key):
        return None
    transport = ASGITransport(app=app)
    with patch.object(A.intake_jobs, "find_by_idempotency_key", fake_find), \
         patch.object(A.asyncio, "create_task", lambda coro: coro.close()):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/assessments/async",
                             data={"text": "A notice.", field: value}, headers=_hdr("customer"))
    assert r.status_code == 422


@pytest.mark.anyio
async def test_config_intake_options_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/config/intake-options", headers=_hdr("customer"))
    assert r.status_code == 200
    body = r.json()
    assert any(o["value"] == "retail" for o in body["industries"])
    assert any(o["value"] == "US-CA" for o in body["jurisdictions"])
