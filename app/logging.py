"""Structured logging setup.

Rules (AGENTS.md §3):
- NEVER log secrets, full notice text, or connection strings.
- Log that text was sent to a model, never the text itself.
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"

# Patterns that must never appear in log output
_REDACT_PREFIXES = ("sb_", "eyJ", "sk-", "postgresql://")


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with structured format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def safe_log_value(value: str, max_len: int = 40) -> str:
    """Redact a value if it looks like a secret."""
    if any(value.startswith(p) for p in _REDACT_PREFIXES):
        return "***REDACTED***"
    if len(value) > max_len:
        return value[:max_len] + "…"
    return value
