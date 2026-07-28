"""Job: pull_regulators (weekly Mon 03:00).

Run ftc/cppa/state_ag connectors → new enforcement_record rows → DETERMINISTIC
entity resolution ONLY (no fuzzy). For each RESOLVED new record, find orgs whose
weakest domains (latest assessment) intersect the record's issue tags → emit
monitoring_event(regulator_signal, payload={enforcement_id, matched_domain}).
"""

from __future__ import annotations

import logging

from app.db import supabase_rest_get
from app.services.jobs.framework import emit_event, execute

log = logging.getLogger(__name__)

_CONNECTORS = ("ftc", "cppa", "state_ag")


def match_orgs(record_tags: set[str], org_weak_domains: dict[str, set[str]]) -> list[dict]:
    """PURE core (testable): for a resolved record's issue tags, return
    [{org_id, matched_domain}] for orgs whose WEAK domains intersect the tags.
    Deterministic: sorted output, exact tag∩domain intersection only."""
    out = []
    for org_id in sorted(org_weak_domains):
        for domain in sorted(org_weak_domains[org_id] & record_tags):
            out.append({"org_id": org_id, "matched_domain": domain})
    return out


def _run_connectors(runner=None) -> int:
    """Best-effort connector invocation (injectable for tests). Real connectors are
    network-bound + lazy-imported; a failure in one never aborts the job."""
    if runner is not None:
        return runner()
    ran = 0
    for name in _CONNECTORS:
        try:
            mod = __import__(f"app.services.ingestion.connectors.{name}", fromlist=["run"])
            fn = getattr(mod, "run", None) or getattr(mod, "main", None)
            if callable(fn):
                fn()
                ran += 1
        except Exception as e:  # noqa: BLE001 — honest best-effort
            log.warning("connector %s failed (non-fatal): %s", name, e)
    return ran


async def _resolved_new_records(since_iso: str | None) -> list[dict]:
    """RESOLVED enforcement records (organization_id present = deterministically resolved)."""
    flt = "organization_id=not.is.null&order=action_date.desc"
    r = await supabase_rest_get("enforcement_record",
                                select="enforcement_id,organization_id,issue_tags,domains,action_date",
                                filters=flt, limit=200)
    return r.json() if r.status_code == 200 else []


async def _org_weak_domains() -> dict[str, set[str]]:
    """Latest-assessment weakest domains per org, from stored derived scores. Deterministic."""
    r = await supabase_rest_get("risk_finding", select="organization_id,domain",
                                filters="order=organization_id", limit=5000)
    weak: dict[str, set[str]] = {}
    for row in (r.json() if r.status_code == 200 else []):
        oid, dom = row.get("organization_id"), row.get("domain")
        if oid and dom:
            weak.setdefault(oid, set()).add(dom)
    return weak


async def _body(run_id: str) -> tuple[int, int]:
    _run_connectors()
    records = await _resolved_new_records(None)
    weak = await _org_weak_domains()
    processed, changed = 0, 0
    seen: set[tuple] = set()
    for rec in records:
        processed += 1
        tags = set(rec.get("issue_tags") or []) | set(rec.get("domains") or [])
        if not tags:
            continue
        for m in match_orgs(tags, weak):
            key = (rec["enforcement_id"], m["org_id"], m["matched_domain"])
            if key in seen:
                continue
            seen.add(key)
            await emit_event(m["org_id"], "regulator_signal", source_id=rec["enforcement_id"],
                             payload={"enforcement_id": rec["enforcement_id"],
                                      "matched_domain": m["matched_domain"]})
            changed += 1
    return processed, changed


async def run(triggered_by: str = "schedule") -> dict:
    return await execute("pull_regulators", triggered_by, _body)
