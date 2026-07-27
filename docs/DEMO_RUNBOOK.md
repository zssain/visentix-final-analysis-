# Demo Runbook — Visentix MVP

> **Reviewed 2026-07-27 (Stage-3).** Reflects the current build: gate mode now
> **defaults to STRICT** (expert_review — customers see nothing until an SME
> approves), the Dashboard carries the **continuous-monitoring hero** (trend /
> feed / alerts), cohort `n` is **live-queried** (retail 25 · healthcare 31 ·
> fintech 23 — never a static number), and post-MVP surfaces are hidden unless
> `VITE_PREVIEW_SURFACES=true`. A full end-to-end re-run **against production**
> is pending deploy (see `LAUNCH-READINESS.md`).

## Prerequisites

1. Backend running: `source .venv/bin/activate && uvicorn app.main:app --reload`
2. Frontend running: `cd web && npm run dev`
3. Ollama running: `brew services start ollama`
4. `.env` configured with Supabase credentials
5. Users provisioned: `python scripts/setup_local_auth.py` (writes `local_users.json`,
   which is gitignored and NOT baked into the Docker image — RLS-AUDIT §4).

### Gate mode (important)

The gate defaults to **STRICT**: a customer sees nothing until an SME approves
(the safe pilot default). To demo the instant-draft (gold-watermark) flow, set it
explicitly first:

```bash
curl -X POST http://localhost:8000/review/gate-mode \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"mode": "instant_draft"}'
```

Leave it STRICT for the real pilot — the report stays a DRAFT until the human gate.

### Pre-intake checklist for a PILOT org (do this BEFORE intake)

Live scoring builds a **dynamic** benchmark population from profiled orgs — it does
**not** read the `retail-2026Q3-v2` demo cohort (those `benchmark_cluster` /
`benchmark_membership` rows power the cohort UI + M-12, not the live benchmark). So
the population quality depends entirely on the org's classification at intake. The
Stage-3 rehearsal org came through with `industry='unknown'`, so its population was
similarity-only (no retail industry match) — avoid that:

1. **Set the pilot org's industry first.** Create the `organization` row with the
   correct `industry` (e.g. `retail`) — and `industry_id` via the SME-approved
   `sic_industry_map` — **before** submitting the notice. Then intake with
   `organization_id=<that org>` (not a bare URL that derives an `unknown` org).
   Without this, `build_population`'s industry-expansion can't find retail peers.
2. **Profiling is automatic** at intake (`_ensure_org_profile`) — no manual step —
   but sanity-check the resulting `organization_intelligence_profile` (esp. `pgms`:
   the rehearsal org landed at `pgms=100`/`Leading`, which drove percentile 100 —
   see `REHEARSAL-DIAGNOSIS.md` §1b; flag any maxed PGMS to the SME).
3. **Confirm the population is CQS-gated + retail-matched:** the benchmark now
   excludes CQS-ineligible (stale-corpus) orgs and discloses the hold-out on the
   cohort label (`cqs_gated_excluded_N`). Expect a retail-heavy population if step 1
   was done.

## Demo Script

### 1. Health Check (30 seconds)

```bash
curl http://localhost:8000/health | python -m json.tool
```

**Expected**: 22 tables with row counts, `ollama: "ok"`.

### 2. Submit a Notice (2 minutes)

**Sample notice** (paste into POST /assessments):

```
Privacy Notice — Demo Corp

We collect your name, email, and browsing data. We use cookies for
analytics and advertising. We share data with third-party providers.
You have the right to access, delete, and opt out. We retain data for
3 years. Data may be transferred internationally. Not for children
under 13. We use AI for personalization. We collect health data with
consent.
```

```bash
curl -X POST http://localhost:8000/assessments/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "text=Privacy Notice — Demo Corp..." \
  -F "organization_name=Demo Corp"
```

**Expected**: `assessment_id`, `sections: ~9`, `clauses: ~9`, `content_hash`.

### 3. View Scores (1 minute)

The pipeline runs decompose → classify → score (F-002 through F-014) → VCI → findings.

**Expected output**:
- Overall Intelligence: 50–70 range
- Regulatory Exposure: moderate tier
- 5–7 findings from catalog
- VCI: moderate or high

### 4. View Report (1 minute)

```bash
curl http://localhost:8000/reports/$ASSESSMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: 12-section JSON payload with scores, findings, recommendations, and a
**live** cohort label (e.g. "n=25 peers as of <date>" for retail) — the number is
queried from `benchmark_membership`, never hardcoded. (If gate mode is STRICT and
the report isn't approved yet, a customer token gets 403 "pending expert review" —
use an SME/admin token, or approve first via §6.)

### 5. Download PDF (30 seconds)

```bash
curl http://localhost:8000/reports/$ASSESSMENT_ID/pdf \
  -H "Authorization: Bearer $TOKEN" -o report.pdf
```

**Expected**: Valid PDF with all 12 sections matching the JSON payload.

### 6. SME Review Flow (2 minutes)

```bash
# View queue
curl http://localhost:8000/review/queue -H "Authorization: Bearer $SME_TOKEN"

# Confirm a finding
curl -X POST http://localhost:8000/review/finding/$ASSESS_ID/f1 \
  -H "Authorization: Bearer $SME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm"}'

# Dismiss a finding
curl -X POST http://localhost:8000/review/finding/$ASSESS_ID/f2 \
  -H "Authorization: Bearer $SME_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "dismiss"}'

# Approve
curl -X POST http://localhost:8000/review/$ASSESS_ID/approve \
  -H "Authorization: Bearer $SME_TOKEN"
```

**Expected**: Status transitions draft → in_review → approved. Dismissed finding
absent from approved report.

### 7. Training Stats (30 seconds)

```bash
curl http://localhost:8000/admin/training-stats \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected**: `total_labels: 2`, `by_action: {confirm: 1, dismiss: 1}`.

### 8. Guardrail Demo (30 seconds)

Show that banned terms are caught:
```python
from app.services.guardrail import enforce
enforce("This is a violation of privacy law.")  # → GuardrailError
```

### 9. Continuous Monitoring (1 minute)

On the customer Dashboard, the monitoring hero shows the **trend sparkline**
(F-012, improvement-colored per DDR-009), the **change feed**, and the **alert
center** (F-013 + resolved enforcement only) — all org-scoped, live:

```bash
curl "http://localhost:8000/api/monitoring/trend"  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/api/monitoring/events" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/api/monitoring/alerts" -H "Authorization: Bearer $TOKEN"
```

A single-assessment org returns `baseline_established` (never a fake trend).

## Key Talking Points

- **Privacy intelligence, not legal compliance** — exposure/likelihood language only
- **Honest numbers** — **live** cohort size (queried, not hardcoded), real date, VCI on every score
- **Reproducible** — reports regenerate identically from snapshots
- **Formula-driven** — no LLM computes scores; LLM only rephrases
- **Continuous monitoring** — trend / change feed / alerts, org-scoped, F-012/F-013
- **Three roles + tenant isolation** — a customer sees only its own org's data (enforced server-side)
- **Safe by default** — gate mode STRICT until an SME approves; guardrails hard-fail banned terms
