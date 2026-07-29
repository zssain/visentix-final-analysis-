# RunPod GPU pod — Ollama + embeddings (PRIVATE, tailnet-only)

The GPU leaf node. Runs **Ollama** (`qwen3:8b`) for classification/phrasing and is
where the **embedding backfill** runs. It is never reachable from the public
internet — the Azure VM calls it over the Tailscale tailnet.

## Live facts (2026-07-29)

| | |
|---|---|
| Pod ID | `1zyg93j5rzy4p4` |
| GPU | NVIDIA RTX 4000 Ada, 20 GB |
| Image / template | `ollama/ollama` (RunPod "Ollama NVIDIA CUDA") |
| Model | `qwen3:8b` (5.2 GB) on the persistent `/workspace` volume |
| Tailnet IP | `100.69.10.127` (MagicDNS: `visentix-runpod.tail813107.ts.net`) |
| Persistent volume | `/workspace` (model at `/workspace/.ollama`, tailscale state at `/workspace/tailscale`) |

## Why userspace-networking Tailscale

This pod image has **no `/dev/net/tun`**, so Tailscale cannot create a kernel
interface. We run `tailscaled --tun=userspace-networking` and expose Ollama with
`tailscale serve` (tailnet-only). Ollama binds **`127.0.0.1` only** — never
`0.0.0.0`, never a published RunPod port. The owner rejected the caddy-sidecar +
bearer-token + IP-allowlist fallback (public port, static token, egress-IP
dependency); see `logs/decision-log.md` (2026-07-29).

## Restart behavior (IMPORTANT — RunPod pods restart more than VMs)

Restart-survival is baked into **`pod-entrypoint.sh`**. Set it as the pod's
**Container Start Command** so it runs on every (re)start:

```
bash /workspace/pod-entrypoint.sh
```

On each start it (idempotently): installs Tailscale if missing → starts
`tailscaled` (userspace, state on `/workspace`) → `tailscale up` (reusable
non-ephemeral authkey from the `TAILSCALE_AUTHKEY` **RunPod Secret**) → starts
`ollama serve` bound to `127.0.0.1` → pulls `qwen3:8b` (no-op if present) →
`tailscale serve --tcp 11434 → 127.0.0.1:11434`. Because tailscaled state and the
model both live on the persistent volume, the tailnet IP and model are stable
across restarts and nothing re-downloads.

If the Container Start Command is NOT set (e.g. the stock template start command
`/bin/ollama serve`), a restart brings Ollama back on `0.0.0.0` with no Tailscale.
Re-run `bash /workspace/pod-entrypoint.sh` by hand to recover, then set the start
command so it is automatic.

## How the Azure VM reaches Ollama

The app's hosted backend (`app/services/llm.py::_chat_hosted`) posts to
`${HOSTED_QWEN_BASE_URL}/api/chat` — the SAME native Ollama call as local
(`think:false`, `num_predict:500`); no API key needed on the tailnet.

`HOSTED_QWEN_BASE_URL` is verified from the Azure VM (the first real second
tailnet node) before it is locked in — a self-connection test from the pod is
invalid in userspace mode, so the scheme is confirmed there:
- primary: `http://100.69.10.127:11434` (raw-TCP passthrough)
- if the tailnet serve turns out TLS-terminated: `https://visentix-runpod.tail813107.ts.net:11434`

Owner condition-1 (`ss` proof of the `127.0.0.1`-only bind + a public-IP port
self-scan) and condition-3 (measured Azure→pod classify latency, 5-clause smoke)
are run from Azure and recorded in `LAUNCH-READINESS-v2.md`.

## Files

- `pod-entrypoint.sh` — the Container Start Command (above).
- `docker-compose.yml` — reference/self-host equivalent of the same contract
  (RunPod runs a single container, not compose, so this is documentation + a
  portable definition for any GPU host that does run compose).
