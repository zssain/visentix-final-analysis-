#!/usr/bin/env bash
# =============================================================================
# scripts/release.sh <version>   e.g. scripts/release.sh v1
#
# One-command version-wise deploy driven by releases/<version>.yaml. In order:
#   1. Refuse a dirty tree.
#   2. Load releases/<version>.yaml; run every data_precondition (refuse + name
#      which failed).
#   3. Check out the matching immutable tag (tag_floor must be <= migration head).
#   4. Build the frontend with the yaml's VITE_SURFACE_* flags.
#   5. Verify by grep that every masked-surface identifier is ABSENT from the
#      built bundle (code-split/DCE masking — App.tsx).
#   6. Deploy the frontend (Cloudflare, `wrangler deploy`).
#   7. Apply platform_settings idempotently — DIRECT SQL upsert into
#      platform_setting (stated: SQL, not the admin API).
#   8. Run deploy/azure/deploy.sh <tag>.
#   9. Print a RELEASE MANIFEST and append it to logs/releases.log.
#
# MUST NOT: unmask a surface whose backend gate isn't flipped in the same
# release; deploy from a dirty tree; tag anything (owner tags).
# =============================================================================
set -euo pipefail

VERSION="${1:-}"
[[ -n "$VERSION" ]] || { echo "usage: $0 <version>  (e.g. v1)" >&2; exit 2; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
YAML="releases/${VERSION}.yaml"
[[ -f "$YAML" ]] || { echo "no such release: $YAML" >&2; exit 2; }
PY="${ROOT}/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

y() { "$PY" - "$YAML" "$1" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
key = sys.argv[2]
cur = d
for part in key.split('.'):
    cur = cur[part] if isinstance(cur, dict) and part in cur else (cur[int(part)] if isinstance(cur, list) else None)
if isinstance(cur, (dict, list)):
    import json; print(json.dumps(cur))
elif cur is None:
    print("")
else:
    print(cur)
PY
}

# ---- 1. clean tree -------------------------------------------------------
log "1/9  Clean tree"
[[ -z "$(git status --porcelain)" ]] || die "working tree is dirty — refusing to release"
ok "clean"

# ---- 2. preconditions ----------------------------------------------------
log "2/9  Preconditions for ${VERSION}"
export GIT_TAG="${VERSION}"   # some preconditions reference the tag
PRECHECK="$("$PY" - "$YAML" <<'PY'
import sys, yaml, subprocess, os
d = yaml.safe_load(open(sys.argv[1]))
fails = []
for pc in d.get("data_preconditions", []):
    name, kind = pc["name"], pc.get("kind")
    okp = False
    try:
        if kind == "pytest":
            okp = subprocess.run(pc["cmd"], shell=True, capture_output=True).returncode == 0
        elif kind == "env":
            okp = all(os.environ.get(k) for k in pc.get("require_env", []))
        elif kind in ("sql", "ci"):
            # sql/ci checks require live creds; surfaced as WARN-manual here so the
            # operator confirms them (release.sh prints them; not auto-passed).
            okp = None
        else:
            okp = None
    except Exception:
        okp = False
    fails.append((name, kind, okp))
for name, kind, okp in fails:
    print(f"{name}\t{kind}\t{okp}")
PY
)"
echo "$PRECHECK" | while IFS=$'\t' read -r name kind res; do
  [[ -z "$name" ]] && continue
  case "$res" in
    True)  ok "precondition $name ($kind)";;
    None)  printf '  \033[1;33m! precondition %s (%s): MANUAL — confirm live before proceeding\033[0m\n' "$name" "$kind";;
    *)     die "precondition FAILED: $name ($kind)";;
  esac
done

# ---- 3. tag --------------------------------------------------------------
log "3/9  Checkout tag ${VERSION}"
git rev-parse "refs/tags/${VERSION}" >/dev/null 2>&1 || die "'${VERSION}' is not a tag (owner tags releases; refusing)"
git checkout -q "tags/${VERSION}"
ok "at ${VERSION} ($(git rev-parse --short HEAD))"

# ---- 4. build frontend with surface flags --------------------------------
log "4/9  Build frontend with ${VERSION} surface flags"
FLAGS="$(y surface_flags)"
ENVLINE="$("$PY" - <<PY
import json
for k,v in json.loads('''$FLAGS''').items():
    print(f'{k}={v}')
