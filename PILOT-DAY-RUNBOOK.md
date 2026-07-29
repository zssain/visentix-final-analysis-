# PILOT-DAY RUNBOOK — Visentix v1

_Click-by-click for the owner on pilot day. The stack was proven clean in the
2026-07-29 prod rehearsal (see LAUNCH-READINESS-v2.md), so this executes on a
known-good platform, not a first flight._

**Live URLs**
- App: `https://visentix-v2-mvp.zssaincoding.workers.dev` (masked v1)
- API: `https://visentix-api.westeurope.cloudapp.azure.com`
- Admin login: `admin@visentix.com` · SME login: `sme@visentix.com`

---

## 0. Pre-flight (5 min) — do NOT start intake until all green

```bash
API=https://visentix-api.westeurope.cloudapp.azure.com
curl -s $API/health | jq '{status,db,model_status}'          # → healthy / ok / ok
```
Confirm in the admin console (log in as admin → Admin):
- [ ] `gate_mode = strict` (STRICT human gate — NEVER instant_draft)
- [ ] all 3 jobs **disabled** (monitor_notices, pull_regulators, refresh_benchmarks)
- [ ] `db_ok` and `ollama_ok` both true
- [ ] frontend shows ONLY: Monitor, Intake, Codex, Methodology (+ Admin for you). No Bulk/Partner/Rewrite/Vendors/Trust/Crosswalk.

If `model_status`/`ollama_ok` is down → the pod dropped; reconnect (see LAUNCH-READINESS "Pod durability") before proceeding. The site still serves; classification is what pauses.

## 1. Intake (the pilot notice)
1. **Intake** → choose the mode the design partner gave you:
   - **Paste text** — paste the notice body.
   - **Upload** — attach the PDF/txt (badge will read "upload", never "verified source").
   - **URL** — paste the privacy-policy URL (discovery + SSRF-checked).
2. Set **Organization name** to the pilot client's name.
3. Submit → wait for **status: scored** (~10–15 s; all clauses should classify via the LLM, keyword_fallback = 0).
4. Note the **assessment_id**.

## 2. SME session (gate STRICT — nothing is client-visible yet)
Log in as **sme@visentix.com** → **Workbench**.
1. Work `SME-REVIEW-CHECKLIST.md` **in order** (if that file isn't in the repo yet, use the review panel's per-domain checklist), then the pilot queue item.
2. For each finding: confirm / edit / dismiss with a note. The LLM only phrases — verify no invented claims, numbers, or verdict language (exposure/likelihood only).
3. Leave it **in_review** until you and the SME agree it's right.

## 3. The finale (owner only — this is the human gate)
When the SME session is done and you're satisfied:
1. **Approve** the snapshot → 2. **Freeze** it → 3. confirm the **teal ribbon** (frozen/approved marker).
4. **Byte-identity check** before delivery:
   ```bash
   AID=<assessment_id>; TOK=<admin bearer>
   curl -s "$API/reports/$AID/pdf" -H "Authorization: Bearer $TOK" -o a.pdf
   curl -s "$API/reports/$AID/pdf" -H "Authorization: Bearer $TOK" -o b.pdf
   shasum -a256 a.pdf b.pdf
   ```
   ⚠️ **KNOWN FINDING (rehearsal):** the PDF is NOT yet byte-identical — WeasyPrint stamps a fresh `/CreationDate` + `/ID` per render. The *content* (snapshot `content_hash`) is stable; the *file bytes* are not. **Decide before delivery:** either accept content-hash identity as the guarantee, or hold delivery until the renderer pins PDF metadata (small fix). Do not claim byte-identity until this is closed.
5. **Deliver** the approved PDF to the pilot client.

## 4. Abort criteria (stop, don't deliver)
- `model_status` down mid-session and won't reconnect → pause; classification unreliable.
- Any finding shows invented data or verdict language → dismiss, do not approve.
- gate_mode is not `strict` → STOP (never deliver an instant_draft to a client).
- PDF byte-identity matters to this client AND the renderer isn't pinned yet → hold.
- Cross-org data appears where it shouldn't → STOP (tenant isolation was verified in rehearsal; any leak is a hard stop).

## 5. Success — the celebration line
On a clean approve → freeze → deliver, append to `logs/decision-log.md`:
```
- 2026-__-__ · owner · **Success Metric #1 — first pilot report delivered.**
  <client> assessment <assessment_id> approved, frozen, delivered. First real
  customer-facing Visentix intelligence report. 🎉
```
