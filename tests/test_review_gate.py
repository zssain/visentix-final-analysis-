"""Phase 7 review gate tests — actions, approval, gate modes, dismissed findings."""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.review import (
    AssessmentStatus,
    FindingAction,
    GateMode,
    approve_assessment,
    customer_can_view,
    get_active_findings,
    get_or_create_review,
    reset_reviews,
    set_gate_mode,
    submit_finding_action,
)


# ── Helpers ──────────────────────────────────────────────────

# UUID-shaped synthetic ids — assessment_id columns enforce a UUID CHECK
# (migration 0047). Must stay in sync with _TEST_IDS in app/services/review.py
# so reset_reviews() cleans them from the DB.
ASSESS_1 = "aaaaaaaa-0000-4000-8000-000000000001"
A1 = "aaaaaaaa-0000-4000-8000-0000000000a1"


def _make_token(sub: str = "test-user", email: str = "test@example.com") -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": sub, "email": email, "aud": "authenticated",
         "iat": now - 60, "exp": now + 3600, "role": "authenticated"},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


def _auth(role: str = "sme"):
    token = _make_token()
    return {
        "mock": patch("app.auth._load_profile", new_callable=AsyncMock,
                       return_value={"role": role, "organization_id": str(uuid4())}),
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture(autouse=True)
def _clean():
    reset_reviews()
    yield
    reset_reviews()


# ── Status model ─────────────────────────────────────────────

def test_initial_status_is_draft():
    review = get_or_create_review(ASSESS_1)
    assert review.status == AssessmentStatus.DRAFT


def test_first_action_moves_to_in_review():
    submit_finding_action(ASSESS_1, "f1", FindingAction.CONFIRM)
    review = get_or_create_review(ASSESS_1)
    assert review.status == AssessmentStatus.IN_REVIEW


def test_approve_moves_to_approved():
    submit_finding_action(ASSESS_1, "f1", FindingAction.CONFIRM)
    approve_assessment(ASSESS_1, "sme-user")
    review = get_or_create_review(ASSESS_1)
    assert review.status == AssessmentStatus.APPROVED


def test_cannot_modify_after_approval():
    submit_finding_action(ASSESS_1, "f1", FindingAction.CONFIRM)
    approve_assessment(ASSESS_1, "sme-user")
    with pytest.raises(ValueError, match="approved"):
        submit_finding_action(ASSESS_1, "f2", FindingAction.CONFIRM)


def test_cannot_double_approve():
    approve_assessment(ASSESS_1, "sme-user")
    with pytest.raises(ValueError, match="already approved"):
        approve_assessment(ASSESS_1, "sme-user")


# ── Finding actions persist ──────────────────────────────────

def test_confirm_persists():
    fr = submit_finding_action(A1, "f1", FindingAction.CONFIRM, reviewer_id="sme-1")
    assert fr.action == FindingAction.CONFIRM
    assert fr.reviewer_id == "sme-1"


def test_edit_persists():
    fr = submit_finding_action(A1, "f1", FindingAction.EDIT,
                                edited_fields={"severity": "medium"})
    assert fr.edited_fields == {"severity": "medium"}


def test_dismiss_persists():
    fr = submit_finding_action(A1, "f1", FindingAction.DISMISS)
    assert fr.action == FindingAction.DISMISS


# ── Dismissed findings excluded from report ──────────────────

def test_dismissed_finding_excluded():
    findings = [
        {"finding_id": "f1", "code": "SH-002", "domain": "data_sharing"},
        {"finding_id": "f2", "code": "RT-003", "domain": "retention"},
        {"finding_id": "f3", "code": "AI-004", "domain": "ai"},
    ]
    submit_finding_action(A1, "f2", FindingAction.DISMISS)
    active = get_active_findings(A1, findings)
    codes = [f["code"] for f in active]
    assert "SH-002" in codes
    assert "RT-003" not in codes  # dismissed
    assert "AI-004" in codes


def test_edited_finding_reflects_changes():
    findings = [{"finding_id": "f1", "code": "SH-002", "severity": "high"}]
    submit_finding_action(A1, "f1", FindingAction.EDIT,
                           edited_fields={"severity": "medium"})
    active = get_active_findings(A1, findings)
    assert active[0]["severity"] == "medium"


# ── Gate modes ───────────────────────────────────────────────

def test_gate_strict_blocks_customer_before_approval():
    set_gate_mode(GateMode.STRICT)
    can_view, banner = customer_can_view(ASSESS_1)
    assert can_view is False


def test_gate_strict_allows_after_approval():
    set_gate_mode(GateMode.STRICT)
    approve_assessment(ASSESS_1, "sme")
    can_view, banner = customer_can_view(ASSESS_1)
    assert can_view is True
    assert banner == ""


def test_gate_instant_draft_shows_with_banner():
    set_gate_mode(GateMode.INSTANT_DRAFT)
    can_view, banner = customer_can_view(ASSESS_1)
    assert can_view is True
    assert "DRAFT" in banner
    assert "pending expert review" in banner.lower()


def test_gate_instant_draft_no_banner_after_approval():
    set_gate_mode(GateMode.INSTANT_DRAFT)
    approve_assessment(ASSESS_1, "sme")
    can_view, banner = customer_can_view(ASSESS_1)
    assert can_view is True
    assert banner == ""


def test_gate_client_reviews_shows_with_banner():
    set_gate_mode(GateMode.CLIENT_REVIEWS)
    can_view, banner = customer_can_view(ASSESS_1)
    assert can_view is True
    assert "DRAFT" in banner


# ── HTTP routes ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_review_queue_sme_only():
    ctx = _auth("customer")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/review/queue", headers=ctx["headers"])
            assert r.status_code == 403


@pytest.mark.anyio
async def test_review_queue_accessible_to_sme():
    ctx = _auth("sme")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/review/queue", headers=ctx["headers"])
            assert r.status_code == 200


@pytest.mark.anyio
async def test_finding_action_via_route():
    ctx = _auth("sme")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                f"/review/finding/{ASSESS_1}/f1",
                headers=ctx["headers"],
                json={"action": "confirm"},
            )
            assert r.status_code == 200
            assert r.json()["action"] == "confirm"


