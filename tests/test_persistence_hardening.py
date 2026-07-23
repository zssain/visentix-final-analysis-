"""F06 persistence hardening — review/training/gate state survive restart, and
approval + snapshot freeze commit atomically.

These exercise the live DB (the authoritative store). State is created, asserted
across a simulated process restart (cache clear, DB untouched), then cleaned up.
"""
import time
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db import get_service_headers
from app.main import app
from app.services import review as R
from app.services.review import (
    AssessmentStatus, FindingAction, GateMode,
    approve_assessment, flag_low_vci_object, get_gate_mode, get_low_vci_objects,
    get_review, reset_reviews, submit_finding_action,
)
from app.services.training import get_labels, reset_labels


@pytest.fixture(autouse=True)
def _clean():
    reset_reviews(); reset_labels()
    yield
    reset_reviews(); reset_labels()


def _token(sub="u", role="authenticated"):
    now = int(time.time())
    return pyjwt.encode({"sub": sub, "email": "u@t.com", "aud": "authenticated",
                         "iat": now - 60, "exp": now + 3600, "role": role},
                        settings.supabase_jwt_secret, algorithm="HS256")


def _profile(role):
    return patch("app.auth._load_profile", new_callable=AsyncMock,
                 return_value={"role": role, "organization_id": str(uuid.uuid4())})


def _rest(method, path, prefer=None, json=None):
    h = {**get_service_headers(), "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return httpx.request(method, f"{settings.supabase_url}/rest/v1/{path}",
                         headers=h, timeout=15, json=json)


def _seed_snapshot() -> str:
    """Insert a minimal report_snapshot; return its snapshot_id."""
    h = {**get_service_headers(), "Content-Type": "application/json", "Prefer": "return=representation"}
    r = httpx.post(f"{settings.supabase_url}/rest/v1/report_snapshot", headers=h, timeout=15, json={
        "organization_id": str(uuid.uuid4()),
        "notice_id": str(uuid.uuid4()),
        "payload": {"section": "test", "value": 42},
        "formula_version_set": {"F-010": "1"},
    })
    return r.json()[0]["snapshot_id"]


def _delete_snapshot(sid: str):
    _rest("DELETE", f"report_snapshot?snapshot_id=eq.{sid}", prefer="return=minimal")


# ── Approval + freeze atomicity ─────────────────────────────────────

def test_approve_freeze_kill_leaves_state_draft():
    """Failure between approval and freeze (bogus snapshot) → nothing commits;
    the assessment stays cleanly un-approved."""
    aid = f"assess-kill-{uuid.uuid4().hex[:8]}"
    submit_finding_action(aid, "f1", FindingAction.CONFIRM, reviewer_id="sme-1")  # -> in_review
    R._clear_caches()
    bogus = str(uuid.uuid4())
    with pytest.raises(RuntimeError):
        approve_assessment(aid, "sme-1", snapshot_id=bogus)
    R._clear_caches()
    review = get_review(aid)
    assert review is not None
    assert review.status != AssessmentStatus.APPROVED           # never half-approved
    assert review.approved_by == ""


def test_approve_freeze_success_commits_both():
    """With a real snapshot, approval AND freeze commit together."""
    aid = f"assess-ok-{uuid.uuid4().hex[:8]}"
    sid = _seed_snapshot()
    try:
        submit_finding_action(aid, "f1", FindingAction.CONFIRM, reviewer_id="sme-1")
        approve_assessment(aid, "sme-1", snapshot_id=sid)
        R._clear_caches()
        # approval persisted
        assert get_review(aid).status == AssessmentStatus.APPROVED
        # snapshot frozen: rendered_report + content_hash written
        snap = _rest("GET", f"report_snapshot?select=rendered_report,content_hash&snapshot_id=eq.{sid}").json()[0]
        assert snap["rendered_report"] is not None
        assert snap["content_hash"] and len(snap["content_hash"]) == 64  # sha256 hex
    finally:
        _delete_snapshot(sid)


# ── Restart survival ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_state_survives_restart():
    """Create review state + labels + gate mode via the API, simulate a process
    restart (fresh instances = caches cleared, DB untouched), and assert
    everything is still there and gate mode is unchanged."""
    aid = f"assess-restart-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)

    with _profile("admin"):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/review/gate-mode", headers={"Authorization": f"Bearer {_token()}"},
                             json={"mode": "strict"})
            assert r.status_code == 200
    with _profile("sme"):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(f"/review/finding/{aid}/f1",
                             headers={"Authorization": f"Bearer {_token()}"},
                             json={"action": "confirm"})
            assert r.status_code == 200

    # VCI queue has no HTTP route — flag at the service layer.
    flag_low_vci_object(aid, "compound_risk", vci_score=30.0, score=55.0)

    # ── simulate restart: fresh service instances, empty caches, DB intact ──
    R._clear_caches()

    # review state reloaded from DB
    review = get_review(aid)
    assert review is not None and review.status == AssessmentStatus.IN_REVIEW
    assert review.finding_reviews["f1"].action == FindingAction.CONFIRM
    # gate mode unchanged
    assert get_gate_mode() == GateMode.STRICT
    # training label persisted
    labels = get_labels(aid)
    assert len(labels) == 1 and labels[0]["action"] == "confirm"
    # VCI queue item persisted
    pending = get_low_vci_objects(aid)
    assert len(pending) == 1 and pending[0]["object_type"] == "compound_risk"
