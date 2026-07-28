#!/usr/bin/env bash
# =============================================================================
# deploy_runpod.sh — idempotent Visentix deploy to a RunPod GPU VM.
#
#   sudo ./deploy/deploy_runpod.sh <git-tag> [repo-url]
#
# Does, in order:
#   1. Install Docker + compose plugin + NVIDIA container toolkit if absent.
#   2. Checkout/pull the repo at <git-tag> (refuses a dirty tree).
#   3. Verify .env has every key present in .env.example (refuses otherwise).
#   4. compose up -d  (build api, GPU ollama, caddy).
#   5. Run DB migrations against prod Supabase (scripts/db/apply_and_record.py).
#   6. Wait on api + ollama healthchecks.
#   7. Firewall / port-scan check: only 443 (and 80 for ACME) public; 8000/11434
#      NOT reachable from outside; SSH is key-only.
#   8. Print a smoke summary (/health, /docs, model list, image digests).
#
# Re-runnable: every step is a no-op when already satisfied.
# =============================================================================
set -euo pipefail

# ---- args ----------------------------------------------------------------
GIT_TAG="${1:-}"
REPO_URL="${2:-https://github.com/zssain/visentix-v2--MVP.git}"
if [[ -z "${GIT_TAG}" ]]; then
  echo "usage: $0 <git-tag> [repo-url]" >&2
  exit 2
fi

# Resolve the deploy root: the parent of this script's directory (repo root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.prod.yml"
ENV_FILE="${REPO_DIR}/.env"
ENV_EXAMPLE="${REPO_DIR}/.env.example"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ---- 1. dependencies -----------------------------------------------------
log "1/8  Checking Docker + NVIDIA toolkit"
if ! command -v docker >/dev/null 2>&1; then
  warn "docker not found — installing via get.docker.com"
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || die "docker compose plugin missing"
ok "docker $(docker --version | awk '{print $3}' | tr -d ,)"

if ! docker info 2>/dev/null | grep -qi nvidia; then
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    warn "NVIDIA container toolkit not detected — installing"
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update && apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
  fi
fi
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1 \
  && ok "GPU visible to Docker" \
  || warn "GPU not visible to Docker — ollama will fall back to CPU (slow). Check the RunPod GPU + toolkit."

# ---- 2. repo at tag ------------------------------------------------------
log "2/8  Repo at tag ${GIT_TAG}"
if [[ -d "${REPO_DIR}/.git" ]]; then
  git -C "${REPO_DIR}" fetch --tags --force origin
else
  git clone "${REPO_URL}" "${REPO_DIR}"
fi
# MUST NOT deploy from a dirty tree.
if [[ -n "$(git -C "${REPO_DIR}" status --porcelain)" ]]; then
  die "working tree is dirty — refusing to deploy. Commit/stash first."
fi
git -C "${REPO_DIR}" checkout -q "tags/${GIT_TAG}" 2>/dev/null \
  || git -C "${REPO_DIR}" checkout -q "${GIT_TAG}"
ok "checked out ${GIT_TAG} ($(git -C "${REPO_DIR}" rev-parse --short HEAD))"
export GIT_TAG

# ---- 3. .env completeness gate ------------------------------------------
log "3/8  Verifying .env against .env.example"
[[ -f "${ENV_FILE}" ]]     || die ".env missing at ${ENV_FILE} (never committed — provision it out of band)"
[[ -f "${ENV_EXAMPLE}" ]]  || die ".env.example missing"
missing=()
while IFS= read -r key; do
  [[ -z "${key}" ]] && continue
  grep -qE "^${key}=" "${ENV_FILE}" || missing+=("${key}")
