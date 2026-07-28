"""Pytest configuration — CI-safe skipping of tests that need external services.

Local dev (real Supabase creds + sentence-transformers installed) runs the FULL
suite. CI (dummy creds, no torch) auto-skips the two classes of tests that
cannot run without those services — detected by probe, so no env flag or marker
maintenance is required:

  * live-Supabase tests   — modules that make real REST/DB calls (not mocked).
  * ML-embedding tests    — modules that import sentence-transformers/torch.

The CI-vs-local gap is documented in .github/workflows/ci.yml. These modules
still run locally before merge; CI is the fast sanity gate (backend unit tests
that mock the DB + frontend tsc/vitest), targeted < 5 min.
"""

import importlib.util
import socket
import urllib.parse

import pytest

# Modules whose tests make real Supabase/REST calls (no mock) → need a reachable
# live DB. (Some already self-skip via their own _require(); listed here so CI
# skips them explicitly and fast, without network retries.)
_LIVE_DB_MODULES = {
    "test_review_gate", "test_training_labels", "test_products",
    "test_persistence_hardening", "test_schema_p1", "test_embeddings",
    "test_f002_f007", "test_normalization", "test_org_profile",
    "test_profile", "test_f02_ingestion_foundation",
    "test_app_boot", "test_auth", "test_live_classify",
}

# Modules that import sentence-transformers / torch at runtime.
_ML_MODULES = {"test_f004_enforcement", "test_embeddings"}


def _supabase_reachable() -> bool:
    """Best-effort TCP probe to the configured Supabase host (port 443)."""
    try:
        from app.config import settings
        host = urllib.parse.urlparse(settings.supabase_url).hostname
        if not host:
            return False
        with socket.create_connection((host, 443), timeout=3):
            return True
    except Exception:
        return False


def _sentence_transformers_available() -> bool:
    try:
        return importlib.util.find_spec("sentence_transformers") is not None
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    db_ok = _supabase_reachable()
    st_ok = _sentence_transformers_available()
    if db_ok and st_ok:
        return  # local dev with everything available → run the full suite
    skip_db = pytest.mark.skip(reason="needs live Supabase (unreachable — CI); runs locally")
    skip_ml = pytest.mark.skip(reason="needs sentence-transformers/torch (not installed — CI); runs locally")
    for item in items:
        mod = item.module.__name__.rsplit(".", 1)[-1]
        if not db_ok and mod in _LIVE_DB_MODULES:
            item.add_marker(skip_db)
        elif not st_ok and mod in _ML_MODULES:
            item.add_marker(skip_ml)
