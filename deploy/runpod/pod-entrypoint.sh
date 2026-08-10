#!/bin/bash
# =============================================================================
# ⚠️  LEGACY — always-on Pod (ROLLBACK ONLY). Superseded by RunPod Serverless
#     (deploy/runpod/serverless/ + deploy/runpod/README.md). This supervisor runs
#     ollama 24/7 with OLLAMA_KEEP_ALIVE=-1 and therefore BILLS CONTINUOUSLY. Do
#     NOT use this pattern for the Serverless worker (RunPod must scale to zero).
#     Kept so the Pod can be restarted for the rollback path (README §19).
# =============================================================================
# pod-entrypoint.sh — RunPod GPU pod start command (Ollama + embeddings, PRIVATE).
#
# Pulled fresh from a gist by the pod's Container Start Command on every (re)start:
#   bash -c "... curl -fsSL <gist>/raw/pod-entrypoint.sh -o /workspace/pod-entrypoint.sh
#            && exec bash /workspace/pod-entrypoint.sh"
#
# It is a SUPERVISOR that NEVER exits (so the container can't crash-loop) and
# self-heals Ollama + Tailscale if either dies. It re-establishes the whole
# private posture on every start:
#   * Ollama bound to 127.0.0.1 ONLY (never 0.0.0.0, never a public port).
#   * Tailscale in userspace-networking mode (this pod image has no /dev/net/tun),
#     state persisted on /workspace so the node identity + tailnet IP are stable.
#   * `tailscale serve` exposes Ollama on the tailnet ONLY (tcp 11434 -> localhost).
#   * The pinned model qwen3:8b lives on the persistent /workspace volume.
#
# TAILSCALE_AUTHKEY comes from the pod ENV (a RunPod Secret) — reusable, non-
# ephemeral. All output is teed to /workspace/entrypoint.log for diagnosis.
# =============================================================================
set +e
exec > >(tee -a /workspace/entrypoint.log) 2>&1
echo "===================================================================="
echo "[entrypoint] start $(date -u 2>/dev/null || echo '?')"

STATE=/workspace/tailscale
SOCK=/var/run/tailscale/tailscaled.sock
MODEL="${QWEN_LOCAL_MODEL:-qwen3:8b}"
TS="tailscale --socket=$SOCK"

export OLLAMA_HOST=127.0.0.1
export OLLAMA_MODELS="${OLLAMA_MODELS:-/workspace/.ollama}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-4}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}"
mkdir -p "$STATE" /var/run/tailscale "$OLLAMA_MODELS"

log(){ echo "[entrypoint $(date -u +%H:%M:%S 2>/dev/null)] $*"; }

# ---- 0. Prereqs (container disk is wiped on restart; ollama image is minimal) --
if ! command -v curl >/dev/null 2>&1 || ! command -v ss >/dev/null 2>&1; then
  log "installing prereqs"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq curl ca-certificates iproute2 nmap
fi
if ! command -v tailscale >/dev/null 2>&1; then
  log "installing tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

start_tailscale(){
  if ! pgrep -x tailscaled >/dev/null 2>&1; then
    log "starting tailscaled (userspace)"
    nohup tailscaled --tun=userspace-networking --state="$STATE/tailscaled.state" --socket="$SOCK" >/workspace/tailscaled.log 2>&1 &
    sleep 5
  fi
  log "tailscale up"
  $TS up ${TAILSCALE_AUTHKEY:+--authkey="$TAILSCALE_AUTHKEY"} --hostname=visentix-runpod --accept-dns=false
  log "tailscale up rc=$?  ip=$($TS ip -4 2>/dev/null | head -1)"
  $TS serve --bg --tcp 11434 tcp://127.0.0.1:11434
  log "tailscale serve rc=$?"
}

start_ollama(){
  log "starting ollama serve (bound $OLLAMA_HOST)"
  nohup ollama serve >/workspace/ollama.log 2>&1 &
  for _ in $(seq 1 30); do ollama list >/dev/null 2>&1 && break; sleep 2; done
  if ! ollama list 2>/dev/null | grep -q "$MODEL"; then
    log "pulling $MODEL"
    ollama pull "$MODEL"
  fi
  log "ollama ready; models: $(ollama list 2>/dev/null | awk 'NR>1{print $1}' | paste -sd, -)"
}

start_ollama
start_tailscale

# ---- Supervisor: never exit; resurrect whatever dies -----------------------
log "entering supervisor loop"
while true; do
  pgrep -x ollama     >/dev/null 2>&1 || { log "ollama died — restarting";     start_ollama; }
  pgrep -x tailscaled >/dev/null 2>&1 || { log "tailscaled died — restarting"; start_tailscale; }
  # keep serve config alive even if tailscaled stayed up but lost it
  $TS serve status 2>/dev/null | grep -q 11434 || $TS serve --bg --tcp 11434 tcp://127.0.0.1:11434 >/dev/null 2>&1
  sleep 20
done
