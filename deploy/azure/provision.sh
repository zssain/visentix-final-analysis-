#!/usr/bin/env bash
# =============================================================================
# deploy/azure/provision.sh — one-time (idempotent) host prep for the Azure VM.
#
#   sudo TAILSCALE_AUTHKEY=tskey-... ./provision.sh
#
# Brings a bare Ubuntu 24.04 VM to a state ready for deploy.sh:
#   1. Docker CE + compose plugin
#   2. A swap file (safety headroom for the in-process embedding model on 4 GB)
#   3. Tailscale installed + joined to the tailnet (reaches the private RunPod pod)
#   4. ufw: default-deny inbound, allow ONLY 22/80/443 + the tailnet interface
#   5. sshd hardening check — refuses to finish if password auth is enabled
#
# Re-runnable: every step is a no-op when already satisfied. Nothing here needs
# the full .env (that gate lives in deploy.sh); only TAILSCALE_AUTHKEY is required.
# =============================================================================
set -euo pipefail

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root (sudo)"

# ---- 1. Docker CE + compose plugin --------------------------------------
log "1/5  Docker + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi
docker compose version >/dev/null 2>&1 || die "docker compose plugin missing"
# let the login user drive docker without sudo
id azureuser >/dev/null 2>&1 && usermod -aG docker azureuser || true
ok "docker $(docker --version | awk '{print $3}' | tr -d ,) + compose plugin"

# ---- 2. swap file (2 GiB) -----------------------------------------------
log "2/5  Swap file (headroom for the embedding model on 4 GB RAM)"
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
ok "swap: $(free -h | awk '/Swap:/{print $2}')"

# ---- 3. Tailscale --------------------------------------------------------
log "3/5  Tailscale (join the private tailnet)"
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
systemctl enable --now tailscaled
if ! tailscale status >/dev/null 2>&1; then
  [[ -n "${TAILSCALE_AUTHKEY:-}" ]] || die "TAILSCALE_AUTHKEY not set — pass it in the environment"
  tailscale up --authkey="${TAILSCALE_AUTHKEY}" --hostname=visentix-azure --ssh
fi
TSIP="$(tailscale ip -4 2>/dev/null | head -1 || echo '?')"
ok "tailnet IP: ${TSIP}"

# ---- 4. ufw firewall -----------------------------------------------------
log "4/5  ufw — default-deny inbound; allow only 22/80/443 + tailnet"
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     comment 'SSH'
ufw allow 80/tcp     comment 'HTTP (ACME + redirect)'
ufw allow 443/tcp    comment 'HTTPS (Caddy)'
ufw allow in on tailscale0 comment 'tailnet'
ufw --force enable
ok "ufw active; open: 22, 80, 443, tailscale0"

# ---- 5. sshd hardening check --------------------------------------------
log "5/5  sshd — must be key-only"
if grep -RqsiE '^\s*PasswordAuthentication\s+yes' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null; then
  die "sshd PasswordAuthentication is ENABLED — set it to 'no' and restart sshd"
fi
ok "sshd password auth disabled (key-only)"

log "provision complete — ready for deploy.sh"
echo "  tailnet IP : ${TSIP}"
echo "  docker     : $(docker --version | awk '{print $3}' | tr -d ,)"
echo "  next       : copy .env to the repo, then run deploy/azure/deploy.sh <tag>"
