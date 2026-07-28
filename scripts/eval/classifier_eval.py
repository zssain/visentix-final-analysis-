"""Classifier evaluation (F17 component 2) — GATED on human gold labels.

Computes accuracy, a 9×9 confusion matrix, per-source split, and VCI-band
calibration (error rate per §8 band — the claim under test: low confidence
concentrates the errors). Also a 3× stability read (labeled stability, NOT
accuracy). If there are zero gold labels, every metric returns "awaiting SME
labels" — nothing is fabricated. Measurement only; changes nothing.
"""

from __future__ import annotations

from collections import defaultdict

from scripts.eval.common import DOMAINS, GOLD_SET_VERSION, VCI_BANDS, band_of, conn

AWAITING = "awaiting SME labels"


def _load_labeled() -> list[dict]:
    """Join gold_label → disclosure_clause. Returns human-labeled clauses only."""
    sql = """
    SELECT g.clause_id::text, g.gold_domain, g.verdict, g.labeler,
           dc.category_v2, dc.nlp_confidence_v2
    FROM gold_label g
    JOIN disclosure_clause dc ON dc.clause_id = g.clause_id
    WHERE g.gold_set_version = %s AND g.gold_domain IS NOT NULL
    """
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, (GOLD_SET_VERSION,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _source_of(clause_ids: list[str]) -> dict[str, str]:
    if not clause_ids:
        return {}
    sql = """
    SELECT dc.clause_id::text,
           CASE WHEN pn.notice_type='open_web' THEN 'fresh_2026'
                WHEN pn.intake_method='upload' THEN 'upload_rehearsal'
                WHEN o.origin='rehearsal' THEN 'upload_rehearsal' ELSE 'legacy' END
    FROM disclosure_clause dc
    JOIN notice_section ns ON dc.section_id=ns.section_id
    JOIN privacy_notice pn ON ns.notice_id=pn.notice_id
    LEFT JOIN organization o ON pn.organization_id=o.organization_id
    WHERE dc.clause_id = ANY(%s)
    """
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, (clause_ids,))
        return {r[0]: r[1] for r in cur.fetchall()}


def evaluate(rows: list[dict] | None = None) -> dict:
    """Pure over `rows` (injectable for tests). Each row needs gold_domain +
    category_v2 (+ nlp_confidence_v2, source). Returns metrics or AWAITING."""
    rows = _load_labeled() if rows is None else rows
    n = len(rows)
    if n == 0:
        return {"status": AWAITING, "labeled": 0}

    correct = sum(1 for r in rows if r["gold_domain"] == r["category_v2"])
    # 9×9 confusion: gold (row) × machine (col)
    confusion = {g: {m: 0 for m in DOMAINS} for g in DOMAINS}
    for r in rows:
        g, m = r["gold_domain"], r["category_v2"]
        if g in confusion and m in confusion[g]:
            confusion[g][m] += 1

    # Per-source accuracy
    per_source: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        s = r.get("source_group", "unknown")
        per_source[s][1] += 1
        if r["gold_domain"] == r["category_v2"]:
            per_source[s][0] += 1
    per_source_acc = {s: {"n": t, "accuracy": round(c / t, 4) if t else None}
                      for s, (c, t) in per_source.items()}

    # VCI-band calibration: error rate per §8 band (claim: low band → more errors)
    per_band: dict[str, list[int]] = {b[0]: [0, 0] for b in VCI_BANDS}
    for r in rows:
        b = band_of(r.get("nlp_confidence_v2"))
        per_band[b][1] += 1
        if r["gold_domain"] != r["category_v2"]:
            per_band[b][0] += 1
    calibration = {b: {"n": t, "error_rate": round(e / t, 4) if t else None}
                   for b, (e, t) in per_band.items()}

    return {
        "status": "ok",
        "labeled": n,
        "accuracy": round(correct / n, 4),
        "confusion": confusion,
        "per_source_accuracy": per_source_acc,
        "vci_calibration_error_rate": calibration,
        "calibration_claim": "low confidence should show higher error_rate (observation only)",
    }


def stability(clause_texts: list[str], classify_fn=None, runs: int = 3) -> dict:
    """3× re-classify a fixed subset → agreement across runs. STABILITY, not accuracy.

    classify_fn(text) -> label. Defaults to the deterministic keyword classifier
    (`decompose.classify_clause_v2`), which is stable by construction (agreement
    1.0) — measuring LLM-path stability requires running the local Qwen3 model 3×
    and is an [ENG] follow-up. Injectable so tests can supply a controlled fn.
    """
    if classify_fn is None:
        from app.services.intake.decompose import classify_clause_v2

        def classify_fn(t):  # deterministic keyword classifier → legacy_slug
            return classify_clause_v2(t)[2]
    per_run = [[classify_fn(t) for t in clause_texts] for _ in range(runs)]
    agree = sum(1 for i in range(len(clause_texts))
                if len({per_run[r][i] for r in range(runs)}) == 1)
    return {"metric": "stability_not_accuracy", "runs": runs, "n": len(clause_texts),
            "full_agreement": agree,
            "agreement_rate": round(agree / len(clause_texts), 4) if clause_texts else None}


if __name__ == "__main__":
    import json
    result = evaluate()
    rows = _load_labeled()
    if rows:
        srcs = _source_of([r["clause_id"] for r in rows])
        for r in rows:
            r["source_group"] = srcs.get(r["clause_id"], "unknown")
        result = evaluate(rows)
    print(json.dumps(result, indent=2, default=str))