done < <(grep -oE '^[A-Z_][A-Z0-9_]*=' "${ENV_EXAMPLE}" | sed 's/=$//' | sort -u)
if (( ${#missing[@]} )); then
  die ".env is missing required keys: ${missing[*]}"
fi
# Critical keys must additionally be NON-empty.
for k in APP_ENV SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SUPABASE_JWT_SECRET DATABASE_URL DOMAIN; do
  val="$(grep -E "^${k}=" "${ENV_FILE}" | head -1 | cut -d= -f2-)"
  [[ -n "${val}" ]] || die "${k} is present but empty in .env"
done
grep -qE '^APP_ENV=production' "${ENV_FILE}" || warn "APP_ENV is not 'production' in .env"
ok "all $(grep -coE '^[A-Z_][A-Z0-9_]*=' "${ENV_EXAMPLE}") keys present; critical keys non-empty"

# ---- 4. compose up -------------------------------------------------------
log "4/8  Building + starting the stack"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build
ok "compose up -d issued"

# ---- 5. migrations against prod Supabase ---------------------------------
log "5/8  Applying DB migrations (scripts/db/apply_and_record.py)"
# Run inside the api container so it uses the pinned Python env + DATABASE_URL.
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T api \
  python scripts/db/apply_and_record.py \
  && ok "migrations applied + recorded in schema_migrations" \
  || die "migrations failed — see output above (nothing frozen; safe to re-run)"

# ---- 6. healthchecks -----------------------------------------------------
log "6/8  Waiting on healthchecks"
wait_healthy() {
  local svc="$1" tries="${2:-60}"
  for ((i=1; i<=tries; i++)); do
    local cid state
    cid="$(docker compose -f "${COMPOSE_FILE}" ps -q "${svc}")"
    [[ -n "${cid}" ]] || { sleep 5; continue; }
    state="$(docker inspect -f '{{.State.Health.Status}}' "${cid}" 2>/dev/null || echo unknown)"
    [[ "${state}" == "healthy" ]] && { ok "${svc} healthy"; return 0; }
    printf '\r  … %s: %s (%d/%d)' "${svc}" "${state}" "${i}" "${tries}"
    sleep 10
  done
  die "${svc} never became healthy"
}
wait_healthy ollama 40   # first model pull is slow
wait_healthy api 30

# ---- 7. firewall / port-scan verification --------------------------------
log "7/8  Firewall + port-scan (only 443/80 public; 8000/11434 closed; SSH key-only)"
PUBLIC_IP="$(curl -fsS https://ifconfig.me 2>/dev/null || echo '')"
if command -v nc >/dev/null 2>&1 && [[ -n "${PUBLIC_IP}" ]]; then
  for port in 443 80; do
    nc -z -w3 "${PUBLIC_IP}" "${port}" && ok "public ${port} open (expected)" \
      || warn "public ${port} NOT open — check RunPod port mapping / Caddy"
  done
  for port in 8000 11434 5432; do
    if nc -z -w3 "${PUBLIC_IP}" "${port}" 2>/dev/null; then
      die "SECURITY: port ${port} is PUBLICLY reachable — must be closed (never expose api/ollama/postgres)"
    else
      ok "port ${port} closed to the public"
    fi
  done
else
  warn "nc or public IP unavailable — verify externally: nmap -Pn ${PUBLIC_IP:-<vm-ip>} should show only 80,443"
fi
# SSH must be key-only.
if grep -RqsiE '^\s*PasswordAuthentication\s+yes' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null; then
  warn "sshd PasswordAuthentication is enabled — set it to 'no' (key-only) and restart sshd"
else
  ok "sshd password auth disabled (key-only) or default-off"
fi

# ---- 8. smoke summary ----------------------------------------------------
log "8/8  Smoke summary"
DOMAIN_VAL="$(grep -E '^DOMAIN=' "${ENV_FILE}" | head -1 | cut -d= -f2-)"
echo "  deployed tag        : ${GIT_TAG} ($(git -C "${REPO_DIR}" rev-parse --short HEAD))"
echo "  public URL          : https://${DOMAIN_VAL}"
echo "  api image digest    : $(docker inspect --format='{{index .RepoDigests 0}}{{if not .RepoDigests}}{{.Id}}{{end}}' "visentix-api:${GIT_TAG}" 2>/dev/null || echo 'n/a')"
echo "  ollama image        : $(docker compose -f "${COMPOSE_FILE}" images ollama --quiet | xargs -r docker inspect --format='{{.Id}}' 2>/dev/null || echo 'n/a')"
echo -n "  /health (internal)  : "; docker compose -f "${COMPOSE_FILE}" exec -T api \
  python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://localhost:8000/health'))if True else'')" 2>/dev/null | head -c 200 || echo 'FAILED'
echo ""
echo -n "  /health (public TLS): "; curl -fsS "https://${DOMAIN_VAL}/health" -o /dev/null -w '%{http_code}\n' 2>/dev/null || echo 'FAILED (TLS may still be issuing — retry in ~30s)'
echo -n "  ollama models       : "; docker compose -f "${COMPOSE_FILE}" exec -T ollama ollama list 2>/dev/null | awk 'NR>1{print $1}' | paste -sd, - || echo 'n/a'
log "Deploy complete. Record digests + model versions in LAUNCH-READINESS-v2.md."
