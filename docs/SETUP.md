# Visentix MVP — Local Development Setup

## Prerequisites

- **macOS** (Apple Silicon tested)
- **Python 3.13+** (`brew install python@3.13`)
- **Node.js 20+** / npm (`brew install node` — React app will be scaffolded in Phase 2)
- **Ollama** (`brew install ollama`)

## 1. Clone and configure secrets

```bash
cp .env.example .env
# Edit .env with your real Supabase credentials and API keys
```

## 2. Python virtual environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Ollama + Qwen3

```bash
# Start the Ollama service (runs in background)
brew services start ollama

# Pull the project's local LLM
ollama pull qwen3:8b

# Verify it responds
curl http://localhost:11434/api/version
```

## 4. Embedding model

The first import of `sentence-transformers/all-MiniLM-L6-v2` downloads the
model (~80 MB) to `~/.cache/huggingface/`. Verify it works:

```bash
source .venv/bin/activate
python -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
v = m.encode('test')
assert len(v) == 384, f'Expected 384 dims, got {len(v)}'
print('OK: 384-dim embedding confirmed')
"
```

## 5. Run the API server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 6. Health check

```bash
curl http://127.0.0.1:8000/health | python -m json.tool
```

Expected output: live row counts for all 13 tables + `"ollama": "ok"`.

## Environment variables

| Variable                  | Required | Description                          |
|---------------------------|----------|--------------------------------------|
| SUPABASE_URL              | Yes      | Supabase project URL                 |
| SUPABASE_ANON_KEY         | Yes      | Public/anon key (used by clients)    |
| SUPABASE_SERVICE_ROLE_KEY | Yes      | Service-role key (server-side only)  |
| DATABASE_URL              | Yes      | Postgres connection string           |
| OLLAMA_BASE_URL           | No       | Defaults to http://localhost:11434   |
| QWEN_LOCAL_MODEL          | No       | Defaults to qwen3:8b                 |
| EMBEDDING_MODEL           | No       | Defaults to all-MiniLM-L6-v2        |
| HOSTED_QWEN_BASE_URL      | Later    | Wired in Phase 5                     |
| HOSTED_QWEN_API_KEY        | Later    | Wired in Phase 5                     |
| HOSTED_QWEN_MODEL          | Later    | Wired in Phase 5                     |
| APP_ENV                   | No       | development (default) or production  |
