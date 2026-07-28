# F18 — Clause Rewrite (Illustrative, Guardrailed)

**Status:** shipped (2026-07-28 — owner-approved build; migration 0041 live)
**Release:** R2
**Owner:** eng (engine) + SME (exemplar approval, register sign-off)
**Depends on:** F05 (BenchmarkLanguage diff, snapshot), F06 (exemplar approval), narrative.py (rephrase + verify + fallback pattern), guardrail.py, intelligence-logic.md §10 (LLM task boundaries), schema.md

## Purpose
Offer a customer an **illustrative** rewrite of a weak clause — clearer structure, peer-informed phrasing — **without ever adding a practice, recipient, purpose, or commitment the clause didn't already make.** It is a drafting *aid*, explicitly **not legal drafting**. Every output passes **both** the banned-term guardrail **and** a fabrication-verification step; any failure falls back to a side-by-side comparison against an approved exemplar. This is the honest, safe realization of intelligence-logic §10 (LLM may rephrase; may not invent facts or render conclusions).

## Users & entry points
`sme,admin` · `/rewrite` (replaces the current mock page). Clause picker (left) → diff/rewrite (right). **v1 gating:** F18 is the **v4 flagship** — for v1 it is gated away from the customer role (route + backend endpoint `sme,admin` only); it releases with v4 entitlements, not silently in the pilot (owner, 2026-07-28; see [`00-plan/version-ladder.md`](../00-plan/version-ladder.md)).

## Data (new — amends schema.md)
`clause_rewrite(id uuid pk, assessment_id fk→privacy_notice(notice_id), clause_id fk→disclosure_clause, model_version text, prompt_version text, guardrail_passed bool, verification_passed bool, suggested_text text null (null when fallback used), fallback_used bool, diff jsonb, created_at)`.
Reads: `disclosure_clause` (raw_text, domain), `disclosure_clause` approved exemplars (`is_exemplar=true, exemplar_status='approved'`).

## API contracts
- `POST /assessments/{id}/clauses/{cid}/rewrite` → `200 {rewrite_id, status:'llm'|'fallback', suggested_text|null, diff, watermark_text}`. **Org-scoped** (403 cross-org). **Gate-mode respecting:** a rewrite may be generated as a draft, but the **report only embeds rewrites present at snapshot freeze** (never regenerated at render — byte-identity holds).
- Reuses the F05 BenchmarkLanguage **diff machinery** for the `diff` payload (gold added / warm-gray struck) — F18 **does not alter BenchmarkLanguage behavior** (MUST NOT).

## Generation logic (`services/rewrite.py`)
**Input** = clause `raw_text` + `domain` + up to **2 SME-approved** exemplar texts for that domain.
1. **Prompt (step 1)** — versioned (`prompt_version`, stored per row): instruct the model to **restructure / clarify ONLY**. Explicitly **forbidden** to add practices, recipients, purposes, or commitments absent from the input clause; **forbidden verdict terms** (the banned-terms list is injected into the prompt). Model + prompt versions recorded on every row.
2. **Guardrail (step 2)** — `guardrail.enforce(output)`; any banned term → reject.
3. **Verification (step 3)** — extract candidate **factual additions** = named entities + purpose phrases present in the output but **absent from (clause ∪ exemplars)**; **any hit → reject.** (Extends `narrative.verify_rephrased` / `extract_entities`; source = clause ∪ exemplars, adds purpose-phrase detection.)
4. **Fallback (step 4)** — on **any** rejection (guardrail OR verification): `fallback_used=true`, `suggested_text=null`, and `diff` = clause vs **best approved exemplar** (reuse BenchmarkLanguage diff machinery). The customer still gets a useful, safe comparison.

**Watermark constant (always shown, incl. on PDF wherever a rewrite appears):**
> "Illustrative language based on peer patterns — not legal drafting. Review with counsel."

**A rewrite is NEVER surfaced unless BOTH guardrail AND verification pass** (MUST NOT).

## Behavior & states
- **Left pane:** clause picker — the selected assessment's clauses grouped by domain, **findings-flagged clauses first**.
- **Right pane:** diff view (gold added / warm-gray struck — the same classes as BenchmarkLanguage), **watermark banner always visible**, "Regenerate" + "Copy" buttons.
- **Fallback state:** renders the side-by-side comparison with a plain explanation line (why no generated text — the safety fallback fired).
- Loading / error / empty per existing customer-page conventions.

## Guardrails & confidence
Both guardrail and verification are hard gates. The watermark is non-dismissible. Exemplars are **approved-only**. No rewrite is embedded in a frozen report unless it existed at freeze (Hard Rule 6 byte-identity preserved). LLM records model + prompt version + review status (intelligence-logic §10).

## Mocks
none — replaces the existing `/rewrite` mock with the real engine.

## Acceptance criteria
- **AC-1** A rewrite passing guardrail + verification returns `status:'llm'` with `suggested_text` + diff + watermark.
- **AC-2** **Fabrication is rejected:** an output introducing an entity/purpose absent from clause∪exemplars (e.g. "we share with advertising partners" when the clause never said so) → verification fails → fallback.
- **AC-3** A banned/verdict term in the output → guardrail fails → fallback.
- **AC-4** Fallback renders the side-by-side (clause vs best approved exemplar) + plain explanation; `suggested_text=null`.
- **AC-5** Every row records `model_version` + `prompt_version` + `guardrail_passed` + `verification_passed` + `fallback_used`.
- **AC-6** Cross-org rewrite → 403; report byte-identity holds (rewrites only embedded if present at freeze; nothing regenerates at render).
- **AC-7** Watermark appears in interactive **and** PDF wherever a rewrite/fallback shows.

## Test gate
`tests/test_f18_rewrite.py` — llm happy path; **fabrication-injection test** (mock LLM adds an unsourced recipient → verification rejects → fallback); guardrail-rejection → fallback; watermark present; `clause_rewrite` fields recorded; cross-org 403; snapshot byte-identity with an embedded rewrite. Frontend vitest for the diff/fallback/watermark states. **BenchmarkLanguage behavior unchanged (regression).**

## Open questions
- **OQ-1 [SME]** Register sign-off on the rewrite prompt + watermark copy.
- **OQ-2 [ENG]** `prompt_version` home — narrative.py does not currently version prompts formally; F18 introduces an explicit `PROMPT_VERSION` constant (proposed home for a future shared prompt library).

## Changelog
- 0.2 (2026-07-28): **Shipped.** `services/rewrite.py` (LLM restructure → banned-term guardrail → fabrication verification [numbers via `narrative.verify_rephrased` + named-entity/purpose-phrase additions absent from clause∪exemplars] → exemplar fallback), `POST /assessments/{id}/clauses/{cid}/rewrite` + `GET …/clauses` picker, real `/rewrite` page (replaces M-26) with token diff + non-dismissible watermark + honest fallback, `clause_rewrite` table (migration 0041, live). `tests/test_f18_rewrite.py` (10). Verification/fallback/guardrail all hard gates. Source: engineer.
- 0.1 (2026-07-28): Initial spec (DRAFT). Illustrative clause rewrite behind guardrail + fabrication-verification, exemplar-fallback, watermark; `clause_rewrite` table + `POST …/rewrite`; reuses narrative verify/fallback + BenchmarkLanguage diff (unchanged). Not implemented — awaiting owner approval. Source: engineer (F18).
