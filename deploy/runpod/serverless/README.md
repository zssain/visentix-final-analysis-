# Visentix RunPod Serverless worker

Ollama + `qwen3:8b`, scale-to-zero. Full deployment runbook (endpoint creation,
GPU/idle settings, model storage, Azure config, rollback, retirement):
**see `../README.md`.**

## Local test (no GPU / no runpod SDK)
```bash
pytest deploy/runpod/serverless/tests -q
```
`handler.py` is import-safe — Ollama startup and `runpod.serverless.start` run only
under `__main__`, so the handler is unit-tested directly with the Ollama call mocked.

## Build (linux/amd64 — required for RunPod GPU nodes)
Build context = repo root (matches RunPod's GitHub build). Run from the repo root:
```bash
docker buildx build --platform linux/amd64 \
  --build-arg OLLAMA_VERSION=0.5.11 \
  -f deploy/runpod/serverless/Dockerfile \
  -t <registry>/visentix-runpod-serverless:<date>-<sha> \
  . --push
```
RunPod GitHub build: Dockerfile path = `/deploy/runpod/serverless/Dockerfile`.

## Contract
Input:
```json
{"input":{"operation":"chat","model":"qwen3:8b",
          "messages":[{"role":"system","content":"..."},{"role":"user","content":"..."}],
          "stream":false,"think":false,"options":{"num_predict":500}}}
```
Output (RunPod wraps this in `output`):
```json
{"model":"qwen3:8b","message":{"role":"assistant","content":"..."},"done":true}
```

Rules: **no forever-supervisor**, no `OLLAMA_KEEP_ALIVE=-1`, Ollama bound to
`127.0.0.1` only, `RUNPOD_API_KEY` never in this image (it's the Azure side).
