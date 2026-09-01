"""Report endpoints — IMMUTABLE snapshot-based report delivery.

GET /reports/{id} returns the STORED snapshot payload verbatim (deterministic).
Only re-assembles if no snapshot exists (not yet scored) or if ?refresh=true
(admin/sme only) — which writes a NEW snapshot and leaves prior ones intact.

All lists sorted by stable keys before serialization.
All dates frozen into the snapshot at creation time.
LLM-smoothed prose generated ONCE at snapshot time and stored.
"""

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser, require_role
from app.config import settings
from app.db import get_service_headers
from app.logging import get_logger
from app.services import guardrail
from app.services.ratelimit import check_rate_limit, client_key
from app.services.report.assembly import assemble_report, ReportPayload
from app.services.report.clause_data import (
    heatmap_counts,
    representative_clauses,
    select_comparators,
)
from app.services.report.renderer import find_unresolved_template_tokens, _strip_placeholders
from app.services.review import customer_can_view
from app.services.scoring.heatmap import build_regulator_heatmap, heatmap_to_serializable

log = get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

# SEC-005: PDF render is CPU+RAM heavy (WeasyPrint, serialized by _PDF_RENDER_SEM).
# ~20/min per user is comfortable for a human clicking Export/Preview but blocks a
# hammering loop before it reaches the render semaphore.
_PDF_LIMIT = 20
_PDF_WINDOW_S = 60

# PDF render is CPU+memory heavy (WeasyPrint). Serialize renders (semaphore=1) so
# concurrent exports can't exhaust a small VM's RAM; on contention fail fast with
# an honest "being prepared" 503 rather than piling up and OOMing. Combined with
# render_pdf running WeasyPrint in a worker thread, the event loop (and /health)
# stays responsive. UPGRADE TRIGGER: if these 503s recur with >1 concurrent user,
# resize the VM to 8 GB (see logs/archive/2026-07/LAUNCH-READINESS-v2.md).
import asyncio
_PDF_RENDER_SEM = asyncio.Semaphore(1)

SB_URL = settings.supabase_url

# object_type → score key mapping
SCORE_TYPE_MAP = {
    "regulatory_exposure": "f002",
    "benchmark_deviation": "f003",
    "enforcement_correlation": "f004",
    "disclosure_maturity": "f005",
    "transparency": "f006",
    "ai_transparency": "f007",
    "compound_risk": "f008",
    "confidence_weighted": "f009",
    "overall_intelligence": "f010",
    "benchmark_percentile": "f011",
}

# Spec VCI bands
_VCI_BANDS = [
    (90, 100, "Very High",  "Suitable for executive presentation without caveat"),
    (75, 89,  "High",       "Suitable for standard reporting"),
    (60, 74,  "Moderate",   "Include with confidence caveat"),
    (40, 59,  "Low",        "Present with clear confidence limitations"),
    (0,  39,  "Very Low",   "Do not present as definitive; route for review"),
]

_MATURITY_BANDS = [
    (90, 100, "Leading"), (75, 89, "Mature"), (60, 74, "Developing"),
    (40, 59, "Lagging"), (0, 39, "Deficient"),
]


def _sb_get(path: str) -> list[dict]:
    r = httpx.get(f"{SB_URL}/rest/v1/{path}", headers=get_service_headers(), timeout=15)
    return r.json() if r.status_code == 200 else []


def assessment_org_id(assessment_id: str) -> str | None:
    """Resolve the organization that owns an assessment (by notice_id, then by
    a snapshot, then treating the id itself as an organization_id)."""
    rows = _sb_get(f"privacy_notice?select=organization_id&notice_id=eq.{assessment_id}&limit=1")
    if rows:
        return rows[0].get("organization_id")
    rows = _sb_get(f"report_snapshot?select=organization_id&notice_id=eq.{assessment_id}&limit=1")
    if rows:
        return rows[0].get("organization_id")
    rows = _sb_get(f"organization?select=organization_id&organization_id=eq.{assessment_id}&limit=1")
    return rows[0].get("organization_id") if rows else None


def assert_customer_owns(assessment_id: str, user) -> None:
    """F10: a customer may only reach its own organization's assessments. Raises
    403 on any cross-tenant access. No-op for sme/admin."""
    if user.role != "customer":
        return
    if not user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No organization is associated with this account.")
    owner = assessment_org_id(assessment_id)
    # Unknown owner → treat as not-yours (never leak another org's data).
    if owner != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not permitted to view this assessment.")


def _vci_band(score: float) -> tuple[str, str]:
    for lo, hi, label, guidance in _VCI_BANDS:
        if lo <= score <= hi:
            return label, guidance
    return "Very Low", "Do not present as definitive; route for review"


def _maturity_band(score: float) -> str:
    for lo, hi, label in _MATURITY_BANDS:
        if lo <= score <= hi:
            return label
    return "Deficient"


