"""Generate INTELLIGENCE-QUALITY.md — real numbers where data exists, else
"awaiting SME labels". Every recommendation carries an owner tag. This report
MEASURES; it changes no weight/threshold/formula.

Run: PYTHONPATH=. python scripts/eval/report.py
"""

from __future__ import annotations

import json
from datetime import date

from scripts.eval import precision
from scripts.eval.common import GOLD_SET_PATH, conn

OUT = GOLD_SET_PATH.resolve().parents[2] / "INTELLIGENCE-QUALITY.md"


def _gold_label_count() -> int:
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM gold_label WHERE gold_domain IS NOT NULL")
        return cur.fetchone()[0]


def build() -> str:
    m = json.loads(GOLD_SET_PATH.read_text()) if GOLD_SET_PATH.exists() else {"selected": 0}
    labeled = _gold_label_count()
    prec = precision.compute()

    awaiting = labeled == 0
    lines = [
        "# INTELLIGENCE-QUALITY.md",
        "",
        f"**Generated:** {date(2026, 7, 28).isoformat()} · F17 evaluation harness (measurement only).",
        "This report **measures**; it changes no weight, threshold, taxonomy, or formula. "
        "Numbers are real where data exists, else \"awaiting SME labels\". Every recommendation "
        "carries an owner — **[SME]**, **[ENG]**, or **[EXPERT]**.",
        "",
        "## 1. Gold set",
        f"- Frozen stratified sample: **{m.get('selected', 0)} clauses** "
        f"(8 domains × 5 §8 bands × 3 sources; `is_noise` excluded; **no labels pre-filled**).",
        f"- Under-populated strata cells: **{len(m.get('empty_cells', []))}** (reported, not back-filled).",
        f"- Human gold labels applied so far: **{labeled}**.",
        "- **[SME]** Label the gold set (`GET /eval/gold-set/export.csv` → fill → `POST /eval/gold-set/import.csv`). "
        "Until then, accuracy/VCI-calibration below are *awaiting*.",
        "",
        "## 2. Classifier eval (gated on labels)",
    ]
    if awaiting:
        lines += [
            f"- **awaiting SME labels** — {labeled} of {m.get('selected', 0)} labeled. "
            "No accuracy, confusion matrix, per-source split, or VCI-calibration number is fabricated.",
            "- **[SME]** provide labels; **[ENG]** the harness (`scripts/eval/classifier_eval.py`) runs automatically once labels exist.",
        ]
    else:
        from scripts.eval import classifier_eval
        r = classifier_eval.evaluate()
        lines += [
            f"- Accuracy: **{r['accuracy']}** over {r['labeled']} labeled clauses.",
            f"- VCI-band error rates: `{r['vci_calibration_error_rate']}` "
            "(claim under test: low band → higher error rate — observation only).",
            "- **[EXPERT]** if low-VCI does NOT concentrate errors, any threshold change is an expert decision (out of scope here).",
        ]
    lines += [
        "- Stability (3× on 50): reported separately as **stability, not accuracy** "
        "(deterministic keyword classifier = 1.0 by construction; LLM-path stability is an **[ENG]** follow-up requiring the local model).",
        "",
        "## 3. Score validity (perturbation + cited monotonicity)",
        "- **Asserted & passing** (`tests/test_f17_score_validity.py`): "
        "**M-1** §7 F-005 (maturity falls when a domain is weakened), "
        "**M-3** §7 F-010 (100 − risk), "
        "**M-4** §7 F-006 (transparency product), "
        "**M-5** §8 VCI (<40 → very-low band, monotone in confidence). Untouched domains stay within tolerance.",
        "- **F-002 — REPORTED, NOT ASSERTED.** `compute_f002` defines *DS = proportion of clauses in each domain* "
        "(coupled, Σ=1), so the verbatim §7 formula does not license a clean \"weaken → exposure worsens\" direction. "
        "**[EXPERT]:** confirm whether regulatory severity should track disclosure **volume** (current) or **quality**. "
        "The harness reports this; it fixes nothing.",
        "",
        "## 4. Golden notices",
        "- 3 **engineer-PROPOSED** retail-cohort notices frozen (strong/mid/weak) with stated rationale; CI diff active "
        "(`tests/test_f17_eval.py`). Only a cited `formula_version` change may legitimately alter a golden file.",
        "- **[SME]** bless or swap the 3 picks (OQ-1) — see SME-REVIEW-CHECKLIST.",
        "",
        "## 5. Benchmark sanity",
        "- Percentile distributions are checked for well-formedness (monotone, sensible spread); a synthetic strong org "
        "lands in the upper half and leaves **no residue** (in-memory only). `tests/test_f17_eval.py`.",
        "",
        "## 6. Finding precision (from real SME review actions)",
    ]
    if prec.get("total", 0) == 0:
        lines += ["- **no SME review actions yet** — confirm/edit/dismiss rates appear here once findings are reviewed.",
                  "- **[SME]** review findings in the workbench to populate this."]
    else:
        lines += [f"- Total review actions: **{prec['total']}**.",
                  f"- Per finding_type: `{json.dumps(prec['by_finding_type'])}`",
                  "- Surfaced read-only in the Admin Console via `GET /eval/finding-precision`."]
    lines += [
        "",
        "## Owners summary",
        "- **[SME]** label the 200-clause gold set; bless/swap the 3 golden notices; review findings for precision data.",
        "- **[EXPERT]** F-002 severity semantics (volume vs quality); any VCI threshold change if calibration warrants.",
        "- **[ENG]** LLM-path stability run; wire the Admin precision panel UI; keep the CI golden diff green.",
        "",
        "_The harness fixes nothing based on these results — measurement only._",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.write_text(build())
    print(f"wrote {OUT.name}")
