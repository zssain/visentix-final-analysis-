# RunPod Pod → RunPod Serverless — Migration Report

**Status legend:** ✅ IMPLEMENTED IN CODE · 🧪 TESTED LOCALLY · 🔧 REQUIRES OPERATOR
ACTION · ⛔ NOT YET VERIFIED IN RUNPOD/AZURE (no fake validation — see §14–15).

## 1. Executive summary
Migrated the hosted qwen3:8b LLM from an **always-on RunPod Pod** (24/7 GPU
billing) to a **request-driven adapter for RunPod Serverless (scale-to-zero)**,
**preserving the model (Ollama + qwen3:8b) and its inference parameters**. Login,
browsing, health checks, and idle now cost **$0 GPU**; only **Analyse Notice** wakes
a worker, which RunPod terminates after a short idle window. Local dev (localhost
Ollama) and Azure-CPU embeddings are unchanged. All code, config, worker, tests,
and docs are done; creating the RunPod endpoint + entering Azure secrets +
retiring the old Pod are **operator actions** (RunPod/Azure credentials required).

## 2. Previous architecture
`Azure backend → Tailscale (100.69.10.127:11434) → always-on Pod 1zyg93j5rzy4p4 →
ollama serve (OLLAMA_KEEP_ALIVE=-1, forever supervisor) → qwen3:8b`. Billed
continuously regardless of use.

## 3. New architecture
`Azure backend → POST https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync (Bearer) →
RunPod Serverless queue → Flex worker (0→1) → ollama serve @127.0.0.1 → qwen3:8b →
COMPLETED → idle timeout → worker→0`.

## 4. Complete file change list
| Path | Change | Why |
|---|---|---|
| `app/config.py` | ✅ Added `LLM_BACKEND`, `runpod_endpoint_id`, `runpod_api_key` (**SecretStr**), `runpod_serverless_base_url/timeout/max_retries`; `effective_llm_backend`, `llm_model_name`, `validate_llm_backend()`. Marked `HOSTED_QWEN_*` legacy. | Provider switch + secret-safe config + no-network validation |
| `app/services/llm.py` | ✅ `_select_backend()`→`effective_llm_backend` (3 modes); renamed `_chat_hosted`→`_chat_hosted_ollama`; added `_chat_runpod_serverless` + `_runpod_await_terminal` + `_runpod_parse`; added `RunPodServerlessError`; `__init__` validates config. | The serverless adapter under the existing single retry policy |
| `app/routers/health.py` | ✅ `/health` no longer probes hosted/serverless model (only local dev); reports `llm.probe=not_invoked_to_avoid_cold_start`; liveness is DB-driven. | Health must never wake a scale-to-zero worker |
| `app/main.py` | ✅ Lifespan calls `settings.validate_llm_backend()` (no network) + logs provider. | Fail fast on misconfig at boot |
| `deploy/runpod/serverless/handler.py` | ✅ New RunPod worker: start Ollama once per cold start (no supervisor), ensure model, `handler(job)`→local `/api/chat`. Import-safe. | The Serverless worker |
| `deploy/runpod/serverless/Dockerfile` | ✅ New. `ollama/ollama` (pinned ARG) + python + runpod SDK; `OLLAMA_MODELS=/runpod-volume/...`; **no** `KEEP_ALIVE=-1`. | Worker image |
| `deploy/runpod/serverless/requirements.txt` `.dockerignore` `README.md` `tests/test_handler.py` `tests/sample_job.json` | ✅ New. | Deps, secret-free build, docs, local tests |
| `deploy/runpod/README.md` | ✅ Rewritten — Serverless-first runbook (click-by-click, curl, Azure, cold start, scale-to-zero, billing, troubleshooting, rollback, retirement); legacy Pod kept as rollback. | Operator runbook |
| `deploy/runpod/pod-entrypoint.sh` | ✅ Legacy banner added (rollback only). | Don't reuse the always-on pattern |
| `.env.example` | ✅ Added `LLM_BACKEND` + `RUNPOD_*`; deprecated `HOSTED_QWEN_*`; pilot `SCHEDULER_ENABLED=false` note. | Config surface |
| `tests/test_llm_runpod_serverless.py` `tests/test_health_no_gpu.py` | ✅🧪 New backend tests. | Adapter matrix + cost regressions |