# DATA-002: keys that carry NO meaningful content — they are volatile artifacts of
# WHEN/HOW a snapshot was built (dates, snapshot ids) or runtime envelope metadata
# (any leading-underscore key injected at store/read time). Including them makes the
# "content hash" change across days and snapshots for byte-identical scores, which
# weakens tamper-evidence: two reports with identical findings/scores/narrative must
# hash IDENTICALLY, and any change to that meaningful content must change the hash.
#
# We strip these recursively, wherever they appear in the (nested) report dict —
# `date` and `snapshot_id` are baked into several section `content` blocks by
# assembly.py, so a top-level-only strip would not be enough.
#
# Two of these keys (`cohort_label`, `note`) hold DERIVED PROSE that embeds the
# volatile date/snapshot id INSIDE a free-text string, where a key-based strip
# can't reach it. They carry no content that isn't already covered structurally
# (`cohort_size`, `snapshot_id`, the score/finding fields), so excluding the whole
# string is safe and keeps the hash pure.
_CONTENT_HASH_EXCLUDE_KEYS = frozenset({
    "date",            # date.today()/cohort_date baked into cover + dashboard sections
    "generated_date",  # ReportPayload.generated_date (== cohort_date, volatile)
    "cohort_date",     # the "as of <date>" stamp — a timestamp, not content
    "as_of_date",      # peer-methodology presentation stamp; population version is retained
    "snapshot_id",     # per-build UUID baked into cover/dashboard/traceability sections
    "cohort_label",    # derived prose: "n=<size> peers as of <date>" (embeds the date)
    "note",            # derived prose: "...via snapshot <id>...as of <date>" (embeds both)
})


def _canonicalize_for_hash(value):
    """Return a copy of `value` with all volatile/runtime keys removed, recursively.

    Excluded (see _CONTENT_HASH_EXCLUDE_KEYS): `date`, `generated_date`,
    `cohort_date`, `snapshot_id`, and the derived-prose `cohort_label`/`note`
    (which embed the date/snapshot id inside free text). Also excluded: ANY key
    beginning with an underscore (`_content_hash`, `_snapshot_id`,
    `_report_version`, `_generated_at`
    and any future `_*` runtime metadata) — these are envelope fields injected at
    store/read time, never meaningful content.

    Everything else — scores, findings, approved narrative text, config,
    formula/version refs, cohort_size, etc. — is preserved so a change to any of it
    changes the hash (tamper-evidence).
    """
    if isinstance(value, dict):
        return {
            k: _canonicalize_for_hash(v)
            for k, v in value.items()
            if not (isinstance(k, str) and (k.startswith("_") or k in _CONTENT_HASH_EXCLUDE_KEYS))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize_for_hash(v) for v in value]
    return value


def _content_hash(data: dict) -> str:
    """DATA-002: deterministic SHA-256 of ONLY the meaningful, immutable content.

    Volatile fields (dates, snapshot_id) and runtime `_*` metadata are stripped
    (see _canonicalize_for_hash) BEFORE canonical serialization, so byte-identical
    scores/findings/narrative always yield the same hash regardless of the day or
    snapshot in which the report was assembled — while any change to the actual
    content still changes the hash.
    """
    canonical = json.dumps(_canonicalize_for_hash(data), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# domain_id (CR/DC/…) → legacy_slug used by the report's your-text lookup.
# Sourced from config/clause_taxonomy.json — authoritative, never invented.
_DOMAIN_ID_TO_SLUG: dict[str, str] = {}


def _domain_id_to_slug() -> dict[str, str]:
    global _DOMAIN_ID_TO_SLUG
    if not _DOMAIN_ID_TO_SLUG:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "clause_taxonomy.json")
        try:
            with open(os.path.abspath(path), encoding="utf-8") as fh:
                for entry in json.load(fh):
                    did = entry.get("domain_id")
                    slug = entry.get("legacy_slug")
                    # First non-"other" slug per domain wins (a domain's canonical slug).
                    if did and slug and slug != "other" and did not in _DOMAIN_ID_TO_SLUG:
                        _DOMAIN_ID_TO_SLUG[did] = slug
        except (OSError, ValueError, KeyError, TypeError) as e:
            # BACK-003: don't swallow KeyboardInterrupt/SystemExit; log the
            # taxonomy-load failure (path + error type, no secrets) and fall back
            # to an empty map — the your-text lookup then renders honest absence.
            log.warning("clause_taxonomy load failed (%s): %s; using empty slug map",
                        type(e).__name__, e)
    return _DOMAIN_ID_TO_SLUG


def _load_exemplar_clauses(org_clauses: dict[str, dict]) -> list[dict]:
    """Approved exemplars gated by domain, similarity, and stored maturity."""
    rows = _sb_get(
        "disclosure_clause?select=clause_id,domain_id,category,category_v2,normalized_text,raw_text,"
        "embedding,transparency_score,is_exemplar,exemplar_status"
        "&is_exemplar=eq.true&exemplar_status=eq.approved"
    )
    return select_comparators(org_clauses, rows, _domain_id_to_slug())


