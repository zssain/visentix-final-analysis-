"""Populate formula_version.description (M-10) — plain-English, guardrail-safe.

Descriptions are sourced strictly from 01-foundation/intelligence-logic.md §7 and
render in the lineage drawer (DDR-005) with NO math notation. Guardrail-safe: they
describe exposure / maturity / likelihood / benchmark position / confidence — never a
compliance verdict. Idempotent (UPDATE by formula_id); re-running changes nothing.

Run: PYTHONPATH=. python scripts/seed_formula_descriptions.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_ar", ROOT / "scripts" / "db" / "apply_and_record.py")
_ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ar)

DESCRIPTIONS = {
    "F-001": "How much we trust the underlying source material behind this result, blending the source's authority, how recently it was gathered, how complete the captured text is, and how confidently it was extracted.",
    "F-002": "An estimate of how much regulatory attention the organization's disclosures could attract, weighing the jurisdictions in scope, how actively each regulator pursues these topics, and how significant each disclosure gap is.",
    "F-003": "How far this organization sits below the strongest performers in its peer group — the distance from the top quartile of comparable peers.",
    "F-004": "How closely the organization's disclosure pattern resembles those seen in past regulator actions, weighted by the priority and activity level of the relevant regulators.",
    "F-005": "How complete and clear the notice is, based on how many expected disclosure elements are present, with reductions for vague or ambiguous wording.",
    "F-006": "How understandable and specific the disclosures are, combining completeness, clarity, specificity, and how well the organization's practices are explained.",
    "F-007": "How thoroughly the notice explains the organization's automated-decision and AI practices, based on the AI-related disclosures present, with a reduction for ambiguous wording.",
    "F-008": "How individual exposure areas reinforce one another — related risks are combined and amplified where they commonly appear together in regulator activity.",
    "F-009": "A derived score adjusted by how confident we are in the inputs behind it, so lower-confidence results are tempered rather than overstated.",
    "F-010": "A single headline measure of privacy maturity, combining the regulatory, benchmark, disclosure, enforcement, AI, and compound signals into one 0–100 figure (higher is stronger).",
    "F-011": "Where this organization ranks within its weighted peer group — the share of comparable peers it scores at or above.",
    "F-012": "How much a measure has moved since the previous assessment, shown as the change from the prior value.",
    "F-013": "How urgently a change warrants attention, combining the size of the risk increase, its resemblance to enforcement activity, the monitoring priority, and our confidence.",
    "F-014": "How much confidence to place in the report overall, based on the share of findings that were validated and the average reliability and classification confidence of the evidence.",
}


def main() -> int:
    import psycopg
    kw = _ar._conn_kwargs()[0]
    with psycopg.connect(**kw) as conn:
        with conn.cursor() as cur:
            updated = 0
            for fid, desc in DESCRIPTIONS.items():
                cur.execute("UPDATE formula_version SET description=%s WHERE formula_id=%s", (desc, fid))
                updated += cur.rowcount
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM formula_version WHERE description IS NULL")
            remaining = cur.fetchone()[0]
    print(f"updated {updated} rows; formula_version rows still NULL description: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
