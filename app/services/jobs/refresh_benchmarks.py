"""Job: refresh_benchmarks (monthly 1st 04:00).

Re-run the F03 demo-cohort job → if a cluster's membership changed, emit
monitoring_event(cohort_rebenchmarked, payload={cluster_id, old_n, new_n}).
(Schema vocabulary is `cohort_rebenchmarked` — the task's 'cohort_refreshed' is
reconciled to the one of the four §2.8 values, since no new type may be added.)
"""

from __future__ import annotations

import logging

from app.db import supabase_rest_get
from app.services.jobs.framework import emit_event, execute

log = logging.getLogger(__name__)


def diff_membership(old: dict[str, int], new: dict[str, int]) -> list[dict]:
    """PURE core (testable): clusters whose membership count changed."""
    out = []
    for cid in sorted(set(old) | set(new)):
        o, n = old.get(cid, 0), new.get(cid, 0)
        if o != n:
            out.append({"cluster_id": cid, "old_n": o, "new_n": n})
    return out


async def _membership_counts() -> dict[str, int]:
    r = await supabase_rest_get("benchmark_membership", select="cluster_id", limit=5000)
    counts: dict[str, int] = {}
    for row in (r.json() if r.status_code == 200 else []):
        cid = row.get("cluster_id")
        if cid:
            counts[cid] = counts.get(cid, 0) + 1
    return counts


def _run_cohort_job(runner=None) -> None:
    """Re-run the F03 demo-cohort builder (injectable for tests)."""
    if runner is not None:
        runner()
        return
    try:  # pragma: no cover - heavy job, exercised via injection in tests
        import importlib
        mod = importlib.import_module("scripts.build_cohorts")
        fn = getattr(mod, "main", None) or getattr(mod, "build", None)
        if callable(fn):
            fn()
    except Exception as e:  # noqa: BLE001
        log.warning("refresh_benchmarks: cohort job failed (non-fatal): %s", e)


async def _body(run_id: str, runner=None) -> tuple[int, int]:
    before = await _membership_counts()
    _run_cohort_job(runner)
    after = await _membership_counts()
    changes = diff_membership(before, after)
    for ch in changes:
        # cohort_rebenchmarked is a platform-wide corpus event (no single org).
        await emit_event(None, "cohort_rebenchmarked", prior=ch["old_n"], current=ch["new_n"],
                         payload=ch)
    return len(before) or len(after), len(changes)


async def run(triggered_by: str = "schedule") -> dict:
    return await execute("refresh_benchmarks", triggered_by, _body)