def _load_report_clause_rows(notice_id: str) -> tuple[list[dict], dict[str, dict]]:
    """One report-layer clause read, scoped through live ``notice_section``.

    Live-schema introspection on 2026-08-21 confirmed that
    ``disclosure_clause.notice_id`` is absent, so direct notice filtering would
    silently return no rows. Every report consumer receives this same result.
    """
    sections = _sb_get(
        f"notice_section?select=section_id,title,sequence&notice_id=eq.{notice_id}&order=sequence.asc"
    )
    section_map = {str(s.get("section_id")): s for s in sections if s.get("section_id")}
    section_ids = list(section_map)
    rows: list[dict] = []
    for i in range(0, len(section_ids), 40):
        chunk = section_ids[i:i + 40]
        id_list = ",".join(f'"{sid}"' for sid in chunk)
        part = _sb_get(
            "disclosure_clause?select=clause_id,section_id,domain_id,category,category_v2,"
            "normalized_text,raw_text,nlp_confidence,nlp_confidence_v2,transparency_score,"
            "ambiguity_score,embedding,is_noise"
            f"&section_id=in.({id_list})&limit=2000"
        )
        for row in part:
            section = section_map.get(str(row.get("section_id"))) or {}
            row["section_title"] = section.get("title")
            row["section_sequence"] = section.get("sequence")
            rows.append(row)
    rows.sort(key=lambda row: (row.get("section_sequence") or 0, str(row.get("clause_id") or "")))
    return rows, section_map


# ── Endpoints ────────────────────────────────────────────────

@router.get("/{assessment_id}")
async def get_report(
    assessment_id: str,
    refresh: Optional[bool] = Query(None),
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return the report. Snapshot-first (deterministic); ?refresh=true for new version."""
    if user.role == "customer":
        # F10: verify org ownership BEFORE the gate check — never leak another
        # org's report even when gate mode would otherwise allow viewing.
        assert_customer_owns(assessment_id, user)
        can_view, banner = customer_can_view(assessment_id)
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Report pending expert review (gate_mode=strict).",
            )
    else:
        banner = ""

    # Try stored snapshot first (deterministic)
    if not refresh:
        stored = _load_stored_report(assessment_id)
        if stored:
            if banner:
                stored["draft_banner"] = banner
            return stored

    # No snapshot OR refresh requested (admin/sme only for refresh)
    if refresh and user.role not in ("sme", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SME/admin can refresh a report.",
        )

    # Assemble from live data
    report = _assemble_from_live(assessment_id)
    result = asdict(report)

    # Store as new immutable snapshot
    _store_snapshot(assessment_id, result)

    if banner:
        result["draft_banner"] = banner
    return result


@router.get("/{assessment_id}/pdf")
async def get_report_pdf(
    assessment_id: str,
    request: Request,
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Render the report as PDF. Uses stored snapshot for determinism."""
    from app.services.report.renderer import render_pdf

    # SEC-005: throttle before any snapshot load or render work.
    check_rate_limit(client_key(request, user), limit=_PDF_LIMIT, window_s=_PDF_WINDOW_S)

    # F10: a customer may only export its own organization's report.
    assert_customer_owns(assessment_id, user)

    # Try snapshot first
    stored = _load_stored_report(assessment_id)
    if stored:
        # Reconstruct ReportPayload from stored dict
        from app.services.report.assembly import ReportSection
        sections = [
            ReportSection(number=s["number"], title=s["title"], content=s.get("content", {}))
            for s in stored.get("sections", [])
        ]
        report = ReportPayload(
            assessment_id=stored.get("assessment_id", assessment_id),
            organization_name=stored.get("organization_name", ""),
            generated_date=stored.get("generated_date", ""),
            sections=sections,
            cohort_size=stored.get("cohort_size", 0),
            cohort_date=stored.get("cohort_date", ""),
            vci_label=stored.get("vci_label", ""),
        )
    else:
        report = _assemble_from_live(assessment_id)

    # Fail fast on contention (another render in flight) — honest, retryable.
    if _PDF_RENDER_SEM.locked():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The report is being prepared. Please retry in a moment.",
            headers={"Retry-After": "3"},
        )
    async with _PDF_RENDER_SEM:
        pdf_bytes = await render_pdf(report, renderer=settings.renderer)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{assessment_id[:12]}.pdf"},
    )


# ── Snapshot storage ─────────────────────────────────────────

def _load_stored_report(assessment_id: str) -> dict | None:
    """Load the latest rendered_report from report_snapshot. Returns None if not found."""
    snapshots = _sb_get(
        f"report_snapshot?select=snapshot_id,rendered_report,content_hash,"
        f"report_version,created_at"
        f"&notice_id=eq.{assessment_id}"
        f"&order=created_at.desc&limit=1"
    )
    if not snapshots:
        snapshots = _sb_get(
            f"report_snapshot?select=snapshot_id,rendered_report,content_hash,"
            f"report_version,created_at"
            f"&organization_id=eq.{assessment_id}"
            f"&order=created_at.desc&limit=1"
        )

    if not snapshots:
        return None

    snap = snapshots[0]
    rendered = snap.get("rendered_report")
    if not rendered:
        return None

    if isinstance(rendered, str):
        try:
            rendered = json.loads(rendered)
        except Exception:
            return None

    # Inject snapshot metadata into the report
    rendered["_snapshot_id"] = snap.get("snapshot_id", "")
    rendered["_report_version"] = snap.get("report_version", 1)
    rendered["_content_hash"] = snap.get("content_hash", "")
    rendered["_generated_at"] = snap.get("created_at", "")

    return rendered


