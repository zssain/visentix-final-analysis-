"""F19 — Bulk Screening tests.

Guards the MUST-NOTs and ACs: 201-row rejection; malformed URL fails alone
(job='partial'); tenancy (job invisible cross-org); VCI suppression in JSON and
CSV; export carries the draft-grade notice + ZERO verdict terms (guardrail
extended to the export); reassessment.py reuse (single scoring path, no forked
scorer); insufficient_profile mapping; draft-never-auto-approved; role gating;
the cross-tenant trap (a row matching an existing customer scores into a fresh
screening org, never the customer's); one-running-job-per-tenant 409.
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import bulk

_ORG = str(uuid4())
_OTHER = str(uuid4())


def _token(role="analyst", org=_ORG):
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
         "app_role": role, "organization_id": org},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


def _hdr(role="analyst", org=_ORG):
    return {"Authorization": f"Bearer {_token(role, org)}"}


class _Resp:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.text = data, status_code, ""

    def json(self):
        return self._data


# ── AC-6: single scoring path (no forked scorer) ─────────────

def test_single_scoring_path_reuses_reassessment_kernel():
    import app.services.reassessment as R
    # Bulk scores ONLY through the kernel; it defines no scorer of its own.
    assert bulk.trigger_reassessment is R.trigger_reassessment
    assert not hasattr(bulk, "score_and_persist"), "bulk must not import a second scoring path"
    assert not hasattr(bulk, "score_notice"), "bulk must not fork the scorer"


# ── AC-1: 201-row rejection ──────────────────────────────────

@pytest.mark.anyio
async def test_201_rows_rejected():
    rows = [{"org_name": f"o{i}", "notice_url": f"https://e{i}.example/p"} for i in range(201)]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/bulk/jobs", json={"label": "x", "rows": rows}, headers=_hdr())
    assert r.status_code == 400
    assert "max" in r.text.lower()


@pytest.mark.anyio
async def test_200_rows_accepted_returns_202():
    rows = [{"org_name": f"o{i}", "notice_url": f"https://e{i}.example/p"} for i in range(200)]
    transport = ASGITransport(app=app)
    with patch.object(bulk, "has_active_job", AsyncMock(return_value=False)), \
         patch.object(bulk, "create_job", AsyncMock(return_value="JOB-1")), \
         patch.object(bulk, "run_bulk_job", AsyncMock()):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/bulk/jobs", json={"rows": rows}, headers=_hdr())
    assert r.status_code == 202
    assert r.json()["bulk_job_id"] == "JOB-1"


# ── AC-9: role gating ────────────────────────────────────────

@pytest.mark.anyio
async def test_customer_forbidden():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/bulk/jobs", headers=_hdr(role="customer"))
    assert r.status_code == 403


@pytest.mark.anyio
async def test_analyst_allowed():
    transport = ASGITransport(app=app)
    with patch.object(bulk, "list_jobs", AsyncMock(return_value=[])):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/bulk/jobs", headers=_hdr(role="analyst"))
    assert r.status_code == 200


# ── AC-11: one running job per tenant ────────────────────────

@pytest.mark.anyio
async def test_second_job_while_running_is_409():
    rows = [{"org_name": "o", "notice_url": "https://e.example/p"}]
    transport = ASGITransport(app=app)
    with patch.object(bulk, "has_active_job", AsyncMock(return_value=True)), \
         patch.object(bulk, "create_job", AsyncMock()) as create:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/bulk/jobs", json={"rows": rows}, headers=_hdr())
    assert r.status_code == 409
    create.assert_not_awaited()  # no second job created


# ── AC-3: tenancy — job invisible cross-org ──────────────────

@pytest.mark.anyio
async def test_job_invisible_cross_org():
    # get_job filters on org_id — a foreign job returns no rows → 404, no leak.
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        return _Resp([])  # nothing matches the caller's org filter
    transport = ASGITransport(app=app)
    with patch.object(bulk, "supabase_rest_get", _get):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(f"/bulk/jobs/{uuid4()}", headers=_hdr())
    assert r.status_code == 404


# ── AC-2 / AC-7: per-row mapping (malformed / insufficient / ok) ──

@pytest.mark.anyio
async def test_malformed_url_fails_alone():
    row = {"org_name": "Acme", "notice_url": "not-a-url", "position": 0}
    out = await bulk._process_row(row, _ORG, "job8")
    assert out["status"] == "failed"
    assert "malformed" in out["error"].lower()


@pytest.mark.anyio
async def test_no_clauses_maps_to_insufficient_profile():
    fake_notice = SimpleNamespace(clauses=[])
    with patch.object(bulk, "is_direct_policy_url", return_value=True), \
         patch.object(bulk, "extract_from_url", AsyncMock(return_value=("text", "hash"))), \
         patch.object(bulk, "decompose", return_value=fake_notice), \
         patch.object(bulk, "classify_clauses", AsyncMock(return_value=(0, 0))):
        out = await bulk._process_row(
            {"org_name": "Acme", "notice_url": "https://acme.example/p", "position": 0}, _ORG, "job8")
    assert out["status"] == "insufficient_profile"
    assert out["assessment_id"] is None


@pytest.mark.anyio
async def test_kernel_skipped_no_clauses_maps_insufficient():
    fake_notice = SimpleNamespace(clauses=[object()])
    with patch.object(bulk, "is_direct_policy_url", return_value=True), \
         patch.object(bulk, "extract_from_url", AsyncMock(return_value=("t", "h"))), \
         patch.object(bulk, "decompose", return_value=fake_notice), \
         patch.object(bulk, "classify_clauses", AsyncMock(return_value=(1, 0))), \
         patch.object(bulk, "create_screening_org", AsyncMock(return_value="SORG")), \
         patch.object(bulk, "persist_notice", AsyncMock(return_value="NID")), \
         patch.object(bulk, "trigger_reassessment",
                      AsyncMock(return_value={"notices": [{"status": "skipped_no_clauses"}]})):
        out = await bulk._process_row(
            {"org_name": "Acme", "notice_url": "https://acme.example/p", "position": 0}, _ORG, "job8")
    assert out["status"] == "insufficient_profile"


# ── AC-10: cross-tenant trap — fresh screening org, never a customer's ──

@pytest.mark.anyio
async def test_cross_tenant_trap_scores_into_fresh_screening_org():
    """A row named like an existing customer must score into a FRESH screening
    org — never that customer's org record, and never via a name lookup."""
    captured = {}

    async def _fake_post(table, payload, **k):
        # create_screening_org ALWAYS inserts a brand-new organization row.
        if table == "organization":
            captured["org"] = payload
        return _Resp([], 201)

    async def _fake_get(*a, **k):
        # If create_screening_org ever tried a find-by-name lookup, this would
        # be the leak vector — assert it is never called for `organization`.
        captured["get_called_for"] = captured.get("get_called_for", []) + [a[0] if a else k.get("table")]
        return _Resp([])

    fake_notice = SimpleNamespace(clauses=[object()])
    persist_calls = {}

    async def _fake_persist(org_id, notice, **k):
        persist_calls["org_id"] = org_id  # the org the assessment lands under
        return "NID-fresh"

    with patch.object(bulk, "supabase_rest_post", _fake_post), \
         patch.object(bulk, "supabase_rest_get", _fake_get), \
         patch.object(bulk, "is_direct_policy_url", return_value=True), \
         patch.object(bulk, "extract_from_url", AsyncMock(return_value=("t", "h"))), \
         patch.object(bulk, "decompose", return_value=fake_notice), \
         patch.object(bulk, "classify_clauses", AsyncMock(return_value=(1, 0))), \
         patch.object(bulk, "persist_notice", _fake_persist), \
         patch.object(bulk, "trigger_reassessment",
                      AsyncMock(return_value={"notices": [{"status": "scored"}]})):
        out = await bulk._process_row(
            {"org_name": "ExistingCustomerCorp", "notice_url": "https://ec.example/p", "position": 3},
            _ORG, "job8")

    assert out["status"] == "succeeded"
    # A fresh org was created (new uuid), namespaced so it can't collide with a
    # customer's real org name/slug, and tagged to the bulk owner's tenant.
    assert captured["org"]["organization_id"]  # a NEW uuid, not resolved by name
    assert "screening" in captured["org"]["name"]
    assert captured["org"]["tenant_id"] == f"bulk:{_ORG}"
    # create_screening_org must NEVER read `organization` (no find-by-name → no leak).
    assert "organization" not in (captured.get("get_called_for") or [])
    # The assessment landed under the fresh screening org — not the customer's.
    assert persist_calls["org_id"] == captured["org"]["organization_id"]


