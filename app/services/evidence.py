"""F05 addendum — Recommendation evidence stacks.

For each confirmed finding, assemble ONE evidence row (obligation context +
one SME-approved exemplar or honest absence + ≤2 resolved-enforcement
precedents + a risk_reduction_delta that is NULL forever). Assembled at
APPROVAL/FREEZE and written once — the frozen artifact (DIR-010). The GET
endpoint reads these frozen rows; nothing re-assembles at render.

Reads only: clause_obligation, obligation, disclosure_clause (approved
exemplars), enforcement_record (resolved). NEVER writes an embedding table.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.db import supabase_rest_get, supabase_rest_post
from app.logging import get_logger

log = get_logger(__name__)

OBLIGATION_FLOOR = 0.35  # obligation_match.py floor
FORMULA_VERSION = "F05-evidence_v1"

# Verbatim exposure-context register (obligation_match.py).
OBLIGATION_REGISTER = (
    "Matches are EXPOSURE CONTEXT only — never a legal conclusion. Unverified "
    "obligations (effective_date=NULL) carry reduced confidence."
)

# Three DISTINCT honest-absence claims — never conflated.
ABSENCE = {
    "out_of_scope": "obligation context not yet available",
    "below_floor": "no related obligations above the similarity threshold",
    "no_approved_exemplar": "no approved exemplar for this domain yet",
}

_SCOPE_ORG_IDS: set[str] | None = None


def _in_scope_orgs() -> set[str]:
    """Org ids whose cohort was matched (logs/eval/obligation_match_scope.json).
    An org outside this set → 'obligation context not yet available'."""
    global _SCOPE_ORG_IDS
    if _SCOPE_ORG_IDS is None:
        ids: set[str] = set()
        try:
            p = Path(__file__).resolve().parents[2] / "logs" / "eval" / "obligation_match_scope.json"
            data = json.loads(p.read_text())
            for cohort in (data.get("cohorts") or {}).values():
                if cohort.get("status") == "covered":
                    ids.update(cohort.get("org_ids") or [])
        except Exception:
            ids = set()
        _SCOPE_ORG_IDS = ids
    return _SCOPE_ORG_IDS


# ── Assembly ─────────────────────────────────────────────────

async def _notice_org(assessment_id: str) -> str | None:
    r = await supabase_rest_get("privacy_notice", select="organization_id",
                                filters=f"notice_id=eq.{assessment_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0]["organization_id"] if rows else None


async def _clauses_by_domain(assessment_id: str) -> dict[str, list[str]]:
    """{domain: [clause_id,…]} for the notice (via notice_section)."""
    r = await supabase_rest_get("notice_section", select="section_id",
                                filters=f"notice_id=eq.{assessment_id}", limit=1000)
    section_ids = [s["section_id"] for s in (r.json() if r.status_code == 200 else []) if s.get("section_id")]
    out: dict[str, list[str]] = {}
    for i in range(0, len(section_ids), 40):
        chunk = ",".join(f'"{s}"' for s in section_ids[i:i + 40])
        cr = await supabase_rest_get("disclosure_clause", select="clause_id,category",
                                     filters=f"section_id=in.({chunk})", limit=2000)
        for c in (cr.json() if cr.status_code == 200 else []):
            out.setdefault(c.get("category") or "other", []).append(c["clause_id"])
    return out


async def _obligation_refs(clause_ids: list[str]) -> list[dict]:
    """Obligation context for a domain's clauses (similarity >= floor)."""
    if not clause_ids:
        return []
    refs: list[dict] = []
    seen: set[str] = set()
    for i in range(0, len(clause_ids), 40):
        chunk = ",".join(f'"{c}"' for c in clause_ids[i:i + 40])
        r = await supabase_rest_get(
            "clause_obligation", select="obligation_id,similarity,matched_terms",
            filters=f"clause_id=in.({chunk})&similarity=gte.{OBLIGATION_FLOOR}"
                    f"&order=similarity.desc", limit=200)
        for m in (r.json() if r.status_code == 200 else []):
            oid = m.get("obligation_id")
            if not oid or oid in seen:
                continue
            seen.add(oid)
            refs.append({"obligation_id": oid, "similarity": round(float(m.get("similarity") or 0), 4),
                         "matched_terms": m.get("matched_terms")})
    if not refs:
        return []
    # Enrich with obligation metadata (law / requirement_type / verified).
    in_list = ",".join(f'"{r["obligation_id"]}"' for r in refs[:8])
    orq = await supabase_rest_get(
        "obligation", select="obligation_id,law,requirement_type,jurisdiction,effective_date",
        filters=f"obligation_id=in.({in_list})", limit=50)
    meta = {o["obligation_id"]: o for o in (orq.json() if orq.status_code == 200 else [])}
    for ref in refs[:8]:
        o = meta.get(ref["obligation_id"], {})
        ref.update({"law": o.get("law"), "requirement_type": o.get("requirement_type"),
                    "jurisdiction": o.get("jurisdiction"),
                    "verified": o.get("effective_date") is not None})
    return refs[:8]


