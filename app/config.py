"""Typed application settings — all values from .env, zero hardcoded secrets."""

from pydantic import Field, SecretStr
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

    # SEC-005: only honor X-Forwarded-For for rate-limit keying when we sit behind
    # a TRUSTED reverse proxy. Default False — the header is client-controlled and
    # spoofable, so an untrusted deployment must key on the real peer IP.
    trusted_proxy: bool = Field(default=False)

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

    # ── LLM provider selection ───────────────────────────────────────────────
    # Explicit provider switch. Empty = auto (back-compat): runpod_serverless if a
    # RunPod endpoint is set, else hosted_ollama if HOSTED_QWEN_BASE_URL is set,
    # else local. Resolved by `effective_llm_backend`. Valid explicit values:
    #   "local"             — dev: localhost Ollama (OLLAMA_BASE_URL)
    #   "hosted_ollama"     — legacy: always-on Ollama on a RunPod Pod (Tailscale)
    #   "runpod_serverless" — RunPod Serverless, scale-to-zero (production target)
    llm_backend: str = Field(default="")

    # Hosted Qwen — LEGACY always-on RunPod Pod (Ollama over the tailnet). Kept for
    # back-compat + rollback; production moves to runpod_serverless below.
    hosted_qwen_base_url: str = Field(default="")
    hosted_qwen_api_key: str = Field(default="")
    hosted_qwen_model: str = Field(default="")

    # ── RunPod Serverless (scale-to-zero) — production LLM compute ────────────
    # The Azure backend authenticates TO RunPod with RUNPOD_API_KEY (a SecretStr so
    # it never prints in logs/repr). NEVER exposed to the frontend. See
    # deploy/runpod/serverless/ + deploy/runpod/README.md.
    runpod_endpoint_id: str = Field(default="")
    runpod_api_key: SecretStr = Field(default=SecretStr(""))
    runpod_serverless_base_url: str = Field(default="https://api.runpod.ai/v2")
    # Overall per-inference budget (covers cold start + model load + generation).
    runpod_serverless_timeout_seconds: float = Field(default=180.0)
    runpod_serverless_max_retries: int = Field(default=3)

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

    # SEC-009 — server-side pepper for partner API-key hashing (HMAC-SHA256).
    # When set, new keys are stored as HMAC(pepper, plaintext); verify still
    # accepts legacy unsalted sha256 for migration. Empty = legacy sha256 (dev).
    partner_key_pepper: str = Field(default="")

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
    def effective_llm_backend(self) -> str:
        """Resolve the active LLM provider. Explicit LLM_BACKEND wins; otherwise
        auto-detect for back-compat (never silently changes an existing deploy)."""
        if self.llm_backend:
            return self.llm_backend
        if self.runpod_endpoint_id:
            return "runpod_serverless"
        if self.hosted_qwen_base_url:
            return "hosted_ollama"
        return "local"

    @property
    def llm_model_name(self) -> str:
        """Model tag used for hosted/serverless inference (falls back to the local
        model tag so a single deploy needn't set two model vars)."""
        return self.hosted_qwen_model or self.qwen_local_model

    def validate_llm_backend(self) -> None:
        """Fail fast on misconfiguration — WITHOUT any network/inference call.

        Called at app startup. Only checks that required config is syntactically
        present for the selected provider; it NEVER contacts RunPod/Ollama (which
        would wake a serverless worker and defeat scale-to-zero)."""
        backend = self.effective_llm_backend
        if backend == "runpod_serverless":
            missing = []
            if not self.runpod_endpoint_id:
                missing.append("RUNPOD_ENDPOINT_ID")
            if not self.runpod_api_key.get_secret_value():
                missing.append("RUNPOD_API_KEY")
            if missing:
                raise ValueError(
                    f"LLM_BACKEND=runpod_serverless but missing required config: "
                    f"{', '.join(missing)}. Set them in the backend .env (never the frontend)."
                )
        elif backend == "hosted_ollama":
            if not self.hosted_qwen_base_url:
                raise ValueError("LLM_BACKEND=hosted_ollama but HOSTED_QWEN_BASE_URL is empty.")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
