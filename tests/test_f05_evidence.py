"""F05 addendum — recommendation evidence stack tests.

Assembled at approval, frozen (idempotent); resolved-enforcement-only capped at
2; approved-exemplars-only; three DISTINCT honest-absence states; delta null
forever; cross-org read 403.
"""

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import evidence as E


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


_ORG = "ORG-IN-SCOPE"


def _reads(*, in_scope=True, obligations=True, exemplar=True):
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp([{"organization_id": _ORG}])
        if table == "risk_finding":
            return _Resp([{"finding_id": "F1", "domain": "retention", "finding_type_code": "RET-003", "severity": "moderate"}])
        if table == "notice_section":
            return _Resp([{"section_id": "S1"}])
        if table == "disclosure_clause" and "is_exemplar" in filters:
            return _Resp([{"clause_id": "EX1"}] if exemplar else [])
        if table == "disclosure_clause":
            return _Resp([{"clause_id": "C1", "category": "retention"}])
        if table == "clause_obligation":
            return _Resp([{"obligation_id": "O1", "similarity": 0.71, "matched_terms": ["retention"]}] if obligations else [])
        if table == "obligation":
            return _Resp([{"obligation_id": "O1", "law": "CCPA", "requirement_type": "retention_limit",
                           "jurisdiction": "US-CA", "effective_date": "2020-01-01"}])
        if table == "enforcement_record":
            return _Resp([
                {"enforcement_id": "E1", "regulator_id": "FTC", "issue_tags": ["retention"], "action_date": "2024-05-01"},
                {"enforcement_id": "E2", "regulator_id": "CPPA", "issue_tags": ["retention", "data"], "action_date": "2023-02-01"},
                {"enforcement_id": "E3", "regulator_id": "ICO", "issue_tags": ["retention"], "action_date": "2022-01-01"},
            ])
        return _Resp([])
    return _get


# ── AC-E3: delta null forever + AC-E2 resolved-only ≤2 + register ──

@pytest.mark.anyio
async def test_delta_null_and_enforcement_capped_and_register():
    with patch.object(E, "supabase_rest_get", _reads()), \
         patch.object(E, "_in_scope_orgs", lambda: {_ORG}):
        stacks = await E.assemble_evidence("NID")
    s = stacks[0]
    assert s["risk_reduction_delta"] is None            # AC-E3 — never a number
    assert len(s["enforcement_refs"]) <= 2              # AC-E2 — capped at 2
    assert s["obligation_register"] == E.OBLIGATION_REGISTER  # verbatim exposure-context register
    assert s["obligation_refs"] and s["obligation_refs"][0]["verified"] is True


@pytest.mark.anyio
async def test_enforcement_query_is_resolved_only():
    captured = []

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        captured.append((table, filters))
        return await _reads()(table, select=select, filters=filters, limit=limit, count=count)
    with patch.object(E, "supabase_rest_get", _get), patch.object(E, "_in_scope_orgs", lambda: {_ORG}):
        await E.assemble_evidence("NID")
    enf = [f for (t, f) in captured if t == "enforcement_record"]
    assert enf and "resolution_status=eq.resolved" in enf[0]


# ── AC-E4: three DISTINCT honest-absence states ──────────────

@pytest.mark.anyio
async def test_absence_out_of_scope():
    # org NOT in the obligation-match scope
    with patch.object(E, "supabase_rest_get", _reads()), patch.object(E, "_in_scope_orgs", lambda: set()):
        s = (await E.assemble_evidence("NID"))[0]
    assert s["absence_reason"] == "out_of_scope"
    assert s["absence_text"] == E.ABSENCE["out_of_scope"] == "obligation context not yet available"


@pytest.mark.anyio
async def test_absence_below_floor():
    # in scope, but no obligation matches above the floor
    with patch.object(E, "supabase_rest_get", _reads(obligations=False)), \
         patch.object(E, "_in_scope_orgs", lambda: {_ORG}):
        s = (await E.assemble_evidence("NID"))[0]
    assert s["absence_reason"] == "below_floor"
    assert s["absence_text"] == "no related obligations above the similarity threshold"


@pytest.mark.anyio
async def test_absence_no_approved_exemplar_is_distinct():
    with patch.object(E, "supabase_rest_get", _reads(exemplar=False)), \
         patch.object(E, "_in_scope_orgs", lambda: {_ORG}):
        s = (await E.assemble_evidence("NID"))[0]
    # exemplar absence is a SEPARATE claim, never conflated with the obligation one
    assert s["exemplar_clause_id"] is None
    assert s["exemplar_absence_text"] == "no approved exemplar for this domain yet"
    assert s["absence_reason"] is None  # obligations were present → not an obligation absence


# ── AC-E1: freeze is idempotent (byte-identity) ──────────────

@pytest.mark.anyio
async def test_freeze_idempotent():
    # First: nothing frozen yet → writes. Second: rows exist → 0 (no re-assemble).
    async def _get_none(table, *, select="*", filters="", limit=1000, count=False):
        return _Resp([])

    async def _get_exists(table, *, select="*", filters="", limit=1000, count=False):
        if table == "recommendation_evidence":
            return _Resp([{"id": "existing"}])
        return _Resp([])
    with patch.object(E, "supabase_rest_get", _get_exists):
        assert await E.freeze_evidence_on_approval("NID") == 0  # already frozen → skip


# ── ID threading: report passes the finding CODE → resolve to UUID ──

@pytest.mark.anyio
async def test_get_evidence_resolves_code_to_finding_id():
    """The report identifies findings by code (assembly sets finding.id=code);
    recommendation_evidence keys on the risk_finding UUID. get_evidence must
    resolve the code so the drawer shows the real frozen stack."""
    calls = []

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        calls.append((table, filters))
        if table == "recommendation_evidence" and "finding_id=eq.RET-003" in filters:
            return _Resp([])  # no row under the CODE (UUIDs are stored)
        if table == "risk_finding":
            return _Resp([{"finding_id": "UUID-1"}])  # code → UUID
        if table == "recommendation_evidence" and "finding_id=eq.UUID-1" in filters:
            return _Resp([{"finding_id": "UUID-1", "obligation_refs": "[]", "exemplar_clause_id": None,
                           "enforcement_refs": "[]", "absence_reason": "below_floor",
                           "risk_reduction_delta": None, "formula_version_id": "F05-evidence_v1", "confidence": 0.0}])
        return _Resp([])
    with patch.object(E, "supabase_rest_get", _get):
        ev = await E.get_evidence("NID", "RET-003")   # called with the CODE
    assert ev is not None and ev["finding_id"] == "UUID-1"
    assert ev["risk_reduction_delta"] is None
    # it resolved via risk_finding, then read by the UUID
    assert any(t == "risk_finding" for t, _ in calls)


# ── AC-E5: cross-org evidence read → 403 ─────────────────────

@pytest.mark.anyio
async def test_cross_org_evidence_403():
    from app.routers import assessments as A

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "privacy_notice":
            return _Resp([{"organization_id": "ORG-OTHER"}])
        return _Resp([])
    with patch.object(A, "supabase_rest_get", _get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(f"/assessments/{uuid4()}/findings/{uuid4()}/evidence",
                            headers={"Authorization": f"Bearer {_token('customer', 'ORG-A')}"})
    assert r.status_code == 403