def _store_snapshot(assessment_id: str, report_dict: dict) -> str:
    """Store a new immutable snapshot. Returns the snapshot_id."""
    from uuid import uuid4

    snapshot_id = str(uuid4())
    ch = _content_hash(report_dict)

    # Determine report_version (max existing + 1)
    existing = _sb_get(
        f"report_snapshot?select=report_version"
        f"&notice_id=eq.{assessment_id}"
        f"&order=report_version.desc&limit=1"
    )
    version = (existing[0]["report_version"] + 1) if existing and existing[0].get("report_version") else 1

    # Add version metadata to the report
    report_dict["_snapshot_id"] = snapshot_id
    report_dict["_report_version"] = version
    report_dict["_content_hash"] = ch

    # Resolve org_id
    notices = _sb_get(f"privacy_notice?select=organization_id&notice_id=eq.{assessment_id}&limit=1")
    org_id = notices[0]["organization_id"] if notices else ""

    sections_by_number = {
        section.get("number"): section.get("content", {})
        for section in report_dict.get("sections", [])
        if isinstance(section, dict)
    }
    benchmark_method = sections_by_number.get(4, {}).get("methodology", {}) or {}
    extraction_quality = sections_by_number.get(11, {}).get("extraction_quality", {}) or {}
    payload = {
        "snapshot_id": snapshot_id,
        "organization_id": org_id,
        "notice_id": assessment_id,
        "rendered_report": json.dumps(report_dict, sort_keys=True, default=str),
        "content_hash": ch,
        "report_version": version,
        "payload": json.dumps({
            "cohort_size": report_dict.get("cohort_size", 0),
            "cohort_date": report_dict.get("cohort_date", ""),
            "population_key": benchmark_method.get("population_key"),
            "relaxations": benchmark_method.get("relaxations", []),
            "benchmark_population_version": benchmark_method.get("benchmark_population_version"),
            "confidence_penalty": benchmark_method.get("confidence_penalty"),
            "scored_clause_count": extraction_quality.get("scored_clause_count"),
        }),
        "formula_version_set": json.dumps([]),
        "scoring_model_version": settings.scoring_model_version,
        "glossary_version": "glossary-v1",
        "template_version": "template-v1",
    }

    headers = {**get_service_headers(), "Content-Type": "application/json", "Prefer": "return=minimal"}
    httpx.post(f"{SB_URL}/rest/v1/report_snapshot", headers=headers, json=payload, timeout=15)

    return snapshot_id


# ── Live assembly (only when no snapshot exists) ─────────────

def _extract_scores(derived_rows: list[dict]) -> tuple[dict, float | None]:
    scores: dict[str, dict] = {}
    seen: set[str] = set()
    vci_confidence: float | None = None

    for d in derived_rows:
        otype = d.get("object_type", "")
        fkey = SCORE_TYPE_MAP.get(otype)
        if not fkey or fkey in seen:
            continue

        lineage = d.get("source_lineage")
        if isinstance(lineage, str):
            try:
                lineage = json.loads(lineage)
            except Exception:
                lineage = {}

        score_val = d.get("score") or d.get("value") or 0
        tier = d.get("value_label") or ""
        band = _maturity_band(score_val) if fkey in ("f010", "f005") else ""

        scores[fkey] = {
            "score": score_val,
            "tier": tier,
            "band": band,
            "lineage": lineage or {},
        }
        seen.add(fkey)

        if otype == "overall_intelligence":
            vci_confidence = d.get("confidence_score")

    return scores, vci_confidence


def _enforce_snapshot_prose(
    exec_summary: str,
    takeaways: list[str],
    recommendations: list[dict],
) -> dict:
    """GRD-001: run the ONE canonical guardrail over EVERY generated string that
    enters the snapshot — exec summary, takeaways, and each recommendation's
    title + body (recommendation_library.body_template). Fail closed per Hard
    Rule 1 ("the phrasing guardrail … must hard-fail report builds containing a
    banned term"): guardrail.enforce raises GuardrailError, which aborts the
    build so no legal-verdict language can reach a snapshot.

    Peer/org clause text and exemplars are NOT passed here — they are cited
    source material, not generated prose, and the guardrail exempts source
    excerpts (business-logic.md §2).

    Returns the real result to persist in snapshot lineage; GRD-002's receipt
    displays this instead of a hardcoded default.
    """
    strings = [exec_summary, *takeaways]
    for r in recommendations:
        strings.append(r.get("title", ""))
        strings.append(r.get("prose", ""))

    checked = 0
    unresolved: list[str] = []
    for s in strings:
        if s:
            unresolved.extend(find_unresolved_template_tokens(s))
            guardrail.enforce(s)  # raises GuardrailError on a banned term → fail closed
            checked += 1

    if unresolved:
        tokens = sorted(set(unresolved))
        raise guardrail.GuardrailError(
            f"Guardrail HARD FAIL — unresolved authored template tokens: {tokens}.",
            terms=tokens,
        )

    return {
        "status": "passed",
        "strings_checked": checked,
        "template_tokens": {"status": "passed", "unresolved": []},
    }



