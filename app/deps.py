"""Request-scoped FastAPI dependencies."""

from app.config import Settings, settings


def get_settings() -> Settings:
    """Inject the shared settings instance into route handlers."""
    return settings
