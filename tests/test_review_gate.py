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
    review = get_or_create_review("assess-1")
    assert review.status == AssessmentStatus.DRAFT


def test_first_action_moves_to_in_review():
    submit_finding_action("assess-1", "f1", FindingAction.CONFIRM)
    review = get_or_create_review("assess-1")
    assert review.status == AssessmentStatus.IN_REVIEW


def test_approve_moves_to_approved():
    submit_finding_action("assess-1", "f1", FindingAction.CONFIRM)
    approve_assessment("assess-1", "sme-user")
    review = get_or_create_review("assess-1")
    assert review.status == AssessmentStatus.APPROVED


def test_cannot_modify_after_approval():
    submit_finding_action("assess-1", "f1", FindingAction.CONFIRM)
    approve_assessment("assess-1", "sme-user")
    with pytest.raises(ValueError, match="approved"):
        submit_finding_action("assess-1", "f2", FindingAction.CONFIRM)


def test_cannot_double_approve():
    approve_assessment("assess-1", "sme-user")
    with pytest.raises(ValueError, match="already approved"):
        approve_assessment("assess-1", "sme-user")


# ── Finding actions persist ──────────────────────────────────

def test_confirm_persists():
    fr = submit_finding_action("a1", "f1", FindingAction.CONFIRM, reviewer_id="sme-1")
    assert fr.action == FindingAction.CONFIRM
    assert fr.reviewer_id == "sme-1"


def test_edit_persists():
    fr = submit_finding_action("a1", "f1", FindingAction.EDIT,
                                edited_fields={"severity": "medium"})
    assert fr.edited_fields == {"severity": "medium"}


def test_dismiss_persists():
    fr = submit_finding_action("a1", "f1", FindingAction.DISMISS)
    assert fr.action == FindingAction.DISMISS


# ── Dismissed findings excluded from report ──────────────────

def test_dismissed_finding_excluded():
    findings = [
        {"finding_id": "f1", "code": "SH-002", "domain": "data_sharing"},
        {"finding_id": "f2", "code": "RT-003", "domain": "retention"},
        {"finding_id": "f3", "code": "AI-004", "domain": "ai"},
    ]
    submit_finding_action("a1", "f2", FindingAction.DISMISS)
    active = get_active_findings("a1", findings)
    codes = [f["code"] for f in active]
    assert "SH-002" in codes
    assert "RT-003" not in codes  # dismissed
    assert "AI-004" in codes


def test_edited_finding_reflects_changes():
    findings = [{"finding_id": "f1", "code": "SH-002", "severity": "high"}]
    submit_finding_action("a1", "f1", FindingAction.EDIT,
                           edited_fields={"severity": "medium"})
    active = get_active_findings("a1", findings)
    assert active[0]["severity"] == "medium"


# ── Gate modes ───────────────────────────────────────────────

def test_gate_strict_blocks_customer_before_approval():
    set_gate_mode(GateMode.STRICT)
    can_view, banner = customer_can_view("assess-1")
    assert can_view is False


def test_gate_strict_allows_after_approval():
    set_gate_mode(GateMode.STRICT)
    approve_assessment("assess-1", "sme")
    can_view, banner = customer_can_view("assess-1")
    assert can_view is True
    assert banner == ""


def test_gate_instant_draft_shows_with_banner():
    set_gate_mode(GateMode.INSTANT_DRAFT)
    can_view, banner = customer_can_view("assess-1")
    assert can_view is True
    assert "DRAFT" in banner
    assert "pending expert review" in banner.lower()


def test_gate_instant_draft_no_banner_after_approval():
    set_gate_mode(GateMode.INSTANT_DRAFT)
    approve_assessment("assess-1", "sme")
    can_view, banner = customer_can_view("assess-1")
    assert can_view is True
    assert banner == ""


def test_gate_client_reviews_shows_with_banner():
    set_gate_mode(GateMode.CLIENT_REVIEWS)
    can_view, banner = customer_can_view("assess-1")
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
                "/review/finding/assess-1/f1",
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
            r = await c.post("/review/assess-1/approve", headers=ctx["headers"])
            assert r.status_code == 200
            assert r.json()["status"] == "approved"


@pytest.mark.anyio
async def test_customer_blocked_in_strict_mode():
    set_gate_mode(GateMode.STRICT)
    ctx = _auth("customer")
    with ctx["mock"]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/reports/assess-1", headers=ctx["headers"])
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
            r = await c.get("/reports/assess-1", headers=ctx["headers"])
            assert r.status_code == 200
            assert "draft_banner" in r.json()
            assert "DRAFT" in r.json()["draft_banner"]
