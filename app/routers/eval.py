"""F17 evaluation-harness endpoints (measurement only — writes no score).

Backend for the gold-label round-trip (CSV-first) and the Admin finding-precision
panel. The gold set pre-fills NOTHING: every gold_label row carries the human
`labeler` from the caller's identity; a label can never be written machine-only.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from fastapi.responses import PlainTextResponse

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get, supabase_rest_post

router = APIRouter(prefix="/eval", tags=["eval"])

_GOLD = Path(__file__).resolve().parents[2] / "logs" / "eval" / "gold_set_v1.json"
_DOMAINS = {
    "consumer_rights", "data_sharing", "tracking_cookies", "cross_border",
    "sensitive_data", "retention", "children_teens", "ai_automated_decisions", "other",
}
_VERDICTS = {"correct", "incorrect", "ambiguous"}


def _labeler(user: AuthenticatedUser) -> str:
    who = user.email or user.user_id
    if not who:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No human labeler on the request.")
    return who


def _gold_set() -> dict:
    if not _GOLD.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Gold set not built — run scripts/eval/gold_set.py")
    return json.loads(_GOLD.read_text())


# ── Gold set (machine labels only — NO gold fields pre-filled) ─

@router.get("/gold-set")
async def get_gold_set(user: AuthenticatedUser = require_role("sme", "admin")):
    m = _gold_set()
    return {
        "gold_set_version": m["gold_set_version"],
        "selected": m["selected"],
        "empty_cells": len(m.get("empty_cells", [])),
        "clauses": [{"clause_id": c["clause_id"], "raw_text": c["raw_text"],
                     "machine_category_v2": c["category_v2"],
                     "nlp_confidence_v2": c["nlp_confidence_v2"],
                     "source_group": c["source_group"], "band": c["band"]}
                    for c in m["clauses"]],
    }


@router.get("/gold-set/export.csv", response_class=PlainTextResponse)
async def export_csv(user: AuthenticatedUser = require_role("sme", "admin")):
    m = _gold_set()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["clause_id", "machine_category_v2", "nlp_confidence_v2", "source_group",
                "band", "raw_text", "gold_domain(FILL)", "verdict(FILL)", "note(FILL)"])
    for c in m["clauses"]:
        w.writerow([c["clause_id"], c["category_v2"], c["nlp_confidence_v2"],
                    c["source_group"], c["band"], c["raw_text"], "", "", ""])
    return buf.getvalue()


# ── Write labels — always attributed to a human ──────────────

async def _write_label(clause_id: str, gold_domain: str, verdict: str | None,
                       note: str | None, labeler: str) -> None:
    if gold_domain not in _DOMAINS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"bad gold_domain: {gold_domain}")
    if verdict and verdict not in _VERDICTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"bad verdict: {verdict}")
    r = await supabase_rest_post("gold_label", {
        "clause_id": clause_id, "labeler": labeler, "gold_domain": gold_domain,
        "verdict": verdict, "note": note, "gold_set_version": "v1",
    }, on_conflict="clause_id,labeler,gold_set_version", upsert=True)
    if r.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"gold_label write failed: {r.text[:200]}")


@router.post("/gold-label", status_code=status.HTTP_201_CREATED)
async def post_gold_label(body: dict, user: AuthenticatedUser = require_role("sme", "admin")):
    """Write one human gold label. Labeler is taken from the caller — never blank."""
    await _write_label(body.get("clause_id"), body.get("gold_domain"),
                       body.get("verdict"), body.get("note"), _labeler(user))
    return {"ok": True, "labeler": _labeler(user)}


@router.post("/gold-set/import.csv")
async def import_csv(file: UploadFile = File(...),
                     user: AuthenticatedUser = require_role("sme", "admin")):
    """Import a human-filled CSV → gold_label. Rows with a blank gold_domain are
    skipped (nothing is fabricated). Labeler = the importing human."""
    labeler = _labeler(user)
    text = (await file.read()).decode("utf-8-sig")
    written, skipped = 0, 0
    for row in csv.DictReader(io.StringIO(text)):
        gd = (row.get("gold_domain(FILL)") or row.get("gold_domain") or "").strip()
        cid = (row.get("clause_id") or "").strip()
        if not cid or not gd:
            skipped += 1
            continue
        await _write_label(cid, gd, (row.get("verdict(FILL)") or row.get("verdict") or "").strip() or None,
                           (row.get("note(FILL)") or row.get("note") or "").strip() or None, labeler)
        written += 1
    return {"written": written, "skipped_blank": skipped, "labeler": labeler}


# ── Admin finding-precision (F09 panel) ──────────────────────

@router.get("/finding-precision")
async def finding_precision(user: AuthenticatedUser = require_role("admin")):
    """Confirm/edit/dismiss rate per finding_type from training_label +
    assessment_review. Honest empty state when there's no review data."""
    actions = ("confirmed", "edited", "dismissed")
    tl = await supabase_rest_get("training_label", select="finding_id,action", limit=5000)
    rows = [x for x in (tl.json() if tl.status_code == 200 else []) if x.get("finding_id")]
    fids = list({x["finding_id"] for x in rows})
    ft_map: dict[str, str] = {}
    for i in range(0, len(fids), 100):
        inl = ",".join(f'"{f}"' for f in fids[i:i + 100])
        rf = await supabase_rest_get("risk_finding", select="finding_id,finding_type_code",
                                     filters=f"finding_id=in.({inl})", limit=100)
        for x in (rf.json() if rf.status_code == 200 else []):
            if x.get("finding_type_code"):
                ft_map[x["finding_id"]] = x["finding_type_code"]

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {a: 0 for a in actions})
    for x in rows:
        ft = ft_map.get(x["finding_id"])
        a = {"confirm": "confirmed", "edit": "edited", "dismiss": "dismissed"}.get(
            (x.get("action") or "").lower(), (x.get("action") or "").lower())
        if ft and a in actions:
            counts[ft][a] += 1

    if not counts:
        return {"status": "no SME review actions yet", "total": 0, "by_finding_type": {}}
    by_type = {}
    for ft, c in sorted(counts.items()):
        total = sum(c.values())
        by_type[ft] = {"total": total, **{a: c[a] for a in actions},
                       **{f"{a}_rate": round(c[a] / total, 4) for a in actions}}
    return {"status": "ok", "total": sum(sum(c.values()) for c in counts.values()),
            "by_finding_type": by_type}