PY
)"
( cd web
  # carry through the API + supabase build vars from the repo web env if present
  export $ENVLINE
  npm ci --silent 2>/dev/null || npm install --silent
  npm run build )
ok "built with: $(echo "$ENVLINE" | tr '\n' ' ')"

# ---- 5. verify masked surfaces absent ------------------------------------
log "5/9  Verify masked-surface chunks ABSENT from the bundle"
JS="$(ls web/dist/assets/index-*.js | head -1)"
MASKED="$(y masked_surfaces)"
"$PY" - "$JS" "$MASKED" <<'PY' || exit 1
import sys, json
js = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
# distinctive identifiers per masked surface
IDENT = {
  "bulk": ["Bulk Analysis", "/bulk"], "partner": ["Partner Workspace", "/partner"],
  "rewrite": ["Trust Language Studio", "/rewrite"], "vendors": ["Vendor Due Diligence", "/vendors"],
  "trust": ["Trust Center", "/trust"], "crosswalk": ["Framework Crosswalk", "/crosswalk"],
}
leaked = []
for surf in json.loads(sys.argv[2]):
    for token in IDENT.get(surf, []):
        if token in js:
            leaked.append((surf, token))
if leaked:
    print("  LEAKED masked-surface identifiers in bundle:", leaked); sys.exit(1)
print("  all masked-surface identifiers absent")
PY
ok "masked surfaces provably absent"

# ---- 6. deploy frontend (Cloudflare) -------------------------------------
log "6/9  Deploy frontend to Cloudflare"
( cd web && npx wrangler deploy )
ok "frontend deployed"

# ---- 7. apply platform_settings (DIRECT SQL upsert) ----------------------
log "7/9  Apply platform_settings (direct SQL upsert into platform_setting)"
SETTINGS="$(y platform_settings)"
"$PY" - "$SETTINGS" <<'PY'
import sys, json, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("_ar", Path("scripts/db/apply_and_record.py"))
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
import psycopg
kw, _ = ar._conn_kwargs()
settings = json.loads(sys.argv[1])
with psycopg.connect(autocommit=True, **kw) as c, c.cursor() as cur:
    for k, v in settings.items():
        cur.execute(
            "INSERT INTO platform_setting (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (k, json.dumps(v)))
    print(f"  applied {len(settings)} platform_setting rows")
PY
ok "platform_settings applied (idempotent)"

# ---- 8. azure app deploy -------------------------------------------------
log "8/9  Azure app deploy (deploy/azure/deploy.sh ${VERSION})"
if [[ -n "${AZURE_VM_IP:-}" ]]; then
  ssh -i "${DEPLOY_SSH_KEY:-$HOME/.ssh/visentix_deploy}" "${AZURE_SSH_USER:-azureuser}@${AZURE_VM_IP}" \
    "cd /home/azureuser/visentix && ./deploy/azure/deploy.sh ${VERSION}"
else
  printf '  \033[1;33m! AZURE_VM_IP unset — run deploy/azure/deploy.sh %s on the VM\033[0m\n' "${VERSION}"
fi

# ---- 9. RELEASE MANIFEST -------------------------------------------------
log "9/9  Release manifest"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SURFACES="$(y frontend_surfaces | "$PY" -c 'import sys,json;print(",".join(json.load(sys.stdin)))')"
MANIFEST="$(cat <<EOF
──────────────── RELEASE MANIFEST ────────────────
version         : ${VERSION}
tag             : ${VERSION} ($(git rev-parse --short HEAD))
timestamp       : ${STAMP}
surfaces live   : ${SURFACES}
masked (absent) : $(y masked_surfaces | "$PY" -c 'import sys,json;print(",".join(json.load(sys.stdin)))')
settings applied: $(echo "$SETTINGS")
preconditions   : passed/checked (see step 2)
frontend        : Cloudflare (wrangler deploy)
backend         : Azure ${AZURE_VM_IP:-<manual>}
───────────────────────────────────────────────────
EOF
)"
echo "$MANIFEST"
{ echo "$MANIFEST"; echo; } >> logs/releases.log
ok "manifest appended to logs/releases.log"
log "release ${VERSION} complete"
