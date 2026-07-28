# Firewall & Network Exposure — RunPod GPU VM

**Principle:** exactly one port is public — **443** (plus **80** only for the ACME
HTTP-01 challenge + redirect to HTTPS). Everything else is internal to the Docker
`visentix` network or bound to loopback. Postgres is managed Supabase (off-VM) and
is never run or exposed here. Ollama is GPU-internal and never published.

## Public vs internal

| Port | Service | Exposure | Notes |
|---|---|---|---|
| 443/tcp, 443/udp | Caddy (TLS) | **PUBLIC** | The only app entry point. HTTP/3 on udp. |
| 80/tcp | Caddy (ACME) | **PUBLIC** | Cert issuance + 308→https only; no app traffic served. |
| 22/tcp | sshd | restricted | **Key-only** (`PasswordAuthentication no`); ideally source-IP allow-listed. |
| 8000/tcp | api (uvicorn) | **internal only** | Reachable as `api:8000` on the compose network. NOT host-published. |
| 11434/tcp | ollama | **internal only** | `ollama:11434`; NOT host-published; GPU-backed. |
| 5432/tcp | Postgres | **n/a (off-VM)** | Managed Supabase; reached outbound over TLS via `DATABASE_URL`. Never listens on the VM. |

The compose file publishes **only** Caddy's `80`/`443`. `api` and `ollama` have no
`ports:` mapping — Docker keeps them on the private bridge, so they are unreachable
from the internet even though they listen inside their containers.

## Host firewall (defense in depth, in case a future service adds a `ports:` map)

RunPod exposes ports via its own port-mapping UI/proxy — expose **only 443 (and 80)**
there. On the VM, add ufw as a second layer:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing        # outbound needed for Supabase, HF, ACME, rclone
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw allow 80/tcp                  # ACME only
sudo ufw allow from <YOUR_IP> to any port 22 proto tcp   # SSH, ideally IP-scoped
sudo ufw enable
```

> Note: Docker can bypass ufw by writing iptables DNAT rules directly — but only for
> ports it actually publishes. Since we publish only 80/443, there is nothing for it
> to punch through for 8000/11434. Keep it that way.

## SSH: key-only

```bash
# /etc/ssh/sshd_config (or a drop-in in /etc/ssh/sshd_config.d/)
PasswordAuthentication no
PermitRootLogin prohibit-password
ChallengeResponseAuthentication no
sudo systemctl restart ssh
```

## rclone (for backups)

```bash
curl https://rclone.org/install.sh | sudo bash
# configure an S3-compatible remote, then export it into .env:
base64 -w0 ~/.config/rclone/rclone.conf   # → paste into RCLONE_CONFIG_BASE64
```

## Verification (also run automatically by deploy_runpod.sh step 7)

From an **external** host — never from the VM itself (localhost sees everything):

```bash
nmap -Pn -p 22,80,443,5432,8000,11434 <VM_PUBLIC_IP>
```

**PASS** = only `80/tcp` + `443/tcp` (+ `443/udp`) open; `22` filtered/allow-listed;
`8000`, `11434`, `5432` **closed/filtered**. Any of the latter three showing `open`
is a launch blocker — record the scan output in `LAUNCH-READINESS-v2.md`.
