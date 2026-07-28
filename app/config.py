"""Typed application settings — all values from .env, zero hardcoded secrets."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = Field(default="development")
    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )

    # Renderer: "weasyprint" (default) or "playwright" (requires Chromium installed)
    renderer: str = Field(default="weasyprint")

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str = Field(default="")
    database_url: str = Field(default="")

    # Local LLM
    ollama_base_url: str = Field(default="http://localhost:11434")
    qwen_local_model: str = Field(default="qwen3:8b")

    # Embeddings
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")

    # Hosted Qwen (wired in Phase 5)
    hosted_qwen_base_url: str = Field(default="")
    hosted_qwen_api_key: str = Field(default="")
    hosted_qwen_model: str = Field(default="")

    # Versioning metadata (VICBNF v2 quintet — stamped on every score/finding)
    scoring_model_version: str = Field(default="vicbnf-2.0.0")
    source_corpus_version: str = Field(default="corpus-2026Q2")

    # Live enforcement correlation (F-004) — requires embeddings to be available
    enable_live_f004: bool = Field(default=False)

    # External data-source APIs (ingest scripts)
    govinfo_api_key: str = Field(default="")
    courtlistener_token: str = Field(default="")
    openstates_api_key: str = Field(default="")

    # Admin
    admin_email: str = Field(default="")

    # F07 scheduler — in-process APScheduler. OFF by default so tests / import
    # never start it; the real server sets SCHEDULER_ENABLED=true.
    scheduler_enabled: bool = Field(default=False)
    database_pooler_url: str = Field(default="")  # IPv4 pooler — APScheduler jobstore

    # F07 alert delivery (email/webhook). No secrets hardcoded; unset = no send.
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_pass: str = Field(default="")
    smtp_from: str = Field(default="alerts@visentix.local")
    public_base_url: str = Field(default="https://app.visentix.local")

    # Ingestion connector framework (F02) — global politeness delay (seconds)
    # between per-item work in a run. 0 in tests; set >0 in prod to be a good citizen.
    ingestion_politeness_seconds: float = Field(default=0.0)

    # SEC EDGAR bulk-import root (full submissions + companyfacts already on disk).
    # The sec_edgar connector reads LOCAL files here; it is a batch importer, not a crawler.
    edgar_bulk_path: str = Field(default="")

    # Princeton-Leuven curated privacy-policy CSVs (per-sector), produced offline.
    # The princeton_leuven connector reads LOCAL CSVs here (domain,category,last_updated,policy_text).
    princeton_extract_dir: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
