#!/bin/sh
# Ollama entrypoint: start the server, then pull the PINNED model(s) once.
# Idempotent — `ollama pull` is a no-op if the model is already present in the
# ollama-models volume.
#
# Pinned models:
#   - ${QWEN_LOCAL_MODEL} (default qwen3:8b) — the classification/rephrase LLM.
# The embedding model (all-MiniLM-L6-v2) is NOT pulled here: it is a
# sentence-transformers model loaded in-process by the api container, cached in
# the hf-cache volume (see docker-compose.prod.yml + app/services/embeddings.py).
set -eu

MODEL="${QWEN_LOCAL_MODEL:-qwen3:8b}"

# Start the server in the background.
/bin/ollama serve &
OLLAMA_PID=$!

# Wait for the API to accept connections.
echo "ollama: waiting for server..."
until ollama list >/dev/null 2>&1; do
  sleep 2
done

echo "ollama: pulling pinned model ${MODEL} (no-op if cached)..."
ollama pull "${MODEL}"
echo "ollama: model ${MODEL} ready."

# Hand the container's lifetime to the server process.
wait "${OLLAMA_PID}"
