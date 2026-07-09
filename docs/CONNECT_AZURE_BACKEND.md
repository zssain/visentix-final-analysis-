# Connecting Visentix Frontend (Cloudflare Pages) to Azure Backend

This guide outlines how to deploy the FastAPI backend to Microsoft Azure and configure the React + Vite frontend on Cloudflare Pages to connect to it.

---

## 1. Deploying the FastAPI Backend to Azure

You can deploy the FastAPI application to **Azure App Service** (Linux) or **Azure Container Apps**.

### Option A: Azure App Service (Code Deployment)
1. **Create an Azure App Service**:
   - Choose **Python 3.13** as the runtime stack.
   - Choose **Linux** as the Operating System.
2. **Configure the Startup Command**:
   - FastAPI requires an ASGI server like `uvicorn` to run.
   - In the Azure Portal, go to **Settings > Configuration > General settings**.
   - Under **Startup Command**, enter:
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port 8000
     ```
     *(Azure App Service will map incoming HTTPS requests on ports 80/443 to the port your application exposes).*

### Option B: Azure Container Apps (Docker Deployment)
1. **Create a Dockerfile** in the repository root:
   ```dockerfile
   FROM python:3.13-slim
   WORKDIR /workspace
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 8000
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```
2. **Deploy to Azure Container Apps**:
   - Build the image and push to Azure Container Registry (ACR).
   - Create a Container App pulling from ACR.
   - Enable Ingress, set to **External**, and set target port to `8000`.

---

## 2. Configuring Backend Environment Variables on Azure

In your Azure App Service or Container App, you must set the environment variables that Visentix relies on. Go to **Settings > Configuration > Application settings** (or the Environment Variables section in Container Apps) and add:

| Key | Example Value | Purpose / Description |
|---|---|---|
| `APP_ENV` | `production` | Enables production mode logs, settings, and disables interactive `/docs` API endpoints. |
| `CORS_ALLOWED_ORIGINS` | `https://visentix-v2.pages.dev` | **CRITICAL:** Allows the Cloudflare Pages frontend origin to access the API. Separate multiple origins with commas. |
| `DATABASE_URL` | `postgresql://...` | Connection string to your production Postgres database (e.g., Azure DB for PostgreSQL or Supabase DB). |
| `SUPABASE_URL` | `https://your-proj.supabase.co` | The URL of your Supabase instance. |
| `SUPABASE_ANON_KEY` | `eyJhbGci...` | The Supabase client public anon key. |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGci...` | **Server-side only** service role key for database security bypasses. |
| `SUPABASE_JWT_SECRET` | `YOUR_JWT_SECRET` | Used to sign and verify local JWT sessions. |
| `HOSTED_QWEN_BASE_URL` | `https://api.your-provider.com/v1` | Base endpoint of your cloud LLM inference provider. |
| `HOSTED_QWEN_API_KEY` | `sk-...` | API Key for hosted Qwen or similar inference provider. |
| `HOSTED_QWEN_MODEL` | `Qwen/Qwen3-8B-Instruct` | Model identifier to use. |

---

## 3. Configuring and Redeploying the Frontend (Cloudflare Pages)

Since Vite bundles environment variables prefixed with `VITE_` at **build time**, you must configure and build the frontend pointing to the Azure API URL.

### Method A: Direct Command Line Deployment
1. Update `web/.env` with your Azure backend URL:
   ```env
   VITE_SUPABASE_URL=https://jhzkyfitrdxmzyyvqfak.supabase.co
   VITE_SUPABASE_ANON_KEY=sb_publishable_vhotPSk88CbSeCenLPQRKw_AfHl9HZ-
   VITE_API_BASE_URL=https://<your-azure-app>.azurewebsites.net
   ```
2. Build the project inside the `web` folder:
   ```bash
   cd web
   npm run build
   ```
3. Deploy the compiled assets to Cloudflare Pages:
   ```bash
   npx wrangler pages deploy dist --project-name=visentix-v2
   ```

### Method B: Git-Integrated CI/CD Builds (Recommended)
If you have linked your Git repository to Cloudflare Pages for automatic deployments:
1. In the **Cloudflare Dashboard**, navigate to **Workers & Pages > visentix-v2 > Settings > Environment variables**.
2. Add a new variable under **Production**:
   - **Variable name**: `VITE_API_BASE_URL`
   - **Value**: `https://<your-azure-app>.azurewebsites.net`
3. Trigger a redeployment in Cloudflare Pages. The build server will read this environment variable and embed the correct API URL into the built JavaScript bundles.
