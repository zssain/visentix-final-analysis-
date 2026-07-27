# F01 — Notice Intake & Decomposition Explorer

**Status:** shipped (M-01 + M-02 replaced — real decomposition + real verified-source badge) · **Release:** R1 · **Depends on:** schema.md §2.4, intelligence-logic.md §4, design-system.md

## Purpose
First customer touchpoint after submitting a privacy notice. Ingests via three modes — **URL**, **pasted text**, or an **uploaded document** (PDF / DOCX / TXT, ≤10 MB) — decomposes it into taxonomy-classified clauses, and makes **lineage visible from the first interaction** via a split-pane original-document vs extracted-clauses view. All three modes feed one shared extract→decompose→classify→score pipeline (no parallel path).

## Users & entry points
Customer role · `/intake` → redirects to `/intake/:assessment_id` when processing begins.

## Data
Writes: `assessment`, `privacy_notice`, `notice_section`, `disclosure_clause` (with embeddings + LLM classification). `privacy_notice` records intake provenance: `intake_method` (url/text/upload) and — for uploads only — `upload_filename`, `upload_mime`, `upload_file_hash` (sha256 of the original bytes; `content_hash` remains the hash of the extracted text). Reads: `clause_taxonomy`. (Migration 0033.)

## API contracts
- `POST /api/assessments` — multipart {url | text | file, org metadata} → {assessment_id, intake_method, ssrf_protected}. SSRF validation server-side for URL intake. **Uploads** (`file`) accept PDF / DOCX / TXT: type is validated by **magic bytes** (never the client Content-Type or the filename extension); size ≤10 MB. PDF text via PyMuPDF, DOCX via python-docx, TXT decoded as UTF-8. Encrypted/password-protected PDFs, zero-extractable-text files (e.g. scanned PDFs with no text layer), oversize, and unsupported types are rejected with plain-language errors. OCR of image-only PDFs is a deliberate future item (not in this release).
- `GET /api/assessments/:id` — status (parsing → classifying → ready), clause list with domain, code, preview.

## Behavior & states
- Split pane: left = intake form or rendered doc; right = domain filter pills (8 domains + other), clause chips (navy, `C-118` + domain eyebrow + 80-char preview). Chip click highlights the source span in the left pane.
- Progress stepper `Ingest → Decompose → Classify` (left-stripe timeline style; animated, reduced-motion safe).
- Upload mode: drag-and-drop zone + file picker (accepts .pdf/.docx/.txt), selected-file name + size, same right-pane processing view as URL intake.
- "Verified source" ✓ on successful URL fetch from the real `ssrf_protected` flag — **never name SSRF in UI**. An uploaded document shows a neutral **"Uploaded document"** badge instead and is **never** shown the verified-source badge (that badge means a URL passed validation; showing it for an upload would be dishonest — `ssrf_protected` stays false for uploads).
- Honest counts: the headline clause count is **substantive clauses** (`is_noise=false`); any filtered clauses show as a "n filtered as noise" sub-note, never hidden.
- States: Waiting / Processing / Ready ("View Assessment →") / Error (plain language; on upload-extraction failure, the error also suggests trying paste or URL).

## Decompose-v2 noise filter
Deterministic, explainable filter (`decompose-v2-noisefilter`) that flags nav/heading/metadata/list-fragment sections and their clauses so they cannot inflate downstream counts. Uses ONLY signals available at decomposition — **char length, list/link structure, cross-section duplication, section position** — no LLM, no scoring.
- **Kept, never deleted.** A flagged clause is persisted with `is_noise = true` + a `noise_reason` code (lineage, split-pane original, and the lineage drawer keep it, shown as *filtered, with reason*). It is excluded **only** from: classification tallies, the presence-count profile dimensions (PGMS/DSI/AIGMS), and finding maturity counts. The prior silent drop of sub-20-char fragments is replaced by keep-and-flag (`clause_fragment`) — count behavior unchanged, lineage preserved.
- **Section predicates (first match wins):** `heading_only` (markdown heading, or ≤6-word non-sentence label) → `metadata` (date-stamp / version / copyright front-matter) → `list_fragment` (≤12 words, ends `;`/`:`, no sentence end) → `duplicate_of:<section_id>` (same normalized text seen earlier; the first occurrence is kept). Clauses inherit their section's flag; the code order is exact and re-checkable by a non-author.
- **TIE-BREAK — uncertain → NOT noise.** Missed noise is bounded, but filtering real disclosure text destroys scoring evidence. There is deliberately **no blunt "too-short/`chars < 120`" predicate**: an ambiguous mid-length fragment (e.g. a list continuation) is kept, not filtered.
- **Versioned + non-retroactive.** New assessments record `privacy_notice.decompose_version = 'decompose-v2-noisefilter'`; existing assessments (NULL / different version) are untouched and never silently re-scored (Rule 4).

## Guardrails & confidence
Clause classification stores `nlp_confidence`; low-confidence clauses flagged for SME attention downstream. No scores shown here — decomposition only. **Noise clauses (`is_noise = true`) are kept for lineage but excluded from every count and presence-count dimension.**

## Mocks
| ID | What | Removal |
|---|---|---|
| M-01 | Static clause fixture | Wire to real decomposition output of `POST /api/assessments` |
| M-02 | Badge always shown | Read real `ssrf_protected` flag |
Upload intake (PDF/DOCX/TXT) is fully wired to backend parsing (was previously "PDF UI-only").