**Not touched (by design):** `app/services/embeddings.py` (stays Azure CPU),
scoring/risk/report/auth business logic, the frontend.

## 5. Backend request flow
See `deploy/runpod/README.md §3`. `Analyse → /assessments/async → classify_clauses
→ get_llm_client().classify() → LLMClient._chat() → _chat_runpod_serverless() →
runsync (+ /status poll on cold start) → parse envelope → output.message.content →
narrative → report`. Browser polls `/assessments/{id}/status` only (never RunPod).

## 6. RunPod worker design
Cold start: `ollama serve`@127.0.0.1 started **once**, wait for `/api/version`,
ensure `qwen3:8b` (pull once onto the network volume). `handler(job)` validates
`input`, POSTs `/api/chat` (stream/think false, num_predict 500), returns
`{"model","message":{role,content},"done",...}`, **raises** on failure (job→FAILED).
**No forever-loop**, **no `KEEP_ALIVE=-1`** → RunPod scales the worker to zero.

## 7. Environment variables — see `deploy/runpod/README.md §9` (table).

## 8. Exact RunPod console setup — see `deploy/runpod/README.md §7` (20 numbered steps).
Pilot settings: **Active=0, Max=1, GPUs/worker=1, Idle=30s, Exec=300s, Queue type.**

## 9. Exact Azure changes
Set in the VM backend `.env`: `LLM_BACKEND=runpod_serverless`, `RUNPOD_ENDPOINT_ID`,
`RUNPOD_API_KEY` (secret), `HOSTED_QWEN_MODEL=qwen3:8b`, `SCHEDULER_ENABLED=false`.
Redeploy (`deploy/azure/deploy.sh <tag>`). Frontend + CORS unchanged.

## 10. Health-check changes (proof it can't wake GPU)
`/health` computes `effective_llm_backend`; for `runpod_serverless`/`hosted_ollama`
it makes **zero** model calls and reports `probe:"not_invoked_to_avoid_cold_start"`.
🧪 `tests/test_health_no_gpu.py::test_health_serverless_does_not_wake_worker` asserts
no request URL contains `runsync`/`/run`/`api.runpod.ai`/`/api/version`/`/api/chat`/`:11434`.

## 11. Scheduler changes (proof pilot is safe)
`scheduler.start()` hard-returns when `SCHEDULER_ENABLED=false` (no jobs
registered). 🧪 `tests/test_health_no_gpu.py::test_scheduler_disabled_registers_no_jobs`.
Pilot `.env` sets it false so the daily `monitor_notices` cron can't send inference.

## 12. Tests added (all local, no GPU/network)
- 🧪 `tests/test_llm_runpod_serverless.py` (9): success + payload shape; 401 no-retry;
  429 retried→ok; 5xx bounded-retry→degrade; timeout retried; job FAILED terminal;
  COMPLETED-missing-output; IN_PROGRESS→/status poll→COMPLETED; API-key never logged.
- 🧪 `tests/test_health_no_gpu.py` (2): health doesn't wake a worker; scheduler-disabled.
- 🧪 `deploy/runpod/serverless/tests/test_handler.py` (5): chat success; reject
  missing messages / unknown op; empty content raises; ollama error raises.

## 13. Local test results
`pytest tests/test_llm_runpod_serverless.py tests/test_health_no_gpu.py` → **11 passed**.
`pytest deploy/runpod/serverless/tests` → **5 passed**. Adjacent regression
(app_boot, llm_retry_taxonomy, intake, render_cors) → **83 passed** total. Existing
LLM retry test still green (renamed dispatch). The only repo failures are the
pre-existing 0047 live-DB env class (TEST-RECONCILIATION.md), unrelated.

