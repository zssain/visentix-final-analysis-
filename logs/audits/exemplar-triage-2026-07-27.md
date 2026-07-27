# Exemplar Triage — 2026-07-27 (Stage-3 Workstream B)

**By:** implementing engineer (`ai_reviewed`; no SME impersonation). **Trigger:** the engineering-closeout data-quality flag — several of the 16 `is_exemplar` clauses looked non-English or domain-mismatched. **Method:** programmatic audit of all 16 for (a) language (English function-word heuristic), (b) domain match via the platform's own `classify_clause_v2`, (c) de-identification via `validate_deidentification`, plus a manual read of every survivor.

> Rows are **never deleted** — deactivation sets `is_exemplar=false, exemplar_status='deidentified'` (they passed de-id; they are simply not approvable as exemplars). Reversible, auditable via `scripts/triage_exemplars.py` (idempotent).

## Outcome

| | Count |
|---|---:|
| Started `is_exemplar=true` | 16 |
| **Deactivated — objective failures** | **7** |
| — non-English (nl/es/de) | 6 |
| — de-identification leak (org name) | 1 |
| **Kept `is_exemplar=true` (approved)** | **9** |

**Live after triage:** 9 exemplars — AI 1 · CR 2 · RT 2 · TRK 1 · DC 2 · XB 1. Every domain that had an exemplar still has ≥1; **no domain lost its last exemplar**, so no corpus replacement was required (task condition not triggered).

## Deactivated (7) — `ai_reviewed`, reversible

| clause_id | domain | class | reason |
|---|---|---|---|
| `06ca5336` | AI | lang | Dutch ("wij beschermen onze eigen financiële positie…") |
| `03cc0895` | — | lang | Spanish ("si creemos de buena fe que la divulgación…") |
| `068b166c` | XB | lang | Spanish ("nuestros clientes pueden utilizar…") |
| `2fdae095` | — | lang | German ("ungefährer standort: wir bestimmen…") |
| `a6460051` | DC | lang | German ("daten über anlagekonten…") |
| `81ad2b15` | DC | lang | Spanish ("detectar y prevenir fraudes…") |
| `f95bbc0b` | RT | **deid** | Leaks org name **"Aetna"** ("you and aetna waive the right to a jury trial") — the token blocklist missed it. Also a mis-domained arbitration clause. |

## Kept (9) — but flagged for SME domain-fit review (NOT auto-pulled)

Whether an English clause *exemplifies* its assigned domain is SME content judgment, so these stay approved pending SME. The keyword classifier agrees with each assigned domain (it made the assignment), so it cannot self-validate. My read:

| clause_id | domain | fit | note for SME |
|---|---|---|---|
| `5c2ef146` | CR | ✅ good | "right to request a restriction on further data processing" |
| `a48885fa` | CR | ✅ good | "right to object to the processing of personal data" |
| `4308b014` | TRK | ✅ good | analytics/tracking purposes list (terse) |
| `b266a77e` | DC | ⚠️ ok/boilerplate | WordPress-default "comments … visitor's IP address and browser user agent" |
| `8f2d6f5a` | DC | ⚠️ marginal | children-under-18 clause — more children/teens than data-collection |
| `e8c4cc3b` | AI | ❌ mismatch | accessibility/format notice ("audio, large print, braille") — **not** automated-decisions |
| `1bee4446` | XB | ❌ mismatch | financial-info **collection** — not cross-border transfer |
| `f48f5e3a` | RT | ❌ mismatch | Argentina regulator-contact/jurisdiction clause — not retention |
| `19957a08` | RT | ❌ low quality | cookie-consent-table fragment ("maximum storage duration: 400 days") |

**Recommendation to SME:** repick or deactivate the ❌ rows; RT in particular is left with two weak survivors (`f48f5e3a`, `19957a08`) — consider sourcing a genuine data-retention exemplar. AI/XB currently surface a mismatched clause in the report (draft only; not client-delivered — the pilot stops at the review gate).

## Missing domains — honest absence + optional candidates

SH (data-sharing) and SEC (security) never had an exemplar → the report renders honest absence for them (M-03). Vetted, English, de-id-passing **candidate** clauses the SME could clean + approve (not staged in the DB — approval is SME-only):

- **SH:** `6ef2219a` ("identity verification and validation services. we disclose information as necessary…"), `131be3cc` ("disclose necessary information in response to … a civil or criminal legal process"), `343004ac` ("third party service partners and providers…").
- **SEC:** `7304264e` ("no security measure … is 100% secure. although we strive to use commercially acceptable means…"), `8e0d1794` ("policies and procedures regarding the protection, retention and disposition of personal information…").

## Systemic finding for hardening

`validate_deidentification` blocks emails, URLs, and a **known-org token list** — but org names outside that list (e.g. "Aetna", "Brex") pass through. Before any exemplar is client-delivered, the SME de-id step must catch names the blocklist doesn't. Consider broadening the de-id check (NER or a larger org lexicon) — logged as a hardening item, not fixed here.
