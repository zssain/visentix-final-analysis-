# Visentix Azure Deployment Guide

Step-by-step guide to deploy the Visentix Privacy Intelligence Platform on Azure + Cloudflare, matching the Technical Architecture v2.0.

## Architecture Overview

```
User -> Cloudflare Pages (frontend) -> Azure Container Apps (FastAPI API)
                                            |
                                    Azure PostgreSQL (pgvector)
                                            |
                                    GPU Node (on-demand, Ollama/vLLM)
```

---

## Prerequisites

- Azure account with a subscription
- Cloudflare account (free tier works)
- GitHub repo: https://github.com/zssain/visentix-v2--MVP.git
- Azure CLI installed: `brew install azure-cli`
- Docker installed: `brew install --cask docker`
- Node.js 18+ and pnpm/npm

---

## Phase 1: Azure Setup (one-time)

### Step 1.1 — Login and create resource group

```bash
# Login to Azure
az login

# Set your subscription (replace with yours)
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Create a resource group (pick a region close to your users)
az group create --name visentix-rg --location eastus
```

### Step 1.2 — Create Azure PostgreSQL with pgvector

```bash
# Create PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group visentix-rg \
  --name visentix-db \
  --location eastus \
  --admin-user visentix_admin \
  --admin-password 'CHOOSE_A_STRONG_PASSWORD_HERE' \
  --sku-name Standard_B2ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --yes

# Allow Azure services to connect
az postgres flexible-server firewall-rule create \
  --resource-group visentix-rg \
  --name visentix-db \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Allow your current IP (for initial setup)
MY_IP=$(curl -s ifconfig.me)
az postgres flexible-server firewall-rule create \
  --resource-group visentix-rg \
  --name visentix-db \
  --rule-name AllowMyIP \
  --start-ip-address $MY_IP \
  --end-ip-address $MY_IP

# Enable pgvector extension
az postgres flexible-server parameter set \
  --resource-group visentix-rg \
  --server-name visentix-db \
  --name azure.extensions \
  --value vector
```

### Step 1.3 — Initialize the database

```bash
# Get your connection string
DB_HOST="visentix-db.postgres.database.azure.com"
DB_USER="visentix_admin"
DB_PASS="YOUR_PASSWORD"
DB_NAME="postgres"

# Connect and create extensions + run migrations
psql "host=$DB_HOST dbname=$DB_NAME user=$DB_USER password=$DB_PASS sslmode=require" << 'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL

# Run ALL migrations in order
for f in db/migrations/0001*.sql db/migrations/0002*.sql db/migrations/0003*.sql \
         db/migrations/0004*.sql db/migrations/0005*.sql db/migrations/0006*.sql \
         db/migrations/0007*.sql db/migrations/0008*.sql db/migrations/0009*.sql \
         db/migrations/0010*.sql db/migrations/0011_reference_corpus.sql \
         db/migrations/0012*.sql db/migrations/0013*.sql db/migrations/0014*.sql \
         db/migrations/0015*.sql db/migrations/0016*.sql db/migrations/0017*.sql \
         db/migrations/0018*.sql db/migrations/0019*.sql; do
  echo "Running $f..."
  psql "host=$DB_HOST dbname=$DB_NAME user=$DB_USER password=$DB_PASS sslmode=require" < "$f"
done
```

### Step 1.4 — Create Azure Container Registry

```bash
# Create container registry for Docker images
az acr create \
  --resource-group visentix-rg \
  --name visentixacr \
  --sku Basic \
  --admin-enabled true

# Get login credentials
az acr credential show --name visentixacr
# Note the username and password — you'll need them
```

---

## Phase 2: Dockerize the Backend

### Step 2.1 — Create Dockerfile

Create `Dockerfile` in the project root:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# System deps for WeasyPrint PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    libffi-dev libgdk-pixbuf2.0-0 libcairo2 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config/ config/
COPY local_users.json .

# Don't copy .env — secrets come from Azure env vars

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2.2 — Create .dockerignore

```
.venv/
node_modules/
web/
scripts/
tests/
docs/
*.pyc
__pycache__/
.env
.git/
```

### Step 2.3 — Build and push to Azure Container Registry

```bash
# Login to ACR
az acr login --name visentixacr

# Build and push
docker build -t visentixacr.azurecr.io/visentix-api:latest .
docker push visentixacr.azurecr.io/visentix-api:latest
```

---

## Phase 3: Deploy Backend on Azure Container Apps

### Step 3.1 — Create Container Apps Environment

```bash
# Create the environment
az containerapp env create \
  --name visentix-env \
  --resource-group visentix-rg \
  --location eastus
```

### Step 3.2 — Generate a JWT secret

```bash
# Generate a strong secret for JWT signing
JWT_SECRET=$(openssl rand -hex 32)
echo "JWT_SECRET: $JWT_SECRET"
# Save this — you'll need it for both backend and frontend
```

### Step 3.3 — Deploy the API container

