# Visentix RunPod Serverless worker — Ollama + qwen3:8b.
# Build for the RunPod GPU node architecture (linux/amd64):
#   docker buildx build --platform linux/amd64 -t <registry>/visentix-runpod-serverless:<tag> \
#       deploy/runpod/serverless --push
#
# The model weights are NOT baked in (they live on a RunPod Network Volume mounted
# at OLLAMA_MODELS — see deploy/runpod/README.md 'Model storage'). This keeps the
# image small and lets the worker start without re-downloading 5 GB every time.

# Pin to a tested Ollama version — do NOT float on :latest in production.
# Verify the tag exists and serves qwen3:8b before deploying.
ARG OLLAMA_VERSION=0.5.11
FROM ollama/ollama:${OLLAMA_VERSION}

# The base image's ENTRYPOINT is the ollama binary; our worker drives ollama itself.
ENTRYPOINT []

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install into an isolated venv. This avoids PEP 668 "externally-managed" errors
# and old-pip `--break-system-packages` incompatibilities across base-image
# variants (the ollama/ollama base ships a pip that rejects that flag).
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Build context is the REPO ROOT (RunPod's GitHub build + `docker build -f <this> .`),
# so paths are repo-root-relative. Only these two files are copied — no secrets,
# no app code, no .env.
COPY deploy/runpod/serverless/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY deploy/runpod/serverless/handler.py .

# Model weights persist on the mounted network volume, not the container disk.
ENV OLLAMA_MODELS=/runpod-volume/ollama \
    OLLAMA_HOST=127.0.0.1 \
    OLLAMA_MODEL=qwen3:8b \
    OLLAMA_URL=http://127.0.0.1:11434 \
    LOG_LEVEL=INFO
# NB: deliberately NO `OLLAMA_KEEP_ALIVE=-1` — RunPod must be free to scale to zero.

CMD ["python3", "handler.py"]
