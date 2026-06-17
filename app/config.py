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
    cors_allowed_origins: str = Field(default="http://localhost:5173")

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

    # Admin
    admin_email: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