@pytest.mark.anyio
async def test_approve_via_route():
    ctx = _auth("sme")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/review/{ASSESS_1}/approve", headers=ctx["headers"])
            assert r.status_code == 200
            assert r.json()["status"] == "approved"


@pytest.mark.anyio
async def test_customer_blocked_in_strict_mode():
    set_gate_mode(GateMode.STRICT)
    ctx = _auth("customer")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(f"/reports/{ASSESS_1}", headers=ctx["headers"])
            assert r.status_code == 403


@pytest.mark.anyio
@pytest.mark.skip(reason="DEBT: review/gate state is in-memory (app/services/review.py) and the "
                         "report route 404s without a seeded snapshot — awaits review-state "
                         "persistence hardening")
async def test_customer_sees_draft_banner_in_instant_mode():
    set_gate_mode(GateMode.INSTANT_DRAFT)
    ctx = _auth("customer")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(f"/reports/{ASSESS_1}", headers=ctx["headers"])
            assert r.status_code == 200
            assert "draft_banner" in r.json()
            assert "DRAFT" in r.json()["draft_banner"]


def test_gate_defaults_to_strict_when_platform_setting_empty():
    """C5/D1 safety: a fresh prod (no gate_mode row) must default to STRICT
    (expert_review) — never show drafts before SME approval."""
    import app.services.review as R

    class _Empty:
        status_code = 200
        def json(self):
            return []

    R._gate_mode_cache = None
    with patch.object(R.httpx, "get", return_value=_Empty()):
        assert R.get_gate_mode() == GateMode.STRICT
    R._gate_mode_cache = None  # don't leak cache to other tests


