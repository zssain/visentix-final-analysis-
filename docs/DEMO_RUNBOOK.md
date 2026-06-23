# Demo Runbook — Visentix MVP

## Prerequisites

1. Backend running: `source .venv/bin/activate && uvicorn app.main:app --reload`
2. Frontend running: `cd web && npm run dev`
3. Ollama running: `brew services start ollama`
4. `.env` configured with Supabase credentials

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

**Expected**: 12-section JSON payload with scores, findings, recommendations, cohort
label "n=30 peers as of 2026-06-23".

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

## Key Talking Points

- **Privacy intelligence, not legal compliance** — exposure/likelihood language only
- **Honest numbers** — real cohort size (n=30), real date, VCI on every score
- **Reproducible** — reports regenerate identically from snapshots
- **Formula-driven** — no LLM computes scores; LLM only rephrases
- **Three roles** — customer sees own data, SME reviews, admin controls
- **Guardrailed** — banned terms hard-fail, fabricated numbers blocked
