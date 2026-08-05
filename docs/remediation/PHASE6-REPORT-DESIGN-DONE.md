# PHASE 6 — Report Design: Match the Executive Prototype (DONE)

**Date:** 2026-08-05
**Scope:** Render-layer only. Turn the plain-HTML PDF into the executive-ready
artefact from the prototype **without fabricating a single value.**
**Prereq honoured:** Runs after Phase 3A — the report already carries real
industry/jurisdiction context, so this is styling over real scores, not lipstick
on `industry:"unknown"`.

The single seam changed is `render_html()`. `assembly.py`'s numbers, the scoring
engine, and snapshot determinism were **not** touched except for two READ-ONLY
exposures of already-computed values (documented below).

---

## What shipped

| File | Change |
|---|---|
| `app/services/report/report.css` | **New (319 lines).** Design system: tokens, `@page` furniture (running header/footer, named strings, cover/back pages), type scale, and reusable components (`.kpi-card`, `.gauge`, `.bar-compare`, `.heat-grid`, `.callout--{insight,alert,risk}`, `.finding-row`, `.numbered-driver`). |
| `app/services/report/renderer.py` | **Rewritten (+904/−136).** Cover, page chrome, all 12 sections, back cover, inline-SVG gauges, comparison/percentile bars, regulator heat grid, callouts, honest-absence helpers, placeholder-strip. SEC-006 validation + `render_pdf*` backends preserved. |
| `app/services/report/assets/wordmark-dark.png`, `wordmark-light.png` | **New (committed).** Copied from `web/public/`. Dark (reversed/white) wordmark is base64-inlined into the cover + back panels for byte-identical determinism (Rule 4). |
| `app/services/report/assembly.py` | **+13 lines, READ-ONLY.** Surfaces `percentile`/`regulatory_exposure`/`regulatory_tier`/`overall_band` into §2 and `top_quartile_score`/`peer_n` (from F-003 lineage) into §4. **No math.** |
| `tests/test_report_design.py` | **New (247 lines).** Part E suite (determinism, honest-absence, guardrail, branding, placeholder-leak, visual). |
| `tests/test_f20_partner.py` | Updated the header-only-branding test for the new cover routing (property preserved, now verified by full-document diff). |
| `docs/remediation/assets/phase6-sample-report.pdf` | **New.** Rendered Brex-like payload for human review (13 pages, 251 KB). |

---

## Assets (Part A)

The **Visentix logo was supplied** (`web/public/`) and is used as instructed —
the reversed wordmark on the navy cover panel and the teal/navy back cover.

