"""Regression test for lesson L-006 — a failed profile write must not be silent.

`_ensure_org_profile` (app/services/live_scoring.py) used to POST the org profile
with no status check, so an insert that 400'd on the (then-unapplied) migration-0014
columns was swallowed for weeks. These tests pin the loud behavior. Fully mocked —
no network, no live DB.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import live_scoring


def _client(post_status: int) -> AsyncMock:
    """AsyncMock httpx client: no existing profile, one org row, POST → post_status."""
    client = AsyncMock()
    prof = MagicMock(status_code=200); prof.json.return_value = []          # no existing profile
    org = MagicMock(status_code=200)
    org.json.return_value = [{"organization_id": "o1", "industry": "fintech",
                              "size": "unknown", "geography": "US"}]
    client.get = AsyncMock(side_effect=[prof, org])
    posted = MagicMock(status_code=post_status)
    client.post = AsyncMock(return_value=posted)
    return client


@pytest.mark.anyio
async def test_failed_profile_write_raises_not_swallowed():
    client = _client(post_status=400)
    notice = MagicMock(); notice.clauses = []
    with patch("app.services.profiling.live_profile.compute_org_profile",
               return_value=MagicMock()):
        with pytest.raises(RuntimeError, match="insert failed"):
            await live_scoring._ensure_org_profile(client, {}, "o1", notice)


@pytest.mark.anyio
async def test_successful_profile_write_returns_payload():
    client = _client(post_status=201)
    notice = MagicMock(); notice.clauses = []
    with patch("app.services.profiling.live_profile.compute_org_profile",
               return_value=MagicMock()):
        result = await live_scoring._ensure_org_profile(client, {}, "o1", notice)
    assert result is not None and result["organization_id"] == "o1"
