"""BACK-001 — stale/orphaned job_run reaping.

A worker SIGKILL'd/OOM'd between _open_run and _close_run leaves a row stuck in
`status=running` forever. These tests prove that (1) `is_running` no longer treats
such a stale row as live, (2) `reap_stale_runs` marks it failed, and (3) a job is
therefore not blocked on the next tick.
"""

from unittest.mock import patch

import pytest

from app.services.jobs import framework as F

_STALE_TS = "2000-01-01T00:00:00+00:00"  # far in the past → older than any max runtime


class _Resp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data


@pytest.mark.anyio
async def test_is_running_excludes_stale_rows():
    """A `running` row older than max runtime must NOT count as live."""
    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        # is_running only counts FRESH running rows (started within max runtime).
        assert "status=eq.running" in filters and "started_at=gte." in filters
        return _Resp([])  # no fresh running row exists
    with patch.object(F, "supabase_rest_get", fake_get):
        assert await F.is_running("monitor_notices") is False


@pytest.mark.anyio
async def test_reap_marks_orphaned_run_failed():
    patched = []

    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        if "started_at=lt." in filters and "status=eq.running" in filters:
            return _Resp([{"id": "run-1", "started_at": _STALE_TS}])
        return _Resp([])

    async def fake_patch(table, filters, payload):
        patched.append((filters, payload))
        return _Resp([], 204)

    with patch.object(F, "supabase_rest_get", fake_get), \
         patch.object(F, "supabase_rest_patch", fake_patch):
        n = await F.reap_stale_runs("monitor_notices")

    assert n == 1
    assert any(p[1]["status"] == "failed" and "reaped" in (p[1].get("error") or "")
               for p in patched), "orphaned run must be marked failed with a reaped reason"


@pytest.mark.anyio
async def test_execute_not_blocked_by_orphaned_run():
    """The core guarantee: an abandoned `running` row does not disable the job."""
    calls = {"reaped": 0, "opened": 0, "body": 0}

    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        if "started_at=lt." in filters:      # reap query → one stale/orphaned row
            return _Resp([{"id": "old", "started_at": _STALE_TS}])
        if "started_at=gte." in filters:     # is_running fresh query → none live
            return _Resp([])
        return _Resp([])

    async def fake_patch(table, filters, payload):
        if payload.get("status") == "failed" and "reaped" in (payload.get("error") or ""):
            calls["reaped"] += 1
        return _Resp([], 204)

    async def fake_post(table, payload, *, on_conflict="", upsert=False):
        if table == "job_run" and payload.get("status") == "running":
            calls["opened"] += 1
        return _Resp([], 201)

    async def body(run_id):
        calls["body"] += 1
        return (5, 2)

    with patch.object(F, "supabase_rest_get", fake_get), \
         patch.object(F, "supabase_rest_patch", fake_patch), \
         patch.object(F, "supabase_rest_post", fake_post):
        result = await F.execute("monitor_notices", "test", body)

    assert calls["reaped"] == 1, "the orphaned run should have been reclaimed"
    assert calls["body"] == 1, "job body must run — not blocked by the stale row"
    assert result["status"] == "succeeded"


@pytest.mark.anyio
async def test_stale_run_count_counts_orphans():
    async def fake_get(table, *, select="*", filters="", limit=1000, count=False):
        if "started_at=lt." in filters:
            return _Resp([{"id": "x"}])  # one orphan per job name queried
        return _Resp([])
    with patch.object(F, "supabase_rest_get", fake_get):
        # counts across the three default jobs → 3 orphans
        assert await F.stale_run_count() == len(F.JOB_DEFAULTS)
        assert await F.stale_run_count("monitor_notices") == 1