## Acceptance criteria
- AC-1 Submitting a real URL produces real `disclosure_clause` rows visible in the right pane within the processing flow.
- AC-2 PDF and raw-text intake produce equivalent decomposition.
- AC-3 Verified-source badge reflects backend flag; absent on failure.
- AC-4 Chip↔span highlight sync works both panes; mobile stacks panes.
- AC-5 Parse failure shows plain-language error, no stack trace.
- AC-6 Uploaded documents (PDF, DOCX, TXT) each produce decomposition equivalent to URL/paste, through the same pipeline.
- AC-7 Type is validated by magic bytes, not extension/Content-Type; oversize (>10 MB), unsupported type, password-protected PDF, and zero-extractable-text files are each rejected with a plain-language error.
- AC-8 An uploaded document shows the "Uploaded document" badge and never the verified-source badge (`ssrf_protected` false).
- AC-9 A customer's assessment — URL, paste, or upload — persists under the caller's own organization only; a client-supplied `organization_id` cannot redirect it into another tenant.
- AC-10 Noise clauses (heading/metadata/list-fragment/duplicate/sub-20-char) are persisted with `is_noise = true` + a `noise_reason` and remain retrievable (never deleted); substantive clauses are `is_noise = false`.
- AC-11 Presence-count dimensions (PGMS/DSI/AIGMS), classification tallies, and finding maturity counts are computed from substantive clauses only — appending noise clauses changes no score, finding, or count.
- AC-12 Tie-break holds: an ambiguous mid-length fragment (>6 words, no trailing `;`/`:`, not a heading/metadata/duplicate) is **not** flagged noise.

## Test gate
Intake pipeline integration tests (URL/PDF/text), SSRF validation tests, classification confidence persistence test, frontend vitest for stepper states. Upload: magic-byte detection + happy-path per type (PDF/DOCX/TXT) + oversize + wrong-type + empty-text PDF + encrypted PDF + tenancy (upload lands under caller's org) — `tests/test_intake_upload.py`. Noise filter: predicate unit checks, noise kept+flagged, scoring/counts exclude noise, tie-break (mid-length fragment kept), duplicate keeps-first, determinism — `tests/test_decompose_noise_filter.py`.

## Changelog
- 2026-07-28 (engineer, expert-approved): **Decompose-v2 noise filter (`decompose-v2-noisefilter`).** Deterministic section-level filter (heading/metadata/list-fragment/duplicate predicates using char length, list structure, cross-section duplication, section position) flags noise clauses `is_noise=true` + `noise_reason` — kept for lineage, excluded from classification tallies, presence-count dimensions (PGMS/DSI/AIGMS), and finding maturity. Approved tie-break "uncertain → not noise": no blunt `chars<120` predicate, so mid-length fragments are kept. Sub-20-char clauses now kept+flagged (`clause_fragment`) instead of silently dropped. Versioned via `privacy_notice.decompose_version`; old assessments untouched (Rule 4). Columns `disclosure_clause.is_noise/noise_reason` + `privacy_notice.decompose_version` (migration 0034). New AC-10/11/12; tests `tests/test_decompose_noise_filter.py`. Labeled rehearsal diagnostic in `REHEARSAL-DIAGNOSIS.md` §2.5 (stored data untouched). Approval: `DECISION-NEEDED.md` Part 1. Source: engineer (Stage-3 rehearsal follow-up).
- 2026-07-28 (engineer): **Upload intake mode added (third mode).** Uploaded documents (PDF/DOCX/TXT, ≤10 MB) now flow through the same extract→decompose→classify→score pipeline as URL/paste, via `POST /assessments/` (multipart `file`) — no new endpoint, no parallel pipeline. Type validated by magic bytes (PDF→PyMuPDF, DOCX→python-docx, TXT→UTF-8); encrypted PDFs, zero-text files, oversize, and unsupported types get plain-language errors (OCR deferred). Provenance persisted via migration 0033 (`privacy_notice.intake_method` + `upload_filename`/`upload_mime`/`upload_file_hash`); UI shows a neutral "Uploaded document" badge, never verified-source (AC-6/7/8). Tenancy hardened: a customer's assessment always lands under their own org (AC-9). Resolves the old "PDF intake UI-only" note. Frontend: `web/src/pages/customer/Intake.tsx`. Source: engineer (task brief said "F02 extension" but F02 states intake is F01 and unchanged — logged as an F01 update).
- 2026-07-27 (engineering closeout): **M-02 Replaced.** `create_assessment` returns a real `ssrf_protected` flag (true only when the source was a URL that passed SSRF validation — a failed check raises earlier); `Intake.tsx` renders a register-safe "✓ Verified source" badge from it (AC-3), never naming SSRF (Rule 9). Absent for file/text intake.
- 2026-07-16 (audit): Status trued up — M-01 verified **Replaced** (Intake posts to real `/assessments/`, renders real decomposition output; no fixture remains); M-02 corrected: the verified-source badge is absent from the UI entirely (not mocked) and still needs building against the real flag.
- 2026-07-16: Added Changelog section for template conformance; no behavioral change. (Mocks M-01/M-02 tracked in [`00-plan/mock-tracker.md`](../00-plan/mock-tracker.md).)