#: Severity rank for ordering observations. Lower sorts first.
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "elevated": 2, "low": 3}


def _significance_key(f: dict) -> tuple:
    """Order observations by SIGNIFICANCE, not by code.

    Findings were sorted alphabetically by `finding_type_code`, and the executive
    takeaways and recommendations took `findings[:5]` — so the report led with
    the five findings whose codes happened to sort first. A low-severity
    "AI-004" displaced a high-severity "SH-002" because A precedes S.

    Every assurance-reporting structure orders observations by significance, and
    a reader reasonably assumes the first thing named is the most important one.

    The code is the final tiebreak so the order stays DETERMINISTIC: two renders
    of the same snapshot must produce identical bytes (Hard Rule 6), which a
    non-total ordering would break.
    """
    sev = (f.get("severity") or "").lower()
    score = f.get("score")
    return (
        _SEVERITY_RANK.get(sev, 9),
        -(score if isinstance(score, (int, float)) else 0.0),
        f.get("code") or f.get("finding_type_code") or "",
    )


def _recommendation_basis_label(finding: dict, selected_laws: set[str]) -> str:
    """Classify a recommendation's basis from STORED references only — never an
    LLM guess (RPT-009). Precedence, strongest signal first:
      1. an obligation in a law the user actually selected  -> scoped requirement
      2. a regulator enforcement reference                  -> regulator signal
      3. a peer-benchmark reference                          -> benchmark
      4. an obligation that exists but is OUTSIDE the selected scope -> general
         requirement (surfaced distinctly so a real signal is not hidden)
      5. nothing stored                                     -> honest absence
    Labels are verdict-free (Hard Rule 1); see the guardrail test matrix.
    """
    obligation_jurisdictions: set[str] = set()
    for ref in finding.get("obligation_refs", []):
        if isinstance(ref, dict):
            value = ref.get("jurisdiction") or ref.get("law") or ref.get("code")
        else:
            value = ref
        if value:
            obligation_jurisdictions.add(str(value))
    if selected_laws & obligation_jurisdictions:
        return "Selected-scope requirement context"
    if finding.get("enforcement_refs"):
        return "Regulator sensitivity context"
    if finding.get("benchmark_reference"):
        return "Peer benchmark context"
    if obligation_jurisdictions:
        return "General requirement context (outside selected scope)"
    return "Basis not recorded"


