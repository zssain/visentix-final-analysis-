"""Finding-precision metric (F17 component 6) — measurement only.

Confirm / edit / dismiss rate per finding_type, from real SME review actions in
`training_label` (action + finding_id) and `assessment_review.finding_reviews`.
Honest empty state when there is no review data. Surfaced read-only in the Admin
Console (F09) via app/routers/eval.py. Changes nothing.
"""

from __future__ import annotations

from collections import defaultdict

from scripts.eval.common import conn

ACTIONS = ("confirmed", "edited", "dismissed")


def _load_actions() -> list[dict]:
    """Each row: {finding_type, action}. Union of training_label + assessment_review."""
    out: list[dict] = []
    with conn() as c, c.cursor() as cur:
        # training_label → finding_type via risk_finding
        cur.execute("""
            SELECT rf.finding_type_code, tl.action
            FROM training_label tl
            JOIN risk_finding rf ON rf.finding_id::text = tl.finding_id::text
            WHERE tl.action IS NOT NULL AND rf.finding_type_code IS NOT NULL
        """)
        out += [{"finding_type": r[0], "action": r[1]} for r in cur.fetchall()]

        # assessment_review.finding_reviews jsonb: {finding_id -> {action,...}}
        cur.execute("""
            SELECT rf.finding_type_code, fr.value->>'action' AS action
            FROM assessment_review ar
            CROSS JOIN LATERAL jsonb_each(ar.finding_reviews) AS fr(finding_id, value)
            JOIN risk_finding rf ON rf.finding_id::text = fr.finding_id
            WHERE fr.value->>'action' IS NOT NULL AND rf.finding_type_code IS NOT NULL
        """)
        out += [{"finding_type": r[0], "action": r[1]} for r in cur.fetchall()]
    return out


def compute(rows: list[dict] | None = None) -> dict:
    """Pure over `rows` (injectable). Returns per-finding_type action rates."""
    rows = _load_actions() if rows is None else rows
    if not rows:
        return {"status": "no SME review actions yet", "total": 0, "by_finding_type": {}}

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {a: 0 for a in ACTIONS})
    for r in rows:
        a = (r["action"] or "").lower()
        # normalize a couple of common synonyms honestly
        a = {"confirm": "confirmed", "edit": "edited", "dismiss": "dismissed"}.get(a, a)
        if a in ACTIONS:
            counts[r["finding_type"]][a] += 1

    by_type = {}
    for ft, c in sorted(counts.items()):
        total = sum(c.values())
        by_type[ft] = {
            "total": total,
            **{a: c[a] for a in ACTIONS},
            **{f"{a}_rate": round(c[a] / total, 4) if total else None for a in ACTIONS},
        }
    return {"status": "ok", "total": sum(sum(c.values()) for c in counts.values()),
            "by_finding_type": by_type}


if __name__ == "__main__":
    import json
    print(json.dumps(compute(), indent=2))
