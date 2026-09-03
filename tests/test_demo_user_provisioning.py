"""Safety contracts for the explicit internal-demo provisioning utility."""

import inspect

import pytest

from scripts.db.provision_demo_users import _normalize_emails, main


def test_email_input_is_normalized_deduplicated_and_explicit():
    assert _normalize_emails([
        " Demo@Example.com ",
        "demo@example.com",
        "second@example.com",
    ]) == ["demo@example.com", "second@example.com"]
    with pytest.raises(ValueError):
        _normalize_emails([])
    with pytest.raises(ValueError):
        _normalize_emails(["not-an-email"])


def test_secret_is_prompted_and_not_a_cli_argument():
    source = inspect.getsource(main)
    assert "getpass.getpass" in source
    assert 'add_argument("--password"' not in source
