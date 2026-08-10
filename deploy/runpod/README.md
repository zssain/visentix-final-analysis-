# RunPod — Visentix LLM compute (qwen3:8b)

**Current recommended architecture: RunPod Serverless (scale-to-zero).**
The legacy always-on Pod is retained only for rollback (bottom of this doc).

Embeddings are **not** here — they run on the Azure CPU
(`app/services/embeddings.py`, sentence-transformers). RunPod serves the
**qwen3:8b LLM only** (classification + narrative phrasing).

---

## 1. Architecture

```
Browser ── HTTPS ──▶ Azure backend (FastAPI)
                        │  POST https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync
                        │  Authorization: Bearer <RUNPOD_API_KEY>   (backend only)
                        ▼
                 RunPod Serverless Queue Endpoint
                        │  job arrives → a Flex worker spins up (0 → 1)
                        ▼
                 Worker container (deploy/runpod/serverless/)
                        │  ollama serve @127.0.0.1  →  qwen3:8b
                        ▼
                 inference → output → job COMPLETED
                        │
                        │  no more jobs + idle timeout expires
                        ▼
                 worker terminated  →  workers = 0  →  $0 GPU
```

## 2. Why Serverless

The legacy Pod ran 24/7 and billed 24/7 regardless of use. Serverless bills only
while a worker is processing (plus a short idle window). Login, browsing, health
checks and idle time cost **$0 GPU**. Only clicking **Analyse Notice** spins a worker.

## 3. Request flow (backend)

```
"Analyse Notice"  → POST /assessments/async  (Intake.tsx → lib/api.ts)
  → assessment pipeline (app/routers/assessments.py)
    → classify_clauses → get_llm_client().classify()      (app/services/intake/persist.py)
      → LLMClient._chat() → _chat_runpod_serverless()      (app/services/llm.py)
        → POST {base}/{ENDPOINT_ID}/runsync  (Bearer)      ← wakes a worker
        → (if still IN_PROGRESS) poll GET /status/{id}
        → parse RunPod envelope → output.message.content
    → narrative (llm.phrase) → report → status=complete
  browser polls GET /assessments/{id}/status  (status only — never RunPod)
```

## 4. Files

```
deploy/runpod/
├── README.md              ← this runbook (Serverless first)
├── pod-entrypoint.sh      ← LEGACY always-on Pod supervisor (rollback only)
├── docker-compose.yml     ← legacy self-host reference
└── serverless/
    ├── Dockerfile         ← worker image (Ollama + python + runpod SDK)
    ├── handler.py         ← RunPod handler → local Ollama /api/chat
    ├── requirements.txt   ← runpod, httpx (pinned)
    ├── .dockerignore
    ├── README.md
    └── tests/
        ├── test_handler.py   ← local unit tests (no GPU/SDK needed)
        └── sample_job.json
```

## 5. Worker design (`serverless/handler.py`)

- On **worker cold start** (`__main__`): start `ollama serve` bound to `127.0.0.1`
  **once**, wait for readiness, ensure `qwen3:8b` is present. **No forever-loop /
  supervisor** — RunPod owns the worker lifecycle so it can scale to zero.
  `OLLAMA_KEEP_ALIVE=-1` is deliberately **NOT** set.
- `handler(job)` validates `job["input"]`, POSTs to the local Ollama `/api/chat`
  with the **same** params as every other backend (`stream:false`, `think:false`,
  `options.num_predict:500`), and returns an Ollama-shaped output. It **raises**
  on any failure so RunPod marks the job **FAILED** (the backend then records an
  honest DEGRADED result — it never silently succeeds).
- Within one warm worker, Ollama's default keep-alive holds the model in VRAM
  across an assessment's sequential calls; after the idle timeout RunPod
  terminates the worker.

## 6. Build the worker image (linux/amd64)

RunPod GPU nodes are `linux/amd64`. On Apple Silicon/macOS you **must** cross-build:

```bash
# from the repo root
docker buildx build --platform linux/amd64 \
  --build-arg OLLAMA_VERSION=0.5.11 \
  -t <registry>/visentix-runpod-serverless:2026-08-10-<git-sha> \
  deploy/runpod/serverless --push
```

- Pin `OLLAMA_VERSION` to a tested tag (verify it exists + serves qwen3:8b).
- Use an **immutable tag** (`<date>-<sha>`), not `:latest`, for the endpoint.
- Registry = your GHCR/Docker Hub. Do **not** invent credentials; use your own.

## 7. Create the RunPod Serverless endpoint — click by click

> Written for someone who has never used RunPod Serverless.

1. Log into **https://runpod.io**.
2. Left sidebar → **Serverless**.
3. Click **New Endpoint**.
4. **Endpoint type:** choose **Queue** (queue-based). Visentix does background
   document processing; it does not need a always-hot low-latency HTTP server.
5. **Worker source / image:** select **Custom / Docker image** and enter the image
   you pushed in step 6, e.g. `ghcr.io/<org>/visentix-runpod-serverless:2026-08-10-<sha>`.
