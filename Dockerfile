FROM python:3.13-slim

WORKDIR /app

# System deps for WeasyPrint PDF rendering + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    libffi-dev libgdk-pixbuf-2.0-0 libcairo2 libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only torch: this VM has no GPU (model inference runs on the RunPod pod), so
# install the CPU build FIRST — sentence-transformers then reuses it instead of
# pulling the multi-GB CUDA/NVIDIA stack. Keeps the image ~3.5GB (vs ~9.5GB) so it
# builds within the VM's disk. See docs/remediation/DEPLOY-DONE.md.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config/ config/
# NB: local_users.json is intentionally NOT copied — demo credential hashes must
# never be baked into a client image (RLS-AUDIT §4). Provision users in prod via
# the DB (RLS-AUDIT §5 "C1b") or an Azure secret mount. With no users file the
# app still boots; every /auth/login simply returns 401 until users are provisioned.

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