# ── run_bulk_job: one good + one bad → 'partial' (AC-2 end-to-end) ──

@pytest.mark.anyio
async def test_run_bulk_job_partial_when_one_row_fails():
    rows = [
        {"id": "r1", "position": 0, "org_name": "Good", "notice_url": "https://good.example/p"},
        {"id": "r2", "position": 1, "org_name": "Bad", "notice_url": "not-a-url"},
    ]
    patched = {}

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "bulk_job_row":
            return _Resp(rows)
        if table == "bulk_job":
            return _Resp([{"org_id": _ORG}])
        return _Resp([])

    async def _patch(table, filters, payload):
        if table == "bulk_job" and "status" in payload and payload["status"] in ("completed", "partial", "failed"):
            patched["final"] = payload["status"]
        return _Resp({}, 204)

    async def _process(row, owner, job8):
        # good row succeeds; the malformed one fails (real url guard covered elsewhere)
        if row["org_name"] == "Good":
            return {"status": "succeeded", "assessment_id": "NID", "error": None}
        return {"status": "failed", "assessment_id": None, "error": "Malformed notice_url"}

    with patch.object(bulk, "supabase_rest_get", _get), \
         patch.object(bulk, "supabase_rest_patch", _patch), \
         patch.object(bulk, "_process_row", _process):
        await bulk.run_bulk_job("JOB-1")
    assert patched["final"] == "partial"


