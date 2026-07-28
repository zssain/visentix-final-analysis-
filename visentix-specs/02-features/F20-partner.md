# F20 — Partner Portal (Deliverable 3: white-label channel, real backend)

**Status:** approved — in-progress (owner-approved 2026-07-28 with the refinements in changelog 0.2)
**Release:** R3
**Owner:** eng (tenancy + feed + branding) + SME (gate language, permitted-use copy sign-off)
**Depends on:** F10 + `app/auth.py` (role/claim mechanism — extend, don't fork), F11 (the mocked portal this makes real — replaces M-19–M-22), F01 intake (`create_assessment` three modes + upload validation), F06 review gate + SME workbench (single path), F05 report renderer (branding injection point), `routers/feed.py` + `services/products/mapping.py` (white-label feed), OD-05 (`LOW_CONFIDENCE_COHORT_N = 10`), DIR-005/DIR-006 (segregation + minimum-sample suppression), schema.md

## Purpose
Let consulting / law / audit / insurance **partners** deliver Visentix intelligence under their own brand: a partner logs in, creates a **client workspace** (wrapping exactly one client org), runs the **same** intake → scoring → gated review → report pipeline our direct customers use, and downloads a **partner-branded** PDF whose numbers are byte-for-byte our numbers. Plus a hardened, **API-key-authenticated, per-cohort-aggregated** white-label data feed. The whole feature is **additive tenancy + branding on top of the existing single pipeline** — no forked review, no forked scorer, no number ever altered by branding.

## Users & entry points
`partner_admin` (new role) · `/partner` (replaces the F11 mock). Our `admin` sees everything (support/oversight). Our SMEs review partner-submitted assessments in the **same workbench queue** (workspace label visible). Existing `customer` / `sme` tenancy is **untouched** (regression suite must stay green).

## Tenancy model (the core — every rule has a mandatory test)
```
partner ──< partner_workspace >── client organization (exactly one per workspace)
   │                                     │
   └─ partner_admin users (role +        └─ privacy_notice / derived_data_item /
      partner_id claim)                     report_snapshot … (normal customer-scoped rows)
```
- **Claim carriage — mirror `organization_id`, don't invent a new mechanism.** `app/auth.py` already carries `organization_id` two ways: local-auth JWTs embed it directly (`app_role` + `organization_id` claims → no profile lookup); Supabase-auth JWTs load it from `profiles`. F20 adds a **`partner_id`** claim/column the **same two ways**, and adds `partner_id` to `AuthenticatedUser` (a new `__slots__` field, default `None`). Role `'partner_admin'` is added to the `user_role` enum (same as F19 added `'analyst'`).
- **Isolation rules (each → a test):**
  1. `partner_admin` sees **only** workspaces where `partner_workspace.partner_id == user.partner_id`.
  2. A client org inside a workspace is **invisible** to other partners **and** to unrelated `customer` users (they never gain access to a partner-owned client org).
  3. Our `admin` sees all (oversight).
  4. **Existing customer tenancy is unchanged** — a `customer` still sees only its own org; partner rows never widen or narrow that.
- **Scope resolution:** a partner endpoint resolves the target org **through the workspace** (`workspace.partner_id == caller.partner_id` → `workspace.client_org_id`). A caller can never name a `client_org_id` that isn't inside one of their own workspaces (403). This is the partner analogue of F10's "a customer's assessment always lands under their own org."

## Data (new — amends schema.md; migration 0039)
```
partner(id uuid pk, name text, logo_url text null, brand_color text null,
  status text CHECK IN ('active','suspended') default 'active', created_at timestamptz)
partner_workspace(id uuid pk, partner_id fk→partner, client_org_id fk→organization,
  name text, created_at)            -- the bridge: one workspace wraps one client org
partner_api_key(id uuid pk, partner_id fk→partner, key_hash text, label text,
  created_at, last_used_at null, revoked_at null)   -- HASH ONLY, never plaintext
feed_access_log(id uuid pk, partner_id fk, api_key_id fk→partner_api_key,
  endpoint text, at timestamptz, row_count int)
```
- **Role:** `ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'partner_admin'`. `profiles`/local-auth carry `partner_id` (mirror of `organization_id`).
- **Branding provenance on the snapshot:** `report_snapshot.branding_applied jsonb null = {partner_id, logo_hash, brand_color}` — **recorded at first branded render and frozen** (Hard Rule 6 byte-identity; see Branding).
- **Segregation (DIR-005):** feed aggregates are computed over `derived_data_item` but the feed **never emits customer-scoped identifiers** (see Feed).

## API contracts
All partner endpoints require `partner_admin` (our `admin` also allowed for oversight); tenant-scoped through the workspace. Every score payload keeps `vci` + `formula_version` + lineage (inherited, unchanged).

- **`POST /partner/workspaces`** `{name, client_org:{name, industry}}` → creates a `partner_workspace` **and** its one client `organization` (via the normal `_find_or_create_org`/profiling path). `industry` must be a canonical taxonomy id (validated server-side). → `201 {workspace_id, client_org_id}`.
- **`GET /partner/workspaces`** → list for `caller.partner_id` only, each with **latest assessment status** per client (`draft` / `in_review` / `approved`) + last activity.
- **`POST /partner/workspaces/{id}/assessments`** — the **same three intake modes** (URL / paste / upload) by **reusing the extended `/assessments/` path** with workspace context; the org is resolved from the workspace (never client-supplied). **Gate mode applies IDENTICALLY** — the assessment is created draft and enqueued to the **same SME workbench** (`get_or_create_review`); **no partner bypass exists** (tested).
- **`GET /partner/reports/{snapshot_id}.pdf`** — branded render: partner **logo + name substituted in the report header at render only**; on first render, `report_snapshot.branding_applied = {partner_id, logo_hash, brand_color}` is written; re-render reads that frozen record → **byte-identical per snapshot**. The report **body (every number and wording) is unchanged** from our own render.
- **Feed hardening — `GET /feed/white-label`:**
  - **Auth via partner API key header** (`X-Partner-Key`); server hashes and compares against `partner_api_key.key_hash` (not revoked); `require_role('admin')` remains valid for internal callers. On match, `last_used_at` is stamped and the call is written to `feed_access_log` (partner_id, api_key_id, endpoint, row_count).
  - **Per-cohort aggregation (identity removal).** The feed is reshaped from per-org rows to genuine **aggregates by `(segment=industry, object_type)`**: each record carries **`population_n`** (distinct orgs in the cohort) + aggregate score stats + VCI band — and **never** `organization_id` or any member identity (MUST NOT; the current per-org `organization_id` field is removed).
  - **Population eligibility — same exclusions as the benchmark/quarterly population (live, not baked at insert).** The aggregate population is built at query time and includes only orgs that (a) are **CQS-eligible** — have a fresh `open_web` `privacy_notice` (the exact gate `benchmark/population.py` applies, "F03 parity, Rule 6") — and (b) are **not** `organization.origin = 'rehearsal'`. Because the exclusion is applied on every request, soft-removing an org or marking it `rehearsal` **immediately** drops it from the aggregate and re-counts `population_n` (tested).
  - **Minimum-sample suppression — records with `population_n < 10` are EXCLUDED server-side.** Threshold **n = 10** per **OD-05** (`LOW_CONFIDENCE_COHORT_N`, Decided 2026-07-27) and **DIR-006** (no aggregate exposed below the minimum cohort). Suppression happens **after** the eligibility exclusions and before serialization — suppressed cohorts never leave the process.
  - **Response versioning.** The feed response carries a `schema_version` (bumped to `vicbnf-3.0.0` for this per-cohort reshape) so partners can detect future shape changes; per-record `population_n` + `segment` make the grain explicit.
- **`POST /partner/api-keys`** `{label}` → generates a key, stores **only its hash**, returns the **plaintext once** (never retrievable again). **`GET /partner/api-keys`** → lists **masked** (label + last4 + created/last_used/revoked). **`DELETE /partner/api-keys/{id}`** → sets `revoked_at` (immediate — the next feed call with that key is rejected).
- **`GET /partner/industries`** → the canonical `industry_taxonomy` (from `config/org_profile_weights.json`) for the New-Client dropdown (frontend fetches, never hardcodes).
- **Branding settings:** `PUT /partner/branding` `{logo (upload), brand_color}` — logo reuses F01 **upload validation** (magic-byte image check, **2 MB cap**); stored as `partner.logo_url` + a `logo_hash`. Changing branding **does not** alter any already-rendered snapshot (its `branding_applied` is frozen).

## Review gate — single path (MUST NOT fork)
Partner assessments are ordinary assessments with a workspace label. They flow through the **exact** `score_and_persist` → `get_or_create_review` (SME DRAFT) path and the **same** gate mode (`instant_draft` / `expert_review`). A `partner_admin` **cannot**: flip gate mode, approve/reject findings, or reach any `/review/*` write endpoint → **403 on every one** (tested). Partners see the **same gate language** as customers ("pending Visentix expert review") — no special casing.

## Branding — render-only, number-safe, byte-identical
Branding injects a **header band** (partner logo + name + brand color) into the report HTML at render; it touches **no section content**. Determinism (Hard Rule 6): the branded PDF is a pure function of `(snapshot.rendered_report, branding_applied)`.
- **Freeze point = snapshot APPROVAL (when everything else freezes), not first render.** When our SME approves a partner-workspace assessment (`approve_assessment` → `approve_and_freeze`), the system resolves the partner via `workspace.partner_id` and writes `report_snapshot.branding_applied = {partner_id, logo_hash, brand_color}` in that same freeze. So the report carries the branding that existed **when the expert approved it** — not whatever the partner happens to have rebranded to by download time.
- **Fallback for pre-existing approved snapshots** (approved before F20 exists → `branding_applied` is NULL): branding is captured at **first branded render** and the record notes `frozen_at: 'first_render'` (vs `'approval'`) so the provenance of the freeze is honest.
- A later logo change never mutates an existing snapshot's PDF. AC: the branded snapshot payload equals our own snapshot payload byte-for-byte in the body (only the header band differs).

## Guardrails & confidence
- **No raw clause text and no cohort-member identities** in any feed (identity-removal reshape above; DIR-005/006).
- **API keys hashed at rest**, plaintext shown once; revocation is immediate.
- **Branding cannot change any number or wording** in the report body (render-only header band).
- **Minimum-sample suppression** cited to OD-05 (n=10) + DIR-006; enforced server-side before exposure.
- Guardrail vocabulary applies to partner-branded narratives **identically** (same banned-term filter).

## Mocks
Replaces **M-19** (partner + workspaces), **M-20** (API keys/usage), **M-21** (feed catalog + suppression), **M-22** (branding + templates) — mark all four **Replaced** in `mock-tracker.md` on merge.

## Acceptance criteria
- **AC-1** Cross-partner isolation: partner A cannot see partner B's workspace, client org, report, or feed access (404/403, no existence leak).
- **AC-2** A `customer` user cannot see any partner-owned client org; existing customer-only visibility is unchanged (regression).
- **AC-3** `partner_admin` cannot flip gate mode or approve/reject — **403 on every `/review/*` write** and on gate-mode.
- **AC-4** Partner assessment is created **draft** and enqueued to the **same** SME workbench (single path; no bypass).
- **AC-5** Feed excludes every cohort with `population_n < 10` (provably), emits `population_n` + `segment` + `schema_version`, and contains **no `organization_id`** / raw clause text.
- **AC-5b** Feed eligibility is **live**: after an org is soft-removed / marked `origin='rehearsal'` (or loses CQS eligibility), the aggregates **recompute** with that org excluded and `population_n` reduced on the next call (not baked at insert).
- **AC-6** Feed requires a valid, non-revoked partner API key; a **revoked key is rejected immediately**; each served call writes a `feed_access_log` row.
- **AC-7** API key returned in plaintext exactly once; storage holds only the hash; `GET` lists masked.
- **AC-8** Branded PDF is **byte-identical per snapshot** across re-renders; the report **body payload equals our own** (same numbers/wording) — branding differs only in the header band.
- **AC-9** New-Client industry dropdown is served from the canonical taxonomy endpoint (not hardcoded).

## Test gate
`tests/test_f20_partner.py` — cross-partner isolation on workspace/report/feed (AC-1); customer regression (AC-2); partner→`/review/*` + gate-mode all 403 (AC-3); partner assessment lands draft in the shared queue, no bypass (AC-4); feed suppresses n<10 + emits population_n/segment/schema_version + zero org identifiers (AC-5); **feed aggregates recompute after an org is soft-removed / marked `rehearsal` — live exclusion, not baked at insert (AC-5b)**; API-key hash-compare + immediate revocation + access-log write (AC-6); plaintext-once + masked list (AC-7); branded PDF byte-identity + body-payload equality vs unbranded + freeze-at-approval (AC-8); industries endpoint served from config (AC-9). **The existing customer-tenant + review-gate suites must stay green (regression).** Frontend vitest: role-guard on `/partner`, workspace cards + status chips, New-Client modal (fetched industries), reused intake components, gate language parity, API-key create/copy-once/revoke, branding preview.

## Future work (additive, no reshape)
- **Finer feed grain — `industry × size` per cell.** v1 aggregates by `industry` only. A later revision may emit an `industry × size` cell **wherever that finer cell independently clears `population_n ≥ 10`**, falling back to the industry-level cell otherwise. This is purely additive (more/finer rows behind the same n≥10 floor + `schema_version` bump) — no reshape of the v1 records.

## Open questions
- **OQ-1 [SME]** Sign-off on partner-facing gate language (must match the customer wording exactly) + the feed permitted-use / contract copy.
- **OQ-2 [ENG] — RESOLVED 2026-07-28 (owner).** Feed grain = **`industry` only** for v1 (`population_n = distinct CQS-eligible, non-rehearsal org count`). `industry × size` is deferred to Future work (per-cell, n≥10-gated, additive).
- **OQ-3 [OD]** OD-05's `n=10` is `ai_reviewed`, not yet human-Teams-approved for client delivery. Feed suppression uses it as the enforced floor; a stricter human-set floor would only *remove* more rows (safe). Flag if the human floor should gate first external partner delivery.

## Changelog
- 0.2 (2026-07-28): Owner-approved for build with refinements — (1) feed reshape confirmed (drop `organization_id`, per-cohort aggregates), **plus** the same population exclusions as the benchmark/quarterly population (`origin != 'rehearsal'`, CQS-eligible), applied **live** per request (AC-5b), and a `schema_version` bump (`vicbnf-3.0.0`) for change detection; (2) grain = `industry`-only for v1, `industry × size` moved to Future work (per-cell n≥10, additive); (3) branding freeze moved from **first render** to **snapshot approval** (fallback: pre-existing approved snapshots freeze at first render, recorded as `frozen_at:'first_render'`). Source: owner.
- 0.1 (2026-07-28): Initial spec (DRAFT). Partner portal real backend on the existing single pipeline — `partner`/`partner_workspace`/`partner_api_key`/`feed_access_log` (migration 0039), `partner_admin` role + `partner_id` claim (mirrors `organization_id`), workspace/assessment/branded-PDF/api-key endpoints, feed hardening (API-key auth + per-cohort aggregation removing `organization_id` + n<10 suppression per OD-05/DIR-006 + access log), render-only frozen branding (byte-identity). Single review path (no partner bypass). Replaces F11 M-19–M-22. Not implemented — awaiting owner approval. Source: engineer (F20).