```bash
# Get ACR credentials
ACR_USER=$(az acr credential show --name visentixacr --query username -o tsv)
ACR_PASS=$(az acr credential show --name visentixacr --query "passwords[0].value" -o tsv)

az containerapp create \
  --name visentix-api \
  --resource-group visentix-rg \
  --environment visentix-env \
  --image visentixacr.azurecr.io/visentix-api:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 2 \
  --memory 4Gi \
  --registry-server visentixacr.azurecr.io \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --env-vars \
    APP_ENV=production \
    SUPABASE_URL=https://visentix-db.postgres.database.azure.com \
    DATABASE_URL="host=visentix-db.postgres.database.azure.com dbname=postgres user=visentix_admin password=YOUR_PASSWORD sslmode=require" \
    SUPABASE_JWT_SECRET="$JWT_SECRET" \
    SUPABASE_SERVICE_ROLE_KEY="not-used-in-azure" \
    SUPABASE_ANON_KEY="not-used-in-azure" \
    CORS_ALLOWED_ORIGINS="https://visentix.pages.dev,https://yourdomain.com" \
    EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2" \
    HOSTED_QWEN_BASE_URL="" \
    HOSTED_QWEN_API_KEY="" \
    HOSTED_QWEN_MODEL=""
```

**IMPORTANT**: The current codebase uses Supabase PostgREST as the database client. For Azure PostgreSQL, you have two options:

**Option A (Quickest)**: Keep using Supabase as your database (it's already working) and just deploy the API container pointing to the same Supabase URL. No code changes needed.

**Option B (Production)**: Migrate from Supabase PostgREST to direct PostgreSQL queries using `psycopg` or `SQLAlchemy`. This requires rewriting `app/db.py` and all PostgREST calls.

**Recommendation for MVP**: Use Option A. Keep Supabase as your managed PostgreSQL + PostgREST layer. Deploy only the API container on Azure Container Apps.

### Step 3.3 (Option A — Keep Supabase) — Simplified deployment

```bash
az containerapp create \
  --name visentix-api \
  --resource-group visentix-rg \
  --environment visentix-env \
  --image visentixacr.azurecr.io/visentix-api:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 2 \
  --memory 4Gi \
  --registry-server visentixacr.azurecr.io \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --env-vars \
    APP_ENV=production \
    SUPABASE_URL="https://jhzkyfitrdxmzyyvqfak.supabase.co" \
    SUPABASE_ANON_KEY="YOUR_ANON_KEY" \
    SUPABASE_SERVICE_ROLE_KEY="YOUR_SERVICE_ROLE_KEY" \
    SUPABASE_JWT_SECRET="YOUR_JWT_SECRET" \
    CORS_ALLOWED_ORIGINS="https://visentix.pages.dev,https://yourdomain.com" \
    EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2" \
    OLLAMA_BASE_URL="http://your-gpu-endpoint:11434" \
    HOSTED_QWEN_BASE_URL="" \
    HOSTED_QWEN_API_KEY="" \
    HOSTED_QWEN_MODEL=""
```

### Step 3.4 — Get the API URL

```bash
az containerapp show \
  --name visentix-api \
  --resource-group visentix-rg \
  --query properties.configuration.ingress.fqdn \
  -o tsv
```

This gives you something like: `visentix-api.happyfield-abc123.eastus.azurecontainerapps.io`

### Step 3.5 — Verify

```bash
curl https://visentix-api.happyfield-abc123.eastus.azurecontainerapps.io/health
```

---

## Phase 4: Deploy Frontend on Cloudflare Pages

### Step 4.1 — Update the API base URL

Edit `web/.env.production` (create if it doesn't exist):

```env
VITE_API_BASE_URL=https://visentix-api.happyfield-abc123.eastus.azurecontainerapps.io
```

### Step 4.2 — Build the frontend

```bash
cd web
npm install
npm run build
# Output goes to web/dist/
```

### Step 4.3 — Deploy to Cloudflare Pages

**Option A — Via Cloudflare Dashboard (easiest):**

1. Go to https://dash.cloudflare.com
2. Click **Workers & Pages** > **Create**
3. Select **Pages** > **Connect to Git**
4. Select your GitHub repo: `zssain/visentix-v2--MVP`
5. Configure build settings:
   - **Build command**: `cd web && npm install && npm run build`
   - **Build output directory**: `web/dist`
   - **Root directory**: `/`
6. Add environment variable:
   - `VITE_API_BASE_URL` = `https://visentix-api.YOUR_DOMAIN.azurecontainerapps.io`
7. Click **Save and Deploy**

**Option B — Via Wrangler CLI:**

```bash
npm install -g wrangler
wrangler login

# Deploy
cd web
wrangler pages deploy dist --project-name visentix
```

### Step 4.4 — Set up custom domain (optional)

1. In Cloudflare Dashboard > Pages > visentix > Custom domains
2. Add `app.visentix.com` (or your domain)
3. Cloudflare auto-provisions TLS

---

## Phase 5: LLM / GPU Setup

The LLM is needed for clause classification. Three options for production:

### Option A — RunPod (cheapest, recommended for MVP)

1. Go to https://runpod.io
2. Create a GPU pod with:
   - Template: **RunPod Ollama**
   - GPU: **RTX 4090** or **A40** (24GB VRAM)
   - Expose port **11434**
3. SSH in and pull the model:
   ```bash
   ollama pull qwen3:8b
   ```
4. Update your Container App env var:
   ```bash
   az containerapp update \
     --name visentix-api \
     --resource-group visentix-rg \
     --set-env-vars OLLAMA_BASE_URL=https://YOUR_RUNPOD_ID-11434.proxy.runpod.net
   ```

### Option B — Azure GPU VM (enterprise)

```bash
# Create an NC-series VM with GPU
az vm create \
  --resource-group visentix-rg \
  --name visentix-gpu \
  --image Ubuntu2204 \
  --size Standard_NC4as_T4_v3 \
  --admin-username azureuser \
  --generate-ssh-keys

# SSH in and install Ollama
ssh azureuser@<VM_IP>
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
# Start Ollama listening on all interfaces
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Option C — No GPU (CPU-only, slower)

The platform works without a GPU — classification falls back to keyword matching. Scores will be less accurate but the pipeline still runs. Set `OLLAMA_BASE_URL=""` and `HOSTED_QWEN_BASE_URL=""`.

---

## Phase 6: DNS and Security

### Step 6.1 — Lock down the backend

The Azure Container App should only accept requests from Cloudflare. Add IP restrictions:

```bash
# Get Cloudflare IP ranges
curl -s https://www.cloudflare.com/ips-v4 > /tmp/cf_ips.txt

# In Azure Portal: Container Apps > visentix-api > Networking > IP Restrictions
# Add each Cloudflare IP range as "Allow"
# Set default action to "Deny"
```

### Step 6.2 — CORS configuration

Update the Container App env var to only allow your Cloudflare domain:

```bash
az containerapp update \
  --name visentix-api \
  --resource-group visentix-rg \
  --set-env-vars CORS_ALLOWED_ORIGINS="https://visentix.pages.dev,https://app.visentix.com"
```

---

## Phase 7: CI/CD (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Visentix

on:
  push:
    branches: [main]

jobs:
  deploy-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - uses: azure/docker-login@v2
        with:
          login-server: visentixacr.azurecr.io
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}

      - run: |
          docker build -t visentixacr.azurecr.io/visentix-api:${{ github.sha }} .
          docker push visentixacr.azurecr.io/visentix-api:${{ github.sha }}

      - run: |
          az containerapp update \
            --name visentix-api \
            --resource-group visentix-rg \
            --image visentixacr.azurecr.io/visentix-api:${{ github.sha }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20

      - run: cd web && npm ci && npm run build
        env:
          VITE_API_BASE_URL: ${{ secrets.API_URL }}

      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          command: pages deploy web/dist --project-name visentix
```

Add these GitHub secrets:
- `AZURE_CREDENTIALS` — from `az ad sp create-for-rbac`
- `ACR_USERNAME` / `ACR_PASSWORD` — from ACR credentials
- `CLOUDFLARE_API_TOKEN` — from Cloudflare dashboard
- `API_URL` — your Container App FQDN

---

## Cost Estimate (Monthly)

| Service | Spec | Cost |
|---------|------|------|
| Azure Container Apps | 2 vCPU, 4GB, 1 replica | ~$50/mo |
| Supabase (keep existing) | Free/Pro tier | $0–25/mo |
| Cloudflare Pages | Free tier | $0/mo |
| RunPod GPU (on-demand) | RTX 4090, ~10 hrs/mo | ~$5–15/mo |
| **Total** | | **~$55–90/mo** |

---

## Quick-Start Checklist

- [ ] Azure CLI installed and logged in
- [ ] Resource group created
- [ ] Container Registry created
- [ ] Docker image built and pushed
- [ ] Container App deployed and healthy
- [ ] Frontend built with production API URL
- [ ] Cloudflare Pages connected to GitHub
- [ ] Custom domain configured (optional)
- [ ] GPU endpoint configured (RunPod or Azure VM)
- [ ] CORS locked to Cloudflare domain only
- [ ] GitHub Actions CI/CD set up
- [ ] Test end-to-end: Intake -> Score -> Report -> PDF

---

## Troubleshooting

**API returns 502**: Check Container App logs: `az containerapp logs show --name visentix-api --resource-group visentix-rg`

**CORS errors**: Verify `CORS_ALLOWED_ORIGINS` includes your frontend domain with `https://`

**LLM classification all "other"**: Check `OLLAMA_BASE_URL` is reachable from the container. Test: `az containerapp exec --name visentix-api --resource-group visentix-rg -- curl $OLLAMA_BASE_URL/api/tags`

**Database connection errors**: Verify firewall rules allow Azure Container Apps. Check the Supabase dashboard for rate limits.
