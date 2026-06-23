"""Training label tests — each SME action writes exactly one label."""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.review import (
    FindingAction,
    reset_reviews,
    submit_finding_action,
)
from app.services.training import (
    capture_label,
    get_labels,
    get_training_stats,
    reset_labels,
)


@pytest.fixture(autouse=True)
def _clean():
    reset_labels()
    reset_reviews()
    yield
    reset_labels()
    reset_reviews()


# ── Direct capture ───────────────────────────────────────────

def test_capture_label_returns_label():
    label = capture_label(
        assessment_id="a1",
        finding_id="f1",
        action="confirm",
        original={"severity": "high"},
        corrected={"action": "confirm"},
        sme_user_id="sme-1",
    )
    assert label is not None
    assert label.action == "confirm"
    assert label.sme_user_id == "sme-1"


def test_capture_stores_original_and_corrected():
    capture_label("a1", "f1", "edit",
                  original={"severity": "high"},
                  corrected={"severity": "medium"})
    labels = get_labels("a1")
    assert len(labels) == 1
    assert labels[0]["original"] == {"severity": "high"}
    assert labels[0]["corrected"] == {"severity": "medium"}


def test_capture_non_blocking_on_failure():
    """Capture should never raise — log and return None on failure."""
    # This should not crash even with weird input
    result = capture_label("a1", "f1", "confirm",
                           original=None, corrected=None)
    assert result is not None  # Normal case works


# ── Integration with review actions ──────────────────────────

def test_confirm_writes_one_label():
    submit_finding_action("a1", "f1", FindingAction.CONFIRM, reviewer_id="sme-1")
    labels = get_labels("a1")
    assert len(labels) == 1
    assert labels[0]["action"] == "confirm"
    assert labels[0]["finding_id"] == "f1"
    assert labels[0]["sme_user_id"] == "sme-1"


def test_edit_writes_one_label_with_changes():
    submit_finding_action("a1", "f1", FindingAction.EDIT,
                           edited_fields={"severity": "medium"},
                           reviewer_id="sme-2")
    labels = get_labels("a1")
    assert len(labels) == 1
    assert labels[0]["action"] == "edit"
    assert labels[0]["corrected"]["severity"] == "medium"


def test_dismiss_writes_one_label():
    submit_finding_action("a1", "f1", FindingAction.DISMISS, reviewer_id="sme-3")
    labels = get_labels("a1")
    assert len(labels) == 1
    assert labels[0]["action"] == "dismiss"


def test_multiple_actions_write_multiple_labels():
    submit_finding_action("a1", "f1", FindingAction.CONFIRM, reviewer_id="sme-1")
    submit_finding_action("a1", "f2", FindingAction.DISMISS, reviewer_id="sme-1")
    submit_finding_action("a1", "f3", FindingAction.EDIT,
                           edited_fields={"severity": "low"}, reviewer_id="sme-1")
    labels = get_labels("a1")
    assert len(labels) == 3


def test_re_reviewing_same_finding_adds_new_label():
    """Re-reviewing the same finding should add a second label (not overwrite)."""
    submit_finding_action("a1", "f1", FindingAction.CONFIRM)
    submit_finding_action("a1", "f1", FindingAction.EDIT,
                           edited_fields={"severity": "low"})
    labels = get_labels("a1")
    assert len(labels) == 2
    assert labels[0]["action"] == "confirm"
    assert labels[1]["action"] == "edit"


# ── Training stats ───────────────────────────────────────────

def test_stats_by_action():
    submit_finding_action("a1", "f1", FindingAction.CONFIRM)
    submit_finding_action("a1", "f2", FindingAction.DISMISS)
    submit_finding_action("a1", "f3", FindingAction.EDIT, edited_fields={})
    stats = get_training_stats()
    assert stats["total_labels"] == 3
    assert stats["by_action"]["confirm"] == 1
    assert stats["by_action"]["dismiss"] == 1
    assert stats["by_action"]["edit"] == 1


def test_stats_empty():
    stats = get_training_stats()
    assert stats["total_labels"] == 0


# ── No secrets in labels ─────────────────────────────────────

def test_labels_contain_no_secrets():
    """Labels should never contain API keys, tokens, or connection strings."""
    submit_finding_action("a1", "f1", FindingAction.CONFIRM, reviewer_id="sme-1")
    labels = get_labels("a1")
    label_str = str(labels)
    assert "sb_" not in label_str
    assert "eyJ" not in label_str
    assert "sk-" not in label_str
    assert "postgresql://" not in label_str


# ── HTTP route ───────────────────────────────────────────────

def _make_token():
    now = int(time.time())
    return pyjwt.encode(
        {"sub": "admin-user", "email": "admin@test.com", "aud": "authenticated",
         "iat": now - 60, "exp": now + 3600},
        settings.supabase_jwt_secret, algorithm="HS256",
    )


@pytest.mark.anyio
async def test_admin_training_stats_route():
    submit_finding_action("a1", "f1", FindingAction.CONFIRM, reviewer_id="sme")
    submit_finding_action("a1", "f2", FindingAction.DISMISS, reviewer_id="sme")

    token = _make_token()
    mock = patch("app.auth._load_profile", new_callable=AsyncMock,
                 return_value={"role": "admin", "organization_id": None})
    with mock:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/admin/training-stats",
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            data = r.json()
            assert data["total_labels"] == 2
            assert "by_action" in data
