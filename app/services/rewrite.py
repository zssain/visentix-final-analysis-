"""F18 — Clause Rewrite (illustrative, guardrailed).

An illustrative rewrite of a weak clause — clearer structure, peer-informed
phrasing — that NEVER adds a practice, recipient, purpose, or commitment the
clause didn't already make. Every output passes BOTH the banned-term guardrail
AND a fabrication-verification step; any failure falls back to a side-by-side
comparison against an approved exemplar. A rewrite is NEVER surfaced unless
BOTH gates pass.
"""

from __future__ import annotations

import difflib
import json
import re
from uuid import uuid4

from app.db import supabase_rest_get, supabase_rest_post
from app.logging import get_logger
from app.services.guardrail import check_generated_prose, load_banned_terms
from app.services.narrative import verify_rephrased

log = get_logger(__name__)

PROMPT_VERSION = "rewrite_v1"
MODEL_VERSION = "llm-phrase"
WATERMARK = "Illustrative language based on peer patterns — not legal drafting. Review with counsel."

# Data-practice recipient/purpose terms whose NEW appearance in a rewrite (absent
# from clause ∪ exemplars) signals a fabricated fact.
PURPOSE_TERMS = {
    "advertising", "advertisers", "advertising partners", "marketing", "third parties",
    "third-party", "third party", "partners", "affiliates", "sell", "sold", "biometric",
    "profiling", "broker", "brokers", "location", "geolocation", "resold",
}
_CAP = re.compile(r"\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})*)\b")
_COMMON_CAPS = {"We", "You", "Your", "This", "The", "Our", "If", "When", "Where", "They", "It"}


# ── Fabrication verification (extends narrative.verify_rephrased) ──

def _candidate_additions(rewrite: str, allowed_text: str) -> set[str]:
    """Named entities + purpose phrases in the rewrite ABSENT from clause∪exemplars."""
    allowed = allowed_text.lower()
    low = rewrite.lower()
    hits: set[str] = set()
    for term in PURPOSE_TERMS:
        if term in low and term not in allowed:
            hits.add(term)
    for m in _CAP.findall(rewrite):
        if m in _COMMON_CAPS:
            continue
        if m.lower() not in allowed:
            hits.add(m)
    return hits


def verify_rewrite(clause_text: str, exemplar_texts: list[str], rewrite: str) -> tuple[bool, str]:
    """Reject any factual addition (number, entity, or purpose phrase) absent
    from clause ∪ exemplars. Returns (passed, reason)."""
    allowed = clause_text + " " + " ".join(exemplar_texts)
    ok, reason = verify_rephrased(clause_text, rewrite)   # numbers (+ lost numbers)
    if not ok:
        return False, reason
    adds = _candidate_additions(rewrite, allowed)
    if adds:
        return False, f"factual additions absent from clause+exemplars: {sorted(adds)}"
    return True, "ok"


def word_diff(before: str, after: str) -> list[dict]:
    """Token-level diff (gold added / warm-gray struck) — same shape the
    BenchmarkLanguage renderer consumes. Deterministic."""
    b, a = before.split(), after.split()
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=b, b=a).get_opcodes():
        if tag == "equal":
            ops.append({"op": "eq", "text": " ".join(b[i1:i2])})
        elif tag == "delete":
            ops.append({"op": "del", "text": " ".join(b[i1:i2])})
        elif tag == "insert":
            ops.append({"op": "add", "text": " ".join(a[j1:j2])})
        elif tag == "replace":
            ops.append({"op": "del", "text": " ".join(b[i1:i2])})
            ops.append({"op": "add", "text": " ".join(a[j1:j2])})
    return ops


async def _llm_rewrite(clause_text: str, exemplar_texts: list[str]) -> str | None:
    """Ask the model to restructure/clarify ONLY. Banned terms injected. Returns
    None if the LLM is unavailable (→ fallback)."""
    try:
        from app.services.llm import get_llm_client
        llm = get_llm_client()
        banned = ", ".join(load_banned_terms())
        system = (
            "You restructure and clarify a single privacy-notice clause. HARD RULES: "
            "do NOT add any practice, recipient, purpose, or commitment that is not "
            "already stated in the clause. Do not introduce company or product names. "
            f"Never use verdict terms ({banned}). Output ONLY the rewritten clause."
        )
        user = (
            f"Clause to rewrite:\n{clause_text}\n\n"
            + ("Approved peer examples (style/structure only — do NOT copy their facts):\n"
               + "\n".join(f"- {e}" for e in exemplar_texts) + "\n\n" if exemplar_texts else "")
            + "Rewritten clause:"
        )
        resp = await llm._chat(system, user)
        return (resp.content or "").strip() or None
    except Exception as exc:  # noqa: BLE001 — LLM down → safe fallback
        log.info("rewrite LLM unavailable → fallback: %s", exc)
        return None


async def generate_rewrite(assessment_id: str, clause_id: str) -> dict:
    """Generate a guardrailed + verified rewrite, else the exemplar fallback.
    Persists one clause_rewrite row and returns the surface payload."""
    cr = await supabase_rest_get("disclosure_clause", select="raw_text,normalized_text,category",
                                 filters=f"clause_id=eq.{clause_id}", limit=1)
    rows = cr.json() if cr.status_code == 200 else []
    if not rows:
        raise ValueError("clause_not_found")
    clause_text = rows[0].get("raw_text") or rows[0].get("normalized_text") or ""
    domain = rows[0].get("category") or "other"

    er = await supabase_rest_get(
        "disclosure_clause", select="raw_text,normalized_text",
        filters=f"is_exemplar=eq.true&exemplar_status=eq.approved&category=eq.{domain}", limit=2)
    exemplars = [(e.get("normalized_text") or e.get("raw_text") or "")
                 for e in (er.json() if er.status_code == 200 else [])]

    output = await _llm_rewrite(clause_text, exemplars)
    guardrail_passed = False
    verification_passed = False
    if output:
        guardrail_passed = len(check_generated_prose(output)) == 0   # banned terms → fail
        if guardrail_passed:
            verification_passed, _reason = verify_rewrite(clause_text, exemplars, output)

    if output and guardrail_passed and verification_passed:
        suggested, fallback, status = output, False, "llm"
        diff = word_diff(clause_text, output)
    else:
        # Fallback: side-by-side vs the best approved exemplar (or empty diff).
        suggested, fallback, status = None, True, "fallback"
        best = exemplars[0] if exemplars else ""
        diff = word_diff(clause_text, best) if best else []

    rewrite_id = str(uuid4())
    await supabase_rest_post("clause_rewrite", {
        "id": rewrite_id, "assessment_id": assessment_id, "clause_id": clause_id,
        "model_version": MODEL_VERSION, "prompt_version": PROMPT_VERSION,
        "guardrail_passed": guardrail_passed, "verification_passed": verification_passed,
        "suggested_text": suggested, "fallback_used": fallback, "diff": json.dumps(diff),
    })
    return {
        "rewrite_id": rewrite_id, "status": status, "suggested_text": suggested,
        "diff": diff, "watermark_text": WATERMARK,
        "guardrail_passed": guardrail_passed, "verification_passed": verification_passed,
        "fallback_used": fallback,
    }
