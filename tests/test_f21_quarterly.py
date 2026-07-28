"""F21 — Quarterly report tests.

Suppression (n<10 AND single-org dominance); gate failure blocks approval;
approved-snapshot immutability (service guard) + baseline zero-deltas;
methodology == stored metadata; public never serves drafts; PDF reproducibility;
rehearsal-origin orgs excluded; enforcement themes resolved-only; approval
reuses the expert-review permission (no bypass).
"""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import quarterly as Q


def _token(role="admin", org="ORG"):
    now = int(time.time())
    return pyjwt.encode({"sub": "u", "aud": "authenticated", "iat": now - 60, "exp": now + 3600,
                         "app_role": role, "organization_id": org},
                        settings.supabase_jwt_secret, algorithm="HS256")


def _hdr(role="admin"):
    return {"Authorization": f"Bearer {_token(role)}"}


class _Resp:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.text = data, status_code, ""

    def json(self):
        return self._data


def _data(*, n_orgs=25, industries=("retail", "healthcare"), clause_each=50,
          dominant_clause_org=None, resolved=None, dmi=62.0):
    """Build a compute_metrics data dict. Orgs split across `industries`."""
    pop = {f"o{i}" for i in range(n_orgs)}
    industry_of, snapshot_of, notice_of, dmi_rows, ai_rows, findings_of = {}, {}, {}, [], [], {}
    for i, o in enumerate(sorted(pop)):
        ind = industries[i % len(industries)]
        industry_of[o] = ind
        clauses = clause_each
        if dominant_clause_org == o:
            clauses = 100000
        snapshot_of[o] = {"scored_clause_count": clauses}
        notice_of[o] = {"jurisdictions": ["US"], "ai_relevant": True}
        dmi_rows.append({"org_id": o, "score": dmi, "confidence": 0.8})
        ai_rows.append({"org_id": o, "score": 40.0, "confidence": 0.7})
        findings_of[o] = {"TRK-007", "RET-003"}
    return {
        "population": pop, "industry_of": industry_of, "snapshot_of": snapshot_of,
        "notice_of": notice_of, "dmi_rows": dmi_rows, "ai_rows": ai_rows,
        "findings_of": findings_of,
        "resolved_enforcement": resolved if resolved is not None else [
            {"issue_tags": ["dark_patterns"], "target_org": "A"},
            {"issue_tags": ["dark_patterns"], "target_org": "B"},
            {"issue_tags": ["ai_adm"], "target_org": "C"},
        ],
        "regulator_jurisdictions": {"US", "EU"},
    }


def _by_id(metrics):
    return {m["metric_id"]: m for m in metrics}


# ── AC-2: n<10 suppression ───────────────────────────────────

def test_ac2_small_population_suppressed():
    metrics = _by_id(Q.compute_metrics(_data(n_orgs=5)))
    assert metrics["S4-001"]["suppressed"] is True
    assert metrics["S4-001"]["suppression_reason"] == "below_min_sample_n10"
    assert metrics["S4-001"]["value"] is None


# ── AC-3: single-org dominance (independent of n) ────────────

def test_ac3_single_org_dominance_suppressed():
    # 12 orgs (n≥10, so NOT n-suppressed) but one org owns >50% of the clauses.
    metrics = _by_id(Q.compute_metrics(_data(n_orgs=12, dominant_clause_org="o0")))
    s2 = metrics["S4-002"]
    assert s2["suppressed"] is True
    assert s2["suppression_reason"] == "single_org_dominance"  # NOT n<10
    # S4-001 (org count) at n=12 is not dominated → stays published.
    assert metrics["S4-001"]["suppressed"] is False


# ── AC-11: enforcement themes resolved-only + dominance ──────