6. **GPU:** pick **one** cost-efficient GPU with enough VRAM for qwen3:8b (see
   §10). Start with a ~16–24 GB tier (e.g. RTX 4000 Ada 20 GB / A4000 / L4). Do
   **not** default to A100/H100.
7. **GPUs per worker:** `1`.
8. **Active (min) workers:** `0`   ← **NON-NEGOTIABLE.** `1` here = 24/7 billing again.
9. **Max workers:** `1` (pilot). Predictable billing + simple debugging. Raise to
   `2` only after cost is validated (see §17 Bulk).
10. **Idle timeout:** `30` seconds. (Long enough to keep the worker warm across an
    assessment's sequential LLM calls; short enough to drain to zero quickly. Tune
    to 5–15 s later if calls are tightly grouped.)
11. **Execution timeout:** `300` seconds (bounds a runaway job).
12. **FlashBoot / startup optimization:** enable if offered (faster cold starts),
    unless it causes model issues — document what you chose.
13. **Environment variables** (worker): usually none required — the image sets
    `OLLAMA_MODELS`, `OLLAMA_HOST`, `OLLAMA_MODEL`. If you attach a network volume
    (§8), confirm `OLLAMA_MODELS` points at its mount (default `/runpod-volume/ollama`).
    **Do NOT put `RUNPOD_API_KEY` here** — that key is for the *Azure* side.
14. **Network volume (model storage):** see §8. Attach it before deploying.
15. Click **Deploy**. Wait until the endpoint status is **Ready/Idle** with **0**
    workers.
16. Copy the **Endpoint ID** (top of the endpoint page) — you'll give it to Azure.

## 8. Model storage — do NOT re-download 5 GB per job

Pod storage and Serverless storage are **separate** — the old `/workspace` volume
does **not** carry over. Choose one:

- **Preferred — RunPod Network Volume:** create a Serverless **Network Volume**
  (~20 GB), attach it to the endpoint. The image sets `OLLAMA_MODELS=/runpod-volume/ollama`.
  First worker `ollama pull qwen3:8b` writes the weights there **once**; every
  later worker start finds them already present (fast cold start). Weights persist
  after workers scale to zero.
- **Alternative — bake into the image:** add `RUN ollama pull qwen3:8b` to the
  Dockerfile. Larger image (~6 GB) but zero pull at runtime. Heavier to rebuild.

**What is stored / where / persistence / size:** qwen3:8b weights (~5.2 GB) at
`OLLAMA_MODELS`; on a network volume they persist across worker shutdowns; budget
~20 GB. Note: a **network volume bills for storage** even when 0 workers run
(small, GB-month) — separate from GPU compute.

## 9. Environment variables (Azure backend)

| Variable | Required? | Secret? | Example | Purpose |
|---|---|---|---|---|
| `LLM_BACKEND` | yes | no | `runpod_serverless` | selects the provider |
| `RUNPOD_ENDPOINT_ID` | yes (serverless) | no | `abc123xyz` | the endpoint from §7.16 |
| `RUNPOD_API_KEY` | yes (serverless) | **YES** | `<secret>` | Bearer auth to RunPod — **backend only** |
| `RUNPOD_SERVERLESS_BASE_URL` | no | no | `https://api.runpod.ai/v2` | RunPod API base |
| `RUNPOD_SERVERLESS_TIMEOUT_SECONDS` | no | no | `180` | per-inference budget |
| `HOSTED_QWEN_MODEL` | no | no | `qwen3:8b` | model tag sent to the worker |
| `SCHEDULER_ENABLED` | yes (pilot) | no | `false` | disables the daily GPU-triggering cron |

Get a RunPod **API key**: RunPod → Settings → **API Keys** → create. Put it **only**
in the Azure backend `.env` / secret store. Never in git, the image, the frontend,
or logs.

## 10. GPU sizing

qwen3:8b in Ollama's default quant needs roughly **6–10 GB** VRAM for weights +
KV cache at a modest context. A ~16–24 GB GPU gives comfortable margin. Measure
during testing (§16 in the migration report): VRAM after load, VRAM peak, context
tested. If you hit OOM, check quant/context/params **before** upgrading GPU tier.

## 11. Direct endpoint test (curl)

```bash
export RUNPOD_ENDPOINT_ID=<endpoint-id>
export RUNPOD_API_KEY=<secret>

curl -sS -X POST \
  "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "operation": "chat",
      "model": "qwen3:8b",
      "messages": [
        { "role": "user", "content": "Reply with exactly: SERVERLESS_OK" }
      ],
      "stream": false,
      "think": false,
      "options": { "num_predict": 50 }
    }
  }'
```

**Expected** (shape): `{"id":"...","status":"COMPLETED","delayTime":...,`
`"executionTime":...,"output":{"model":"qwen3:8b",`
`"message":{"role":"assistant","content":"SERVERLESS_OK"},"done":true}}`.
The **first** call after idle is slow (cold start + model load) — that is normal.

## 12. Azure configuration

Set the §9 variables in the VM's backend `.env`, then redeploy the backend
(`deploy/azure/deploy.sh <tag>`). The frontend is unchanged (it never talks to
RunPod). CORS/API base are unchanged.

## 13. End-to-end Visentix test