async def _approved_exemplar(domain: str) -> str | None:
    r = await supabase_rest_get(
        "disclosure_clause", select="clause_id",
        filters=f"is_exemplar=eq.true&exemplar_status=eq.approved&category=eq.{domain}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0]["clause_id"] if rows else None


async def _enforcement_refs(domain: str) -> list[dict]:
    """≤2 RESOLVED enforcement precedents whose issue_tags relate to the domain."""
    r = await supabase_rest_get(
        "enforcement_record", select="enforcement_id,regulator_id,issue_tags,action_date",
        filters="resolution_status=eq.resolved", limit=500)
    dom_tokens = set(domain.split("_"))
    scored = []
    for e in (r.json() if r.status_code == 200 else []):
        tags = e.get("issue_tags") or []
        tag_tokens = {t.lower() for tag in tags for t in str(tag).replace("-", "_").split("_")}
        overlap = dom_tokens & tag_tokens
        if not overlap:
            continue
        sim = round(len(overlap) / max(len(tag_tokens), 1), 3)
        yr = (e.get("action_date") or "")[:4]
        scored.append((sim, {"enforcement_id": e["enforcement_id"], "regulator": e.get("regulator_id"),
                             "year": yr, "similarity": sim}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:2]]


async def assemble_evidence(assessment_id: str) -> list[dict]:
    """Build one evidence dict per finding. Pure of writes."""
    org_id = await _notice_org(assessment_id)
    in_scope = bool(org_id and org_id in _in_scope_orgs())

    fr = await supabase_rest_get("risk_finding", select="finding_id,domain,finding_type_code,severity",
                                 filters=f"notice_id=eq.{assessment_id}", limit=200)
    findings = fr.json() if fr.status_code == 200 else []
    clauses = await _clauses_by_domain(assessment_id)

    out: list[dict] = []
    for f in findings:
        domain = f.get("domain") or "other"
        # obligation context + honest absence (3 distinct claims, never conflated)
        obligation_refs: list[dict] = []
        absence_reason: str | None = None
        if not in_scope:
            absence_reason = "out_of_scope"
        else:
            obligation_refs = await _obligation_refs(clauses.get(domain, []))
            if not obligation_refs:
                absence_reason = "below_floor"
        exemplar_id = await _approved_exemplar(domain)
        exemplar_absent = exemplar_id is None
        enforcement_refs = await _enforcement_refs(domain)

        out.append({
            "finding_id": f["finding_id"], "assessment_id": assessment_id,
            "domain": domain, "finding_type_code": f.get("finding_type_code"),
            "obligation_refs": obligation_refs,
            "obligation_register": OBLIGATION_REGISTER,
            "exemplar_clause_id": exemplar_id,
            "enforcement_refs": enforcement_refs,
            # three distinct absence claims (obligation-level + exemplar-level, never merged)
            "absence_reason": absence_reason,
            "absence_text": ABSENCE.get(absence_reason) if absence_reason else None,
            "exemplar_absence_text": ABSENCE["no_approved_exemplar"] if exemplar_absent else None,
            "risk_reduction_delta": None,   # NULL forever — no formula exists
            "formula_version_id": FORMULA_VERSION,
            "confidence": round(
                (sum(r["similarity"] for r in obligation_refs) / len(obligation_refs)) if obligation_refs else 0.0, 3),
        })
    return out


async def freeze_evidence_on_approval(assessment_id: str) -> int:
    """Assemble + persist evidence ONCE at approval (idempotent → byte-identity).
    Returns rows written (0 if already frozen). Never raises into approval."""
    try:
        existing = await supabase_rest_get("recommendation_evidence", select="id",
                                           filters=f"assessment_id=eq.{assessment_id}", limit=1)
        if existing.status_code == 200 and existing.json():
            return 0  # already frozen — do not re-assemble (DIR-010 byte-identity)
        stacks = await assemble_evidence(assessment_id)
        rows = [{
            "id": str(uuid4()), "finding_id": s["finding_id"], "assessment_id": assessment_id,
            "obligation_refs": json.dumps(s["obligation_refs"]),
            "exemplar_clause_id": s["exemplar_clause_id"],
            "enforcement_refs": json.dumps(s["enforcement_refs"]),
            "absence_reason": s["absence_reason"],
            "risk_reduction_delta": None,
            "formula_version_id": s["formula_version_id"], "confidence": s["confidence"],
        } for s in stacks]
        if rows:
            await supabase_rest_post("recommendation_evidence", rows)
        return len(rows)
    except Exception as exc:  # noqa: BLE001 — evidence freeze must never fail approval
        log.warning("evidence freeze skipped for %s: %s", assessment_id[:12], exc)
        return 0


async def _resolve_finding_id(assessment_id: str, finding_ref: str) -> str | None:
    """The report identifies a finding by its CODE (assembly sets finding.id =
    finding_type_code), but recommendation_evidence keys on the risk_finding
    UUID. Resolve a code → finding_id for this assessment. A value that is
    already a UUID falls through unchanged."""
    fr = await supabase_rest_get(
        "risk_finding", select="finding_id",
        filters=f"notice_id=eq.{assessment_id}&finding_type_code=eq.{finding_ref}", limit=1)
    rows = fr.json() if fr.status_code == 200 else []
    return rows[0]["finding_id"] if rows else None


async def _read_evidence_row(assessment_id: str, finding_id: str) -> dict | None:
    r = await supabase_rest_get(
        "recommendation_evidence",
        select="finding_id,obligation_refs,exemplar_clause_id,enforcement_refs,absence_reason,"
               "risk_reduction_delta,formula_version_id,confidence,generated_at",
        filters=f"assessment_id=eq.{assessment_id}&finding_id=eq.{finding_id}", limit=1)
    rows = r.json() if r.status_code == 200 else []
    return rows[0] if rows else None


async def get_evidence(assessment_id: str, finding_ref: str) -> dict | None:
    """Read the frozen stack for one finding (never re-assembles). Accepts the
    risk_finding UUID OR the finding code the report uses as the id."""
    ev = await _read_evidence_row(assessment_id, finding_ref)      # UUID path
    if ev is None:
        resolved = await _resolve_finding_id(assessment_id, finding_ref)  # code → UUID
        if resolved:
            ev = await _read_evidence_row(assessment_id, resolved)
    if ev is None:
        return None

    def _j(v):
        return json.loads(v) if isinstance(v, str) else (v or [])

    obligation_refs = _j(ev.get("obligation_refs"))
    ar = ev.get("absence_reason")
    return {
        "finding_id": ev["finding_id"],
        "obligation_refs": obligation_refs,
        "obligation_register": OBLIGATION_REGISTER,
        "obligation_absence": ABSENCE.get(ar) if ar in ("out_of_scope", "below_floor") else None,
        "exemplar_clause_id": ev.get("exemplar_clause_id"),
        "exemplar_absence": ABSENCE["no_approved_exemplar"] if not ev.get("exemplar_clause_id") else None,
        "enforcement_refs": _j(ev.get("enforcement_refs")),
        "risk_reduction_delta": ev.get("risk_reduction_delta"),   # null → UI hides the row
        "formula_version_id": ev.get("formula_version_id"),
        "confidence": ev.get("confidence"),
        "generated_at": ev.get("generated_at"),
    }