| Asset | Status |
|---|---|
| Logo — full colour / reversed | ✅ **Used** (`wordmark-dark.png` on dark panels, committed under `assets/`). |
| Brand colour tokens | ✅ Navy `#12365B`, teal `#2FB3A0` (per Platform Documentation). |
| Risk ramp | ✅ low `#2E9E6B` · moderate `#E9A23B` · high `#D9534F` · elevated `#C0392B`. One ramp, used everywhere. |
| Brand fonts (`.ttf`/`.otf`) | ⛔ **BLOCKED — EXTERNAL.** Not supplied. Using the documented **DejaVu Sans** fallback (bundled with WeasyPrint). When the files arrive, drop them in `assets/` and add an `@font-face` in `report.css`. |
| Icon set | Fallback used — simple single-colour inline-SVG glyphs (`_glyph`) drawn in code (diamond/arrow/alert/check). |
| Back-cover contact block | ⛔ **BLOCKED — EXTERNAL.** No verified published contact exists (the org's real domain is `teclusion.ai`, not the invented `visentix.ai`). Rather than fabricate an email/URL, the back cover shows only "Visentix · Privacy Intelligence Platform" + the confidentiality line. Owner to supply the real contact block. |
| "CONFIDENTIAL" wording | ✅ Prompt's default wording used on the cover badge + back cover. |

---

## Section-by-section (real code section order)

The prototype's section list differs from the code's; the design was mapped onto
the **actual** `assembly.py` order (Recommendations = §9, Risk Reduction = §10,
Traceability = §11, Trend = §12).

1. **Cover** — navy angular panel, reversed wordmark, org, title, Prepared-For / Report-Date / Assessment-Type, CONFIDENTIAL badge. All data present.
2. **Executive Summary** — 3 KPI cards (Overall `/100` + band, Percentile with ordinal suffix, Regulatory Exposure level in risk colour) + icon takeaways. Guardrail wiring untouched (enforced upstream).
3. **Risk Dashboard** — 3 inline-SVG gauge dials + 4-card metric strip + risk-ramp dimension bars. Handles both extremes (AI 15.7 → crimson, Disclosure 98.5 → green) without clipping.
4. **Benchmark Intelligence** — percentile marker bar + **real** Your-score vs Peer-top-quartile (F-003 `top_quartile_score`, n weighted peers). Per-dimension peer averages **do not exist** → explicit "Insufficient peer data" state, never a guessed average.
5. **Regulator Exposure** — regulator cards (real names/jurisdictions) + domain×regulator **heat grid** + numbered drivers. **Honest coverage:** only cells with clause evidence are coloured; no-evidence cells are hatched and the "N of M cells backed by evidence" coverage is labelled.
6. **Disclosure Findings** — rich finding rows (id · domain · severity chip · confidence · exposure). `notice_section`/page refs are **not** in the snapshot → column omitted with a stated caveat, never a plausible-looking page number.
7. **Compound Risk** — alert callout (level + score) + numbered drivers from F-008 lineage + impact callout.
8. **Benchmark Language Comparison** — two-column Your-language vs Top-quartile exemplar. **Privacy control:** the peer column only shows SME-approved exemplars; where none exists it shows the honest-absence line, never an unapproved clause.
9. **Strategic Recommendations** — icon + title + body rows. **Placeholder leak fixed:** any un-substituted `{ai_use_cases}`/`{sensitive_data_types}` token is stripped (with its governing preposition) so it reads cleanly and no literal brace ships.
10. **Risk Reduction by Severity** — High/Moderate/Low columns of numbered actions; a level with no findings shows honest absence.
11. **Source Traceability** — formula-version table + **real guardrail receipt** (GRD-001/002 PASSED/not_recorded chip) + snapshot line + page-ref caveat.
12. **Trend & Emerging Risk** — **the section that must NOT be built as designed.** No trend line. A designed empty state ("Trend begins after your next monitored capture") + the real static regulatory-landscape content.
- **Back cover** — teal/navy angular panel, wordmark, "Thank you for your trust", confidentiality line.

---

## Hard constraints (Part D) — verification

1. **Byte-identical determinism survives.** No `datetime.now()`/random/remote fetch in the render path (the old `from datetime import datetime` import was removed). CSS + wordmark read from disk at import and base64-inlined. Same frozen payload → identical sha256 twice; no `/CreationDate`/`/ModDate`/`/ID`. `test_pdf_determinism.py` + `test_report_reproducible.py` pass. Explicit re-render check: `83cc2d2fabcf == 83cc2d2fabcf`.
2. **Guardrail stays in path.** Enforcement lives in `reports._assemble_from_live` (upstream of the renderer); restyle cannot route around it. `test_guardrail_still_fails_closed_after_restyle` proves a banned term still raises `GuardrailError`.
3. **Partner branding still works (F20).** Band is header-only; body bytes are identical branded vs unbranded apart from the injected `<div class="brand-band">`. SEC-006 `brand_color`/`logo_url` validation preserved (`test_branding_rejects_css_injection_color`, `test_sec006_branding.py`).
4. **No fabricated values.** `_num()` treats missing/None as absent → "Not recorded" / "Insufficient data" / "Not yet measured", never a `0` or fake bar. A **real bug** was caught and fixed: a missing F-002 (defaulted to `0.0` by assembly) was rendering as "Low / exposure score 0.0" — the KPI now keys off tier-presence (F-002 always emits a tier when computed) and shows honest absence.
5. **WeasyPrint-compatible CSS only.** Table-based card strips + real `<table>` heat grid (no CSS grid), inline SVG for gauges/glyphs, no JS. Verified with the actual WeasyPrint 69 renderer, not a browser.

---

## READ-ONLY assembly exposures (justified)

The prompt explicitly permits surfacing already-computed F-003 values
("read-only addition, no math change"). Two spots:

- **§4** — `top_quartile_score` + `peer_n` from `scores["f003"]["lineage"]` (weighted top-quartile threshold; `None` when F-003 had no peers → honest absence).
- **§2** — `percentile` / `regulatory_exposure` / `regulatory_tier` / `overall_band`, all already computed above in `assemble_report`, exposed so the exec KPI cards read real values.

No score is computed or altered; the content hash legitimately includes these as
real content. `test_data002_content_hash.py` + `test_report_reproducible.py` pass.

---

## Gate results (real counts)

- **Determinism + report tests (explicitly named):**
  `test_pdf_determinism.py`, `test_report_reproducible.py`, `test_report_design.py` — **all pass.**
- **Report-adjacent suite** (every module importing renderer/assembly/heatmap):
  **137 passed, 2 skipped.**
- **Full backend `pytest -q`:** **1038 passed, 36 failed, 15 skipped.** The 36
  failures are pre-existing, environment-only (live-DB/seeded-corpus/secrets):
  `test_review_gate.py`, `test_training_labels.py`, `test_schema_p1.py` — all
  `RuntimeError: assessment…`-class, none in report/render/assembly/pdf/design.
  (Baseline before this work: identical set fails locally without the seeded DB.)
- **Frontend:** `npx tsc --noEmit` → **0 errors**; `npm run build` → **✓ built.**
  (No web files were touched; run for completeness.)

## Visual artefact

`docs/remediation/assets/phase6-sample-report.pdf` — the Brex-like payload
(overall 70.9, 88.1th percentile, n=93, VCI 71.4, AI 15.7, Disclosure 98.5, a
deliberately-leaky `{ai_use_cases}` recommendation) rendered to 13 pages for
human review. Every panel verified page-by-page: cover, KPI cards, gauges, the
Your-vs-top-quartile bars, the evidenced heat grid, findings, compound, the
privacy-controlled language comparison, the guardrail receipt, and the trend
**empty state** (no fabricated line).

---

## Not done (out of scope / external)

- **Brand fonts** — BLOCKED-EXTERNAL; DejaVu fallback in use.
- **Back-cover contact block** — BLOCKED-EXTERNAL; no verified published contact.
- **Notice-section / page references (§6, §11)** — not carried in the snapshot;
  columns omitted with a stated caveat rather than estimated. Wiring the
  clause→section reference through is a future read-only addition.