def _assemble_from_live(assessment_id: str) -> ReportPayload:
    """Assemble report from live DB data. Used when no snapshot exists."""

    notices = _sb_get(
        f"privacy_notice?select=notice_id,organization_id,url,retrieval_date,effective_date,"
        f"intake_method,upload_filename"
        f"&notice_id=eq.{assessment_id}&limit=1"
    )
    if not notices:
        notices = _sb_get(
            f"privacy_notice?select=notice_id,organization_id,url,retrieval_date,effective_date,"
            f"intake_method,upload_filename"
            f"&organization_id=eq.{assessment_id}"
            f"&order=retrieval_date.desc&limit=1"
        )
    if not notices:
        raise HTTPException(status_code=404, detail="Assessment not found")

    notice = notices[0]
    # Schema aliases: privacy_notice stores url/retrieval_date, but the report layer
    # historically referenced source_url/capture_date. Map them so downstream
    # provenance fields keep resolving. (No notice-version column exists → stays unset.)
    notice.setdefault("source_url", notice.get("url"))
    notice.setdefault("capture_date", notice.get("retrieval_date"))
    notice_id = notice["notice_id"]
    org_id = notice["organization_id"]

    orgs = _sb_get(
        f"organization?select=name,industry,industry_source,size,public_private,geography,jurisdiction_presence"
        f"&organization_id=eq.{org_id}&limit=1"
    )
    org = orgs[0] if orgs else {"name": "Unknown Organization", "industry": "unknown", "size": "", "geography": ""}
    org_name = org["name"]
    scope_rows = _sb_get(
        f"assessment_intake_scope?select=organization_name,organization_size,public_private,geography,"
        f"state_footprint,selected_laws,data_categories,business_practices,provenance"
        f"&notice_id=eq.{notice_id}&limit=1"
    )
    intake_scope = scope_rows[0] if scope_rows else {}

    # Scores
    derived = _sb_get(
        f"derived_data_item?select=object_type,score,value,value_label,"
        f"confidence_score,source_lineage"
        f"&notice_id=eq.{notice_id}&order=generated_at.desc&limit=50"
    )
    if not derived:
        derived = _sb_get(
            f"derived_data_item?select=object_type,score,value,value_label,"
            f"confidence_score,source_lineage"
            f"&organization_id=eq.{org_id}&order=generated_at.desc&limit=50"
        )

    scores, vci_confidence = _extract_scores(derived)

    # One report-layer clause read feeds heatmap, benchmark language, findings,
    # recommendations, and traceability. Noise semantics match score_notice().
    clause_rows, _section_map = _load_report_clause_rows(notice_id)
    slug_map = _domain_id_to_slug()
    clause_cats = heatmap_counts(clause_rows, slug_map)
    org_clauses_by_domain = representative_clauses(clause_rows, slug_map)
    clauses_by_id = {str(row.get("clause_id")): row for row in clause_rows if row.get("clause_id")}

    # Findings — sorted by code for determinism
    findings_raw = _sb_get(
        f"risk_finding?select=finding_id,finding_type_code,severity,score,domain,confidence_score,"
        f"formula_version_id,benchmark_deviation_score"
        f"&notice_id=eq.{notice_id}&order=finding_type_code.asc&limit=20"
    )
    if not findings_raw:
        findings_raw = _sb_get(
            f"risk_finding?select=finding_id,finding_type_code,severity,score,domain,confidence_score,"
            f"formula_version_id,benchmark_deviation_score"
            f"&organization_id=eq.{org_id}&order=finding_type_code.asc&limit=20"
        )

    finding_ids = [str(row.get("finding_id")) for row in findings_raw if row.get("finding_id")]
    finding_clause_map: dict[str, list[str]] = {}
    if finding_ids:
        ids = ",".join(f'"{fid}"' for fid in finding_ids)
        for link in _sb_get(f"finding_clause?select=finding_id,clause_id&finding_id=in.({ids})&limit=2000"):
            finding_clause_map.setdefault(str(link.get("finding_id")), []).append(str(link.get("clause_id")))

    evidence_by_finding: dict[str, dict] = {}
    if finding_ids:
        ids = ",".join(f'"{fid}"' for fid in finding_ids)
        for row in _sb_get(
            "recommendation_evidence?select=finding_id,obligation_refs,enforcement_refs,"
            f"formula_version_id,confidence&assessment_id=eq.{notice_id}&finding_id=in.({ids})&limit=200"
        ):
            evidence_by_finding[str(row.get("finding_id"))] = row

    source_reference = notice.get("source_url") or notice.get("upload_filename") or "Not recorded"
    findings: list[dict] = []
    seen_codes: set[str] = set()
    for f in sorted(findings_raw, key=lambda x: x.get("finding_type_code", "")):
        code = f.get("finding_type_code") or ""
        if code and code not in seen_codes:
            finding_id = str(f.get("finding_id") or "")
            clause_ids = sorted(set(finding_clause_map.get(finding_id, [])))
            evidence = []
            for clause_id in clause_ids:
                row = clauses_by_id.get(clause_id)
                if not row:
                    continue
                title = row.get("section_title")
                sequence = row.get("section_sequence")
                section_reference = title or (f"Section {sequence}" if sequence is not None else "Not recorded")
                excerpt = str(row.get("raw_text") or row.get("normalized_text") or "")[:500]
                evidence.append({
                    "clause_id": clause_id,
                    "section_reference": section_reference,
                    "excerpt": excerpt,
                    "source_reference": source_reference,
                    "notice_version": notice.get("notice_version"),
                    "capture_date": notice.get("capture_date"),
                })
            frozen = evidence_by_finding.get(finding_id) or {}
            obligation_refs = frozen.get("obligation_refs") or []
            enforcement_refs = frozen.get("enforcement_refs") or []
            if isinstance(obligation_refs, str):
                try:
                    obligation_refs = json.loads(obligation_refs)
                except (TypeError, ValueError):
                    obligation_refs = []
            if isinstance(enforcement_refs, str):
                try:
                    enforcement_refs = json.loads(enforcement_refs)
                except (TypeError, ValueError):
                    enforcement_refs = []
            findings.append({
                "finding_id": finding_id,
                "code": code,
                "domain": f.get("domain", ""),
                "severity": f.get("severity", "medium"),
                "score": f.get("score", 0),
                "confidence": frozen.get("confidence") or f.get("confidence_score"),
                "formula_version": frozen.get("formula_version_id") or f.get("formula_version_id"),
                "clause_ids": clause_ids,
                "evidence": evidence,
                "obligation_refs": obligation_refs,
                "enforcement_refs": enforcement_refs,
                "benchmark_reference": (
                    {"score": f.get("benchmark_deviation_score"), "formula": "F-003"}
                    if f.get("benchmark_deviation_score") is not None else None
                ),
            })
            seen_codes.add(code)

    # VCI
    if vci_confidence is not None:
        vci_score = vci_confidence * 100
        vci_label, vci_guidance = _vci_band(vci_score)
        vci = {"score": round(vci_score, 1), "label": vci_label, "guidance": vci_guidance}
    else:
        vci_label = "not_recorded"
        vci = {"score": None, "label": vci_label,
               "guidance": "Confidence was not recorded for this assessment."}

    # Cohort from existing snapshot metadata
    snap_rows = _sb_get(
        f"report_snapshot?select=snapshot_id,payload,created_at,benchmark_population_version"
        f"&notice_id=eq.{notice_id}&order=created_at.desc&limit=1"
    )
    if snap_rows:
        sp = snap_rows[0]
        snap_payload = sp.get("payload", {})
        if isinstance(snap_payload, str):
            try:
                snap_payload = json.loads(snap_payload)
            except (ValueError, TypeError) as e:
                # BACK-003: narrow the bare except (no KeyboardInterrupt/SystemExit);
                # log the malformed-payload context (notice id + error, no secrets)
                # before falling back to an empty cohort payload.
                log.warning("snapshot payload not valid JSON for notice=%s (%s): %s",
                            notice_id[:12], type(e).__name__, e)
                snap_payload = {}
        cohort_size = snap_payload.get("cohort_size", 0)
        cohort_date = (sp.get("created_at") or "")[:10]
        snapshot_id = sp["snapshot_id"]
        population_key = snap_payload.get("population_key")
        relaxations = snap_payload.get("relaxations") or []
        population_version = (
            snap_payload.get("benchmark_population_version")
            or sp.get("benchmark_population_version")
        )
        confidence_penalty = snap_payload.get("confidence_penalty")
        stored_scored_clause_count = snap_payload.get("scored_clause_count")
    else:
        cohort_size = 0
        cohort_date = ""
        snapshot_id = ""
        population_key = None
        relaxations = []
        population_version = None
        confidence_penalty = None
        stored_scored_clause_count = scores.get("f002", {}).get("lineage", {}).get("total_clauses")

    actual_scored_clause_count = sum(clause_cats.values())
    if isinstance(stored_scored_clause_count, (int, float)):
        quality_status = (
            "mismatch" if int(stored_scored_clause_count) != actual_scored_clause_count
            else "insufficient" if actual_scored_clause_count == 0
            else "passed"
        )
        extraction_quality = {
            "status": quality_status,
            "scored_clause_count": int(stored_scored_clause_count),
            "report_clause_count": actual_scored_clause_count,
        }
    else:
        extraction_quality = {
            "status": "insufficient" if actual_scored_clause_count == 0 else "not_recorded",
            "scored_clause_count": None,
            "report_clause_count": actual_scored_clause_count,
        }

    parts = str(population_key or "").split("|") if population_key else []
    from app.services.intake_options import (
        BENCHMARK_DIMENSION_LABELS,
        LOW_CONFIDENCE_COHORT_N,
        benchmark_relaxation_label,
    )
    dimensions = [
        f"{name}: {value}"
        for name, value in zip(BENCHMARK_DIMENSION_LABELS, parts)
        if value
    ]
    if dimensions and org.get("industry"):
        dimensions[0] = f"Industry: {org.get('industry')}"
    cohort_methodology = {
        "population_key": population_key,
        "dimensions": dimensions,
        "relaxations": [benchmark_relaxation_label(str(value)) for value in relaxations],
        "benchmark_population_version": population_version,
        "confidence_penalty": confidence_penalty,
        "as_of_date": cohort_date,
        "low_confidence": 0 < cohort_size < LOW_CONFIDENCE_COHORT_N,
        "low_confidence_threshold": LOW_CONFIDENCE_COHORT_N,
    } if population_key or population_version else {}

    # Narrative — frozen at assembly time
    overall_score = scores.get("f010", {}).get("score", 0)
    overall_band = _maturity_band(overall_score) if overall_score > 0 else ""
    percentile = scores.get("f011", {}).get("score", 0)

    if scores:
        cohort_desc = f"n={cohort_size} peers" if cohort_size > 0 else "cohort not yet constructed"
        exec_summary = (
            f"{org_name} presents an overall privacy intelligence score of "
            f"{overall_score:.1f} out of 100"
            f"{f' ({overall_band})' if overall_band else ''}"
            f", placing it at the {percentile:.1f}th percentile "
            f"within its peer cohort ({cohort_desc}"
            f"{f', as of {cohort_date}' if cohort_date else ''}). "
            f"The assessment identified {len(findings)} areas of elevated exposure. "
            f"Confidence level: {vci_label}."
        )
    else:
        exec_summary = (
            f"Scoring for {org_name} has not yet completed. "
            f"Clause decomposition is available; scores will appear once the scoring pipeline runs."
        )

    # Observations in order of significance. `findings` itself is re-ordered so
    # every downstream section (findings table, risk reduction, traceability)
    # inherits the same order rather than each picking its own.
    findings.sort(key=_significance_key)
    top_findings = findings[:5]

    takeaways = []
    for f in top_findings:
        sev = "elevated" if f["severity"] == "high" else "moderate"
        takeaways.append(
            f"The {f['domain'].replace('_', ' ')} domain presents {sev} exposure "
            f"(finding {f['code']}, score {f['score']:.1f}/100)."
        )

    # Load real recommendations from recommendation_library
    rec_lib = _sb_get(
        "recommendation_library?select=finding_type_code,title,body_template,severity_bucket,source_note"
    )
    rec_map = {r["finding_type_code"]: r for r in rec_lib}

    recommendations = []
    for f in top_findings:
        rec = rec_map.get(f["code"])
        if rec:
            selected_laws = set(intake_scope.get("selected_laws") or [])
            basis_label = _recommendation_basis_label(f, selected_laws)
            recommendations.append({
                "severity": f["severity"],
                "code": f["code"],
                "title": rec["title"],
                # Strip un-substituted authored tokens (e.g. {missing_elements}) the
                # same way the PDF renderer does (renderer._strip_placeholders, Part C
                # §10 / Part E), so the assembly guardrail — which fails closed on any
                # unresolved token — only trips on genuinely bad prose, and the JSON
                # report matches the rendered PDF.
                "prose": _strip_placeholders(rec["body_template"]),
                "source_note": rec.get("source_note"),
                "basis_label": basis_label,
                "evidence": f.get("evidence", []),
                "obligation_refs": f.get("obligation_refs", []),
                "enforcement_refs": f.get("enforcement_refs", []),
                "benchmark_reference": f.get("benchmark_reference"),
            })
        else:
            recommendations.append({
                "severity": f["severity"],
                "code": f["code"],
                "title": f"{f['code']} — authored recommendation unavailable",
                "prose": "No authored recommendation exists for this finding type yet.",
                "basis_label": "Basis not recorded",
                "evidence": f.get("evidence", []),
            })

    # Heatmap
    regulators = _sb_get("regulator?select=regulator_id,name,jurisdiction,priority_weights,enforcement_frequency_weight")
    heatmap = heatmap_to_serializable(build_regulator_heatmap(regulators, clause_cats))

    # M-03: best-practice exemplars come from the approved `disclosure_clause`
    # exemplars (is_exemplar=true, exemplar_status=approved — de-id-passing).
    # A domain with no approved exemplar simply renders honest absence.
    exemplars = _load_exemplar_clauses(org_clauses_by_domain)

    # GRD-001: enforce the guardrail on ALL generated prose before it can enter a
    # snapshot. Fails closed on a banned term; records the real result for lineage.
    guardrail_result = _enforce_snapshot_prose(exec_summary, takeaways, recommendations)

    provenance = intake_scope.get("provenance") or {}
    if isinstance(provenance, str):
        try:
            provenance = json.loads(provenance)
        except (TypeError, ValueError):
            provenance = {}

    def _scope_item(key: str, value, fallback_source: str = "not_recorded") -> dict:
        return {"value": value, "provenance": provenance.get(key, fallback_source)}

    assessment_scope = {
        "source": _scope_item(
            "source", notice.get("source_url") or notice.get("upload_filename"), "captured"
        ),
        "notice_version": _scope_item("notice_version", notice.get("notice_version"), "captured"),
        "capture_date": _scope_item("capture_date", notice.get("capture_date"), "captured"),
        "effective_date": _scope_item("effective_date", notice.get("effective_date"), "captured"),
        "intake_method": _scope_item("intake_method", notice.get("intake_method"), "captured"),
        "organization_name": _scope_item(
            "organization_name", intake_scope.get("organization_name") or org_name,
            "inferred" if not intake_scope.get("organization_name") else "user_declared",
        ),
        "organization_size": _scope_item(
            "organization_size", intake_scope.get("organization_size") or org.get("size"),
            "inferred" if not intake_scope.get("organization_size") else "user_declared",
        ),
        "public_private": _scope_item(
            "public_private", intake_scope.get("public_private") or org.get("public_private"),
            "inferred" if not intake_scope.get("public_private") else "user_declared",
        ),
        "geography": _scope_item(
            "geography", intake_scope.get("geography") or org.get("geography"),
            "inferred" if not intake_scope.get("geography") else "user_declared",
        ),
        "industry": _scope_item(
            "industry", org.get("industry"),
            "user_declared" if org.get("industry_source") == "user_provided" else "inferred",
        ),
        "cohort_definition": _scope_item(
            "cohort_definition", cohort_methodology.get("dimensions"), "stored_benchmark"
        ),
        "state_footprint": _scope_item(
            "state_footprint",
            intake_scope.get("state_footprint") or org.get("jurisdiction_presence"),
            "inferred" if not intake_scope.get("state_footprint") else "user_declared",
        ),
        "selected_laws": _scope_item("selected_laws", intake_scope.get("selected_laws")),
        "data_categories": _scope_item("data_categories", intake_scope.get("data_categories")),
        "business_practices": _scope_item("business_practices", intake_scope.get("business_practices")),
    }

    return assemble_report(
        assessment_id=assessment_id,
        org_name=org_name,
        scores=scores,
        findings=findings,
        vci=vci,
        narrative_exec=exec_summary,
        narrative_takeaways=takeaways,
        narrative_recommendations=recommendations,
        exemplars=exemplars,
        enforcement_heatmap=heatmap,
        cohort_size=cohort_size,
        cohort_date=cohort_date,
        snapshot_id=snapshot_id,
        org_clauses_by_domain=org_clauses_by_domain,
        guardrail_result=guardrail_result,
        extraction_quality=extraction_quality,
        cohort_methodology=cohort_methodology,
        assessment_scope=assessment_scope,
    )