Log in → **Analyse Notice** a URL/paste → watch status reach `complete` → open the
report. Confirm output parity vs the old Pod (§55 of the migration prompt): schema
valid, categories sane, narrative present.

## 14. Cold-start behavior

The first Analyse after idle waits for a worker to start + the model to load
(seconds to ~1 min). The pipeline runs in the background and the frontend polls
status for up to 5 minutes, so the user sees "Classifying…", not a failure. Do
**not** fix cold starts by setting Active Workers > 0 (that recreates 24/7 billing).

## 15. Scale-to-zero verification

In the RunPod endpoint page, the **Workers** panel shows active/idle counts. After
an analysis finishes and the idle timeout passes, it must return to **0 active
workers**. If a worker stays up indefinitely, the migration is **not** complete —
see Troubleshooting → "workers never return to zero".

## 16. Logging / monitoring

- **Backend** logs per inference (no secrets, no prompt text): `provider`,
  `operation`, `status`, `delayTime`, `executionTime`, `duration_ms`, `job_id`.
- **RunPod console** → endpoint → **Requests / Metrics**: worker count, queue depth,
  cold-start delay, execution time, errors.

## 17. Billing behavior (accurate)

Serverless Flex bills **while a worker exists**: startup + model load + inference +
the idle-timeout window all count; then the worker terminates and GPU billing
stops. It is **not** "only token time" and **not** "exactly 65 s/doc" — cold start
and idle count too. A **network volume** also bills small storage while idle. Use
the RunPod metrics (`delayTime`/`executionTime`) for real numbers.

## 18. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `401 Unauthorized` | Wrong/missing `RUNPOD_API_KEY` on the Azure side. Regenerate; set backend-only. |
| `403 Forbidden` | API key lacks access to this endpoint / wrong account. |
| `404` endpoint not found | Wrong `RUNPOD_ENDPOINT_ID` or base URL. |
| `429` | Endpoint at max workers / account rate limit. Backend retries with backoff; raise max workers to 2 if needed. |
| Worker stuck `INITIALIZING` | Image pull slow / model download on first start. Attach a network volume; check FlashBoot. |
| Worker `FAILED` | See RunPod request logs. Common: Ollama not started, model missing, OOM. |
| Ollama won't start | Check the worker's `ollama serve` logs; base image/version mismatch. |
| qwen3 model missing / re-downloads every start | Network volume not attached, or `OLLAMA_MODELS` not pointing at it. |
| GPU OOM | Reduce context/params or move up **one** GPU tier; verify quant. |
| Request times out | Raise `RUNPOD_SERVERLESS_TIMEOUT_SECONDS` / endpoint execution timeout; check cold-start size. |
| `COMPLETED` but malformed output | Worker output contract drift — must be `{"message":{"content":...}}`. |
| Backend gets 502/503 | Transient RunPod 5xx — backend retries (bounded). |
| Works locally, not in prod | Azure `.env` missing `LLM_BACKEND`/`RUNPOD_*`; check startup validation log. |
| **/health starts a GPU worker** | Should be impossible now — `/health` never probes hosted/serverless. If seen, something else is calling the endpoint (see next row). |
| **Workers never return to zero** | Investigate in order: Active workers accidentally > 0; idle timeout too high; `SCHEDULER_ENABLED=true` (daily `monitor_notices`); an external monitor/curl loop hitting `/runsync`; Bulk Analysis backlog; a health check wired to the model. |
| Bulk Analysis slow | Expected at max workers = 1 (jobs queue). Raise to 2 after cost is verified. |

## 19. Rollback (to the legacy Pod)

1. Ensure the old Pod `1zyg93j5rzy4p4` is running (or restart it with
   `pod-entrypoint.sh`).
2. Azure `.env`: `LLM_BACKEND=hosted_ollama` and `HOSTED_QWEN_BASE_URL=http://100.69.10.127:11434`.
3. Redeploy the backend. Inference goes back to the always-on Pod immediately.
   (No code change — the `_chat_hosted_ollama` path is retained.)

## 20. Retiring the old Pod (operator action — do this LAST)

Only after Serverless is validated end-to-end and scale-to-zero is confirmed:
1. **STOP** Pod `1zyg93j5rzy4p4` (RunPod console). Confirm Visentix still works on
   Serverless. Keep it stopped through your rollback window.
2. Then **DELETE** the Pod. Also delete/repurpose its **`/workspace` volume** — a
   stopped Pod's **volume still bills storage** until removed.
3. Billing components to check are separate: Pod compute, Pod volume, Serverless
   compute, Serverless network volume.

> Nothing in this repo stops/deletes the Pod automatically. That is an explicit
> operator action after parity verification.

---

## Legacy — always-on Pod (rollback reference only)

`pod-entrypoint.sh` + `docker-compose.yml` describe the **legacy** always-on Pod:
a supervisor that runs `ollama serve` 24/7 with `OLLAMA_KEEP_ALIVE=-1`, exposed on
the tailnet (`100.69.10.127:11434`). This is the architecture the Serverless
migration replaces (it bills continuously). Keep it only for the rollback in §19.
Production runtime must not depend on `100.69.10.127` / `11434` once migrated.