def test_ac11_enforcement_resolved_only_and_theme_dominance():
    # dark_patterns across 10 distinct orgs (total records ≥ n=10 so not
    # n-suppressed); solo_theme owned by ONE org → dropped by max-share.
    resolved = [{"issue_tags": ["dark_patterns"], "target_org": f"org{i}"} for i in range(10)]
    resolved += [{"issue_tags": ["solo_theme"], "target_org": "org0"},
                 {"issue_tags": ["solo_theme"], "target_org": "org0"}]
    metrics = _by_id(Q.compute_metrics(_data(resolved=resolved)))
    assert metrics["S4-018"]["suppressed"] is False  # 12 resolved records ≥ n=10
    import json
    names = {t["theme"] for t in json.loads(metrics["S4-018"]["value_label"])}
    assert "dark_patterns" in names
    assert "solo_theme" not in names  # single-org theme not published


def test_ac11_fetch_filters_resolved_only():
    # _fetch_data must query enforcement_record with resolution_status=eq.resolved
    captured = []

    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        captured.append((table, filters))
        return _Resp([])
    with patch.object(Q, "supabase_rest_get", _get):
        import anyio
        anyio.run(Q._fetch_data, "2026-Q3")
    enf = [f for (t, f) in captured if t == "enforcement_record"]
    assert enf and "resolution_status=eq.resolved" in enf[0]


# ── AC-7: baseline zero deltas ───────────────────────────────

def test_ac7_no_qoq_delta_fields():
    metrics = Q.compute_metrics(_data())
    for m in metrics:
        assert "qoq" not in m and "delta" not in str(m.keys()).lower()
    # public payload advertises baseline with no deltas
    snap = {"id": "S", "quarter": "2026-Q3", "status": "approved",
            "population_criteria": '{"rule":"r","quarter_window":["2026-07-01","2026-09-30"]}',
            "formula_versions": "{}"}
    meth = Q.methodology_block(snap, metrics)
    assert "Baseline edition" in meth["baseline_note"]


# ── AC-8: methodology == stored metadata (no drift) ──────────

def test_ac8_methodology_matches_metric_values():
    metrics = Q.compute_metrics(_data(n_orgs=20, industries=("retail", "healthcare")))
    by = _by_id(metrics)
    snap = {"id": "S", "quarter": "2026-Q3", "status": "approved",
            "population_criteria": '{"rule":"r","quarter_window":["2026-07-01","2026-09-30"]}',
            "formula_versions": '{"S4-005":"F-005_v1"}'}
    meth = Q.methodology_block(snap, metrics)
    assert meth["corpus"]["organizations"] == by["S4-001"]["value"] == 20
    assert meth["corpus"]["clauses_analyzed"] == by["S4-002"]["value"]
    # both industries have 10 orgs → S4-003 counts them
    assert meth["corpus"]["industries_benchmarked"] == by["S4-003"]["value"] == 2


# ── AC-1: rehearsal exclusion in population build ────────────

def test_ac1_rehearsal_and_cqs_population():
    async def _get(table, *, select="*", filters="", limit=1000, count=False):
        if table == "report_snapshot":
            return _Resp([{"organization_id": o, "notice_id": f"n{o}", "payload": "{}",
                           "created_at": "2026-08-01"} for o in ["a", "b", "c"]])
        if table == "privacy_notice" and "open_web" in filters:
            return _Resp([{"organization_id": o} for o in ["a", "b", "c"]])  # all CQS
        if table == "organization" and "origin=eq.rehearsal" in filters:
            return _Resp([{"organization_id": "c"}])                          # c is rehearsal
        return _Resp([])
    with patch.object(Q, "supabase_rest_get", _get):
        import anyio
        data, criteria = anyio.run(Q._fetch_data, "2026-Q3")
    assert data["population"] == {"a", "b"}      # c excluded (rehearsal)
    assert criteria["eligible_org_count"] == 2
    assert "rehearsal" in criteria["rule"]


# ── AC-4: anonymization gate + gate blocks approval ──────────

def test_ac4_gate_catches_unsuppressed_violation():
    good = Q.run_anonymization_gate(Q.compute_metrics(_data(n_orgs=25)))
    assert good["passed"] is True
    # forge an unsuppressed n<10 metric (simulating a compute bug)
    bad = Q.run_anonymization_gate([{"metric_id": "X", "suppressed": False, "population_n": 3}])
    assert bad["passed"] is False and bad["violations"]


