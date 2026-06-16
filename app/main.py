import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_ANON_KEY"]
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

CORE_TABLES = [
    "organization",
    "source_record",
    "privacy_notice",
    "notice_section",
    "disclosure_clause",
    "obligation",
    "enforcement_record",
    "regulator",
    "litigation_event",
    "monitoring_event",
    "formula_version",
    "benchmark_membership",
    "derived_data_item",
]

app = FastAPI(title="Visentix MVP", version="0.1.0")


@app.get("/health")
async def health():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact",
    }

    row_counts = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for table in CORE_TABLES:
            try:
                r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=0",
                    headers=headers,
                )
                content_range = r.headers.get("content-range", "*/0")
                total = content_range.split("/")[-1]
                row_counts[table] = int(total) if total.isdigit() else 0
            except Exception:
                row_counts[table] = "error"

        ollama_status = "down"
        try:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            if r.status_code == 200:
                ollama_status = "ok"
        except Exception:
            pass

    return {
        "status": "healthy",
        "row_counts": row_counts,
        "ollama": ollama_status,
    }