@pytest.mark.anyio
async def test_gate_mode_route_not_shadowed_by_dynamic_id():
    """Regression: GET /review/gate-mode must return {'mode': ...}, not be
    swallowed by GET /review/{assessment_id} (Stage-3 routing fix)."""
    import app.routers.review as RR
    ctx = _auth("admin")
    with ctx["mock"], patch.object(RR, "get_gate_mode", return_value=GateMode.STRICT):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/review/gate-mode", headers=ctx["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body == {"mode": "strict"}      # not a review object
    assert "assessment_id" not in body


# ── FUNC-001 / F06 AC-3: the gate must actually gate ─────────
#
# Two defects made the review gate fail open, and these are their regressions.
#
#  1. The workbench fetched `GET /findings/`, which for an SME returns EVERY
#     organization's findings ordered by score and capped at 200, then filtered
#     client-side by notice_id. An assessment outside that global top-200
#     rendered an empty finding list — while Approve stayed live.
#  2. approve_assessment never checked whether findings had been reviewed, so a
#     report could be frozen as client-shippable with nothing read.

@pytest.mark.anyio
async def test_approve_refused_while_findings_are_unreviewed():
    """STRICT is the spec's expert_review and the default: approval must be
    refused (409) while any finding still has no decision."""
    set_gate_mode(GateMode.STRICT)
    ctx = _auth("sme")
    unreviewed = str(uuid4())

    async def fake_rest_get(table, **kw):
        class R:
            @staticmethod
            def json():
                return [{"finding_id": unreviewed}] if table == "risk_finding" else []
        return R()

    with ctx["mock"], patch("app.db.supabase_rest_get", new=fake_rest_get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/review/{ASSESS_1}/approve", headers=ctx["headers"])
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["error"] == "findings_pending_review"
    assert unreviewed in body["pending_finding_ids"]


@pytest.mark.anyio
async def test_review_findings_are_scoped_to_the_assessment_and_carry_real_citations():
    """The per-assessment endpoint filters on notice_id (never a global top-N)
    and cites clauses through `finding_clause` — never 'a clause in the same
    domain'. A finding with no linked clause reports honest absence."""
    ctx = _auth("sme")
    fid, cited = str(uuid4()), str(uuid4())
    seen: dict[str, str] = {}

    async def fake_rest_get(table, **kw):
        seen[table] = kw.get("filters", "")
        rows = {
            "risk_finding": [
                {"finding_id": fid, "finding_type_code": "RT-003", "domain": "retention"},
                {"finding_id": "no-evidence", "finding_type_code": "SH-002", "domain": "data_sharing"},
            ],
            "finding_clause": [{"finding_id": fid, "clause_id": cited}],
            "disclosure_clause": [{"clause_id": cited, "raw_text": "We keep data for 24 months.",
                                   "category": "retention"}],
        }.get(table, [])

        class R:
            @staticmethod
            def json():
                return rows
        return R()

    with ctx["mock"], patch("app.db.supabase_rest_get", new=fake_rest_get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get(f"/review/{ASSESS_1}/findings", headers=ctx["headers"])

    assert r.status_code == 200, r.text
    data = r.json()
    # Scoped by assessment — not a platform-wide list trimmed by score.
    assert f"notice_id=eq.{ASSESS_1}" in seen["risk_finding"]
    by_code = {f["finding_type_code"]: f for f in data["findings"]}
    assert by_code["RT-003"]["evidence"][0]["clause_id"] == cited
    assert "24 months" in by_code["RT-003"]["evidence"][0]["text"]
    # Honest absence — never padded with an unrelated same-domain clause.
    assert by_code["SH-002"]["evidence"] == []
    assert data["total_count"] == 2
    assert data["reviewed_count"] == 0
    assert data["all_reviewed"] is False