## 14. RunPod test results
⛔ **Not performed** — requires a RunPod account/API key + a built+pushed image +
a created endpoint (operator credentials I don't have). Run the `README §11` curl
after §6–7; expect `status:COMPLETED`, `output.message.content:"SERVERLESS_OK"`.

## 15. Scale-to-zero verification
⛔ **Not verified here.** Run `README §60`-style Tests A–G (idle/login/browse/health
→ 0 workers; Analyse → 1 → back to 0). Migration is complete only when the RunPod
Workers panel returns to **0 active** after the idle timeout.

## 16. Cost behavior before vs after
Before: always-on Pod → billed 24/7 (~$0.79/hr ≈ ~$570/mo) irrespective of use.
After: Flex worker billed only while it exists (startup + model load + inference +
idle window), then $0; a small network-volume storage charge persists. **Not**
"tokens only" or "exactly 65 s/doc." Use RunPod `delayTime`/`executionTime` for real
numbers (logged by the backend). Architecturally: idle GPU cost → **$0**.

## 17. Cold-start behavior
First Analyse after idle waits for worker start + model load (seconds→~1 min);
handled by the background pipeline + 5-min status polling; UX shows "Classifying…".
Not "fixed" by min-workers>0. Measure real cold-start via RunPod `delayTime`.

## 18. Security review
`RUNPOD_API_KEY` is `SecretStr` (never in repr/logs), read only in
`_chat_runpod_serverless` via `get_secret_value()` for the Bearer header — backend
only. 🧪 test asserts the key never appears in logs/errors. Never in the frontend,
image, git, or `/health`. `.dockerignore` excludes `.env`/secrets from the image.

## 19. Remaining risks
- runsync cold start can exceed its wait window → handled by `/status` polling, but
  validate real cold-start time vs `RUNPOD_SERVERLESS_TIMEOUT_SECONDS` (default 180).
- Pinned `OLLAMA_VERSION=0.5.11` in the Dockerfile is a **placeholder** — verify the
  tag exists and serves qwen3:8b before building.
- GPU tier must fit qwen3:8b (measure VRAM; §10).
- Output parity vs the Pod is expected but must be spot-checked (§55 of the prompt).
- `app/routers/admin.py` still pings `ollama_base_url/api/tags` for /admin/status
  (localhost, harmless — will show `ollama_ok:false` in prod; cosmetic follow-up).

## 20. Operator actions still required (checklist)
- [ ] 🔧 Build + push the worker image (linux/amd64), pin a real `OLLAMA_VERSION`.
- [ ] 🔧 Create the RunPod Serverless **Queue** endpoint (Active=0, Max=1, Idle=30s, Exec=300s).
- [ ] 🔧 Attach a network volume for `qwen3:8b` (or bake into image).
- [ ] 🔧 Direct curl test (README §11) → `SERVERLESS_OK`.
- [ ] 🔧 Create a RunPod API key; put `RUNPOD_ENDPOINT_ID` + `RUNPOD_API_KEY` in Azure secrets.
- [ ] 🔧 Set `LLM_BACKEND=runpod_serverless`, `SCHEDULER_ENABLED=false`; redeploy backend.
- [ ] 🔧 E2E: login→browse→health = 0 workers; Analyse → worker → complete → back to 0.
- [ ] 🔧 Verify output parity + record cold-start/exec times.
- [ ] 🔧 Only then: STOP old Pod, verify, then DELETE Pod + its volume.

## 21. Rollback procedure
No code change needed. Azure `.env`: `LLM_BACKEND=hosted_ollama` +
`HOSTED_QWEN_BASE_URL=http://100.69.10.127:11434`; ensure the Pod is running;
redeploy. Inference returns to the Pod (`_chat_hosted_ollama` retained). (README §19.)

## 22. Old Pod retirement
After Serverless is validated + scale-to-zero confirmed: **STOP** Pod
`1zyg93j5rzy4p4`, confirm Visentix still works, keep stopped for a rollback window,
then **DELETE** the Pod **and** its `/workspace` volume (a stopped Pod's volume
still bills storage). Not automated — explicit operator action (README §20).