@pytest.mark.anyio
async def test_ac4_gate_failed_blocks_approval():
    snap = {"id": "S", "status": "draft", "gate_result": '{"passed": false, "violations":[{"x":1}]}'}
    with patch.object(Q, "_snapshot", AsyncMock(return_value=snap)):
        with pytest.raises(ValueError, match="gate_failed"):
            await Q.approve_quarterly("S", "expert-1")


# ── AC-6: immutability (service guard) + AC-5 approval path ──

@pytest.mark.anyio
async def test_ac6_already_approved_is_immutable():
    snap = {"id": "S", "status": "approved", "gate_result": '{"passed": true}'}
    with patch.object(Q, "_snapshot", AsyncMock(return_value=snap)):
        with pytest.raises(ValueError, match="already_approved"):
            await Q.approve_quarterly("S", "expert-1")


@pytest.mark.anyio
async def test_ac5_approve_records_expert_and_freezes():
    snap = {"id": "S", "status": "draft", "gate_result": '{"passed": true}'}
    patched = {}

    async def _patch(table, filters, payload):
        patched.update(payload)
        return _Resp({}, 204)
    with patch.object(Q, "_snapshot", AsyncMock(return_value=snap)), \
         patch.object(Q, "supabase_rest_patch", _patch):
        out = await Q.approve_quarterly("S", "expert-42")
    assert out["status"] == "approved"
    assert patched["status"] == "approved" and patched["approved_by"] == "expert-42"
    assert patched["frozen_at"] == "now()"


@pytest.mark.anyio
async def test_ac5_customer_cannot_approve():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(f"/admin/quarterly/{uuid4()}/approve", headers=_hdr(role="customer"))
    assert r.status_code == 403  # no bypass of the review-permission check


@pytest.mark.anyio
async def test_ac5_sme_permitted_on_approve_route():
    with patch.object(Q, "approve_quarterly", AsyncMock(return_value={"status": "approved"})):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/admin/quarterly/{uuid4()}/approve", headers=_hdr(role="sme"))
    assert r.status_code == 200  # sme (expert) may approve


# ── AC-9: public never serves drafts ─────────────────────────

@pytest.mark.anyio
async def test_ac9_public_never_serves_draft():
    # get_by_quarter only returns approved; a draft-only quarter → None → 404
    with patch.object(Q, "get_by_quarter", AsyncMock(return_value=None)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/quarterly/2026-Q3")
    assert r.status_code == 404


def test_ac9_public_payload_omits_suppressed():
    # a suppressed metric must be ABSENT from the public payload (not a dash)
    rows = [
        {"metric_id": "S4-001", "value": 25, "value_label": None, "population_n": 25,
         "suppressed": False, "formula_citation": "c"},
        {"metric_id": "S4-005", "value": None, "value_label": None, "population_n": 4,
         "suppressed": True, "suppression_reason": "below_min_sample_n10", "formula_citation": "c"},
    ]
    pub = Q._public_metrics(rows)
    ids = {m["metric_id"] for m in pub}
    assert "S4-001" in ids and "S4-005" not in ids


# ── AC-10: PDF/HTML reproducibility ──────────────────────────

def test_ac10_render_html_deterministic():
    from app.routers.quarterly import _render_html
    payload = {"quarter": "2026-Q3",
               "metrics": [{"metric_id": "S4-005", "value": 62.0, "value_label": None, "suppressed": False}],
               "methodology": {"quarter": "2026-Q3", "corpus": {"organizations": 25},
                               "baseline_note": "Baseline edition — trend deltas begin next quarter.",
                               "quarter_window": ["2026-07-01", "2026-09-30"]}}
    assert _render_html(payload, watermark=False) == _render_html(payload, watermark=False)
    assert "DRAFT" in _render_html(payload, watermark=True)
    assert "DRAFT" not in _render_html(payload, watermark=False)