# ── AC-4 / AC-8: suppression + draft review_status in results ──

def _assemble_reads(*, suppress: bool):
    vci = {"score": 20 if suppress else 72, "suppress": suppress}
    payload = {"vci": vci, "cohort_size": 24, "relaxations": []}
    import json as _json

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "bulk_job":
            return _Resp([{"id": "JOB-1", "org_id": _ORG, "status": "completed"}])
        if table == "bulk_job_row":
            return _Resp([{"position": 0, "org_name": "Acme", "notice_url": "u",
                           "status": "succeeded", "assessment_id": "NID", "error": None}])
        if table == "report_snapshot":
            return _Resp([{"notice_id": "NID", "payload": _json.dumps(payload)}])
        if table == "risk_finding":
            return _Resp([{"notice_id": "NID", "finding_type_code": "TRK-007",
                           "domain": "tracking_cookies", "severity": "high", "score": 80.0}])
        if table == "derived_data_item":
            return _Resp([{"notice_id": "NID", "score": 66.0}])
        if table == "assessment_review":
            return _Resp([{"assessment_id": "NID", "status": "draft"}])
        return _Resp([])
    return _get


@pytest.mark.anyio
async def test_results_draft_and_unsuppressed():
    with patch.object(bulk, "supabase_rest_get", _assemble_reads(suppress=False)):
        out = await bulk.get_results("JOB-1", _ORG)
    row = out["results"][0]
    assert row["review_status"] == "draft"          # AC-8: never auto-approved
    assert row["overall"] == 66.0
    assert row["suppressed_reason"] is None
    tracking = next(c for c in row["domain_scores"] if c["domain"] == "tracking_cookies")
    assert tracking["score"] == 80.0
    assert len(row["domain_scores"]) == 8
    assert row["top_findings"][0]["code"] == "TRK-007"


@pytest.mark.anyio
async def test_results_suppressed_json():
    with patch.object(bulk, "supabase_rest_get", _assemble_reads(suppress=True)):
        out = await bulk.get_results("JOB-1", _ORG)
    row = out["results"][0]
    assert row["overall"] is None                    # AC-4: suppressed → null
    assert row["suppressed_reason"] == "low_confidence"
    assert all(c["score"] is None for c in row["domain_scores"])


# ── AC-5: export CSV — draft notice + zero verdict terms + suppressed cells ──

@pytest.mark.anyio
async def test_export_csv_notice_and_suppression_and_vocabulary():
    from app.services.guardrail import check_generated_prose

    with patch.object(bulk, "supabase_rest_get", _assemble_reads(suppress=True)):
        csv_text = await bulk.export_csv("JOB-1", _ORG)

    # Draft-grade notice line present.
    assert bulk.EXPORT_NOTICE in csv_text
    assert "not expert-reviewed" in csv_text
    # Suppressed cells are literal.
    assert "suppressed_low_confidence" in csv_text
    # Zero verdict terms anywhere in the export (guardrail extended to export).
    spans = check_generated_prose(csv_text)
    assert spans == [], f"verdict terms leaked into export: {[s.term for s in spans]}"


@pytest.mark.anyio
async def test_export_csv_unsuppressed_has_scores_and_notice():
    from app.services.guardrail import check_generated_prose
    with patch.object(bulk, "supabase_rest_get", _assemble_reads(suppress=False)):
        csv_text = await bulk.export_csv("JOB-1", _ORG)
    assert bulk.EXPORT_NOTICE in csv_text
    assert "Acme" in csv_text
    assert "66.0" in csv_text
    assert check_generated_prose(csv_text) == []


@pytest.mark.anyio
async def test_export_cross_org_is_none():
    async def _get(*a, **k):
        return _Resp([])  # foreign job → get_job None
    with patch.object(bulk, "supabase_rest_get", _get):
        assert await bulk.export_csv("JOB-1", _OTHER) is None
