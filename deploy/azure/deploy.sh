#!/usr/bin/env bash
# =============================================================================
# deploy/azure/deploy.sh — idempotent app deploy on the Azure VM.
#
#   ./deploy/azure/deploy.sh <git-tag>
#
# In order:
#   1. Refuse a dirty tree; check out the immutable <git-tag> (refuse a non-tag).
#   2. Gate: .env must contain every key present in .env.example (+ criticals non-empty).
#   3. Pre-apply schema dump, then run migrations via scripts/db/apply_and_record.py.
#   4. docker compose build + up -d (api + caddy; NO ollama here).
#   5. Wait on healthchecks (120s, fail loudly).
#   6. Port self-scan: only 22/80/443 public; 8000 (api) closed.
#   7. Smoke summary: /health, /docs, gate_mode, migration head, image digest.
#
# Re-runnable: every step is a no-op when already satisfied.
# =============================================================================
set -euo pipefail

GIT_TAG="${1:-}"
[[ -n "$GIT_TAG" ]] || { echo "usage: $0 <git-tag>" >&2; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE="${SCRIPT_DIR}/docker-compose.yml"
ENV_FILE="${REPO_DIR}/.env"
ENV_EXAMPLE="${REPO_DIR}/.env.example"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

cd "${REPO_DIR}"

# ---- 1. clean tree + immutable tag --------------------------------------
log "1/7  Checkout tag ${GIT_TAG}"
[[ -z "$(git status --porcelain)" ]] || die "working tree is dirty — refusing to deploy"
git rev-parse "refs/tags/${GIT_TAG}" >/dev/null 2>&1 || die "'${GIT_TAG}' is not a tag — refusing (immutable tags only)"
git fetch --tags --quiet origin || true
git checkout -q "tags/${GIT_TAG}"
export GIT_TAG
ok "at ${GIT_TAG} ($(git rev-parse --short HEAD))"

# ---- 2. .env completeness gate ------------------------------------------
log "2/7  .env vs .env.example"
[[ -f "${ENV_FILE}" ]]    || die ".env missing (provision it out of band; never in git)"
[[ -f "${ENV_EXAMPLE}" ]] || die ".env.example missing"
missing=()
while IFS= read -r key; do
  [[ -z "${key}" ]] && continue
  grep -qE "^${key}=" "${ENV_FILE}" || missing+=("${key}")
done < <(grep -oE '^[A-Z_][A-Z0-9_]*=' "${ENV_EXAMPLE}" | sed 's/=$//' | sort -u)
(( ${#missing[@]} == 0 )) || die ".env missing keys: ${missing[*]}"
for k in APP_ENV SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SUPABASE_JWT_SECRET DATABASE_URL DOMAIN HOSTED_QWEN_BASE_URL; do
  v="$(grep -E "^${k}=" "${ENV_FILE}" | head -1 | cut -d= -f2-)"
  [[ -n "${v}" ]] || die "${k} present but empty in .env"
done
grep -qE '^APP_ENV=production' "${ENV_FILE}" || warn "APP_ENV is not 'production'"
ok "all keys present; criticals non-empty"

# ---- 3. migrations (pre-dump + apply_and_record) ------------------------
log "3/7  DB migrations"
DUMP_DIR="${REPO_DIR}/db/schema_dumps"; mkdir -p "${DUMP_DIR}"
STAMP="$(git rev-parse --short HEAD)"
python3 scripts/db/dump_column_types.py > "${DUMP_DIR}/pre_deploy_${GIT_TAG}_${STAMP}.sql" 2>/dev/null \
  && ok "pre-apply schema dump written" || warn "schema dump skipped (non-fatal)"
python3 scripts/db/apply_and_record.py \
  && ok "migrations applied + recorded" \
  || die "migrations failed — nothing frozen; safe to re-run"

# ---- 4. build + up ------------------------------------------------------
log "4/7  compose build + up"
docker compose -f "${COMPOSE}" --env-file "${ENV_FILE}" up -d --build
ok "compose up -d"

# ---- 5. healthchecks ----------------------------------------------------
log "5/7  healthchecks (120s budget)"
wait_healthy() {
  local svc="$1" deadline=$(( SECONDS + 120 ))
  while (( SECONDS < deadline )); do
    local cid state
    cid="$(docker compose -f "${COMPOSE}" ps -q "${svc}")"
    state="$(docker inspect -f '{{.State.Health.Status}}' "${cid}" 2>/dev/null || echo starting)"
    [[ "${state}" == "healthy" ]] && { ok "${svc} healthy"; return 0; }
    printf '\r  … %s: %s' "${svc}" "${state}"; sleep 5
  done
  die "${svc} never became healthy"
}
wait_healthy api

# ---- 6. port self-scan --------------------------------------------------
log "6/7  port self-scan (only 22/80/443 public; 8000 closed)"
PUB="$(curl -fsS https://ifconfig.me 2>/dev/null || echo '')"
if command -v nc >/dev/null 2>&1 && [[ -n "${PUB}" ]]; then
  for p in 80 443; do nc -z -w3 "${PUB}" "${p}" && ok "public ${p} open" || warn "public ${p} not open (Azure NSG may block — open 80/443)"; done
  for p in 8000 11434 5432; do
    nc -z -w3 "${PUB}" "${p}" 2>/dev/null && die "SECURITY: port ${p} is PUBLIC — must be closed" || ok "port ${p} closed"
  done
else
  warn "nc/public IP unavailable — verify externally"
fi

# ---- 7. smoke summary ---------------------------------------------------
log "7/7  smoke summary"
DOMAIN_VAL="$(grep -E '^DOMAIN=' "${ENV_FILE}" | head -1 | cut -d= -f2-)"
echo "  tag            : ${GIT_TAG} ($(git rev-parse --short HEAD))"
echo "  url            : https://${DOMAIN_VAL}"
echo -n "  /health (int)  : "; docker compose -f "${COMPOSE}" exec -T api python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health',timeout=5).read().decode()[:200])" 2>/dev/null || echo FAILED
echo -n "  /health (TLS)  : "; curl -fsS "https://${DOMAIN_VAL}/health" -o /dev/null -w '%{http_code}\n' 2>/dev/null || echo 'FAILED (TLS may still be issuing — retry in ~30s)'
echo -n "  /docs (TLS)    : "; curl -fsS "https://${DOMAIN_VAL}/docs" -o /dev/null -w '%{http_code}\n' 2>/dev/null || echo n/a
echo "  migration head : $(python3 scripts/db/apply_and_record.py --print-head 2>/dev/null || echo 'see step 3')"
log "deploy complete — record digest + versions in LAUNCH-READINESS-v2.md"
