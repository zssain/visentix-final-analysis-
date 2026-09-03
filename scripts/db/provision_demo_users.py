#!/usr/bin/env python3
"""Idempotently provision explicitly named internal-demo users in Supabase.

The shared password is accepted only through a non-echoing prompt. It is never
accepted as a command-line argument, written to disk, or printed. This script
creates/updates only the emails explicitly supplied with ``--email``.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
DEMO_NAME = "Visentix Demo"
DEMO_SLUG = "visentix-demo"


def _settings() -> tuple[str, str]:
    env = dotenv_values(ROOT / ".env")
    url = str(env.get("SUPABASE_URL") or "").rstrip("/")
    service_key = str(env.get("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not url or not service_key:
        raise RuntimeError("Supabase server settings are not configured")
    return url, service_key


def _headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def _normalize_emails(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("every --email value must be a valid email address")
        if email not in out:
            out.append(email)
    if not out:
        raise ValueError("provide at least one --email")
    return out


def _ensure_workspace(client: httpx.Client, base_url: str, headers: dict[str, str]) -> str:
    response = client.get(
        f"{base_url}/rest/v1/organization",
        params={
            "select": "organization_id,name,slug,origin",
            "slug": f"eq.{DEMO_SLUG}",
            "limit": "1",
        },
        headers=headers,
    )
    if response.status_code != 200:
        raise RuntimeError(f"workspace lookup failed (HTTP {response.status_code})")
    rows = response.json()
    if rows:
        row = rows[0]
        if row.get("name") != DEMO_NAME or row.get("origin") != "internal_demo_workspace":
            raise RuntimeError("the reserved demo workspace slug belongs to another organization")
        return str(row["organization_id"])

    workspace_id = str(uuid4())
    created = client.post(
        f"{base_url}/rest/v1/organization",
        headers={**headers, "Prefer": "return=minimal"},
        json={
            "organization_id": workspace_id,
            "name": DEMO_NAME,
            "slug": DEMO_SLUG,
            "industry": "unknown",
            "entity_type": "internal_demo_workspace",
            "tenant_id": workspace_id,
            "origin": "internal_demo_workspace",
        },
    )
    if created.status_code >= 300:
        raise RuntimeError(f"workspace creation failed (HTTP {created.status_code})")
    return workspace_id


def _auth_users(client: httpx.Client, base_url: str, headers: dict[str, str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    page = 1
    while True:
        response = client.get(
            f"{base_url}/auth/v1/admin/users",
            params={"page": str(page), "per_page": "100"},
            headers=headers,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Auth user lookup failed (HTTP {response.status_code})")
        payload = response.json()
        users = payload.get("users", payload if isinstance(payload, list) else [])
        for user in users:
            email = str(user.get("email") or "").strip().lower()
            if email:
                found[email] = user
        if len(users) < 100:
            return found
        page += 1


def provision(emails: list[str], password: str) -> tuple[int, int]:
    if not password:
        raise ValueError("password cannot be blank")
    base_url, service_key = _settings()
    headers = _headers(service_key)
    created_count = 0
    updated_count = 0

    with httpx.Client(timeout=20) as client:
        workspace_id = _ensure_workspace(client, base_url, headers)
        existing = _auth_users(client, base_url, headers)

        for email in emails:
            user = existing.get(email)
            if user:
                user_id = str(user["id"])
                auth_response = client.put(
                    f"{base_url}/auth/v1/admin/users/{user_id}",
                    headers=headers,
                    json={"password": password, "email_confirm": True},
                )
                updated_count += 1
            else:
                auth_response = client.post(
                    f"{base_url}/auth/v1/admin/users",
                    headers=headers,
                    json={"email": email, "password": password, "email_confirm": True},
                )
                if auth_response.status_code >= 300:
                    raise RuntimeError(
                        f"Auth user creation failed for {email} (HTTP {auth_response.status_code})"
                    )
                user_id = str(auth_response.json().get("id") or "")
                created_count += 1

            if auth_response.status_code >= 300:
                raise RuntimeError(
                    f"Auth user update failed for {email} (HTTP {auth_response.status_code})"
                )
            if not user_id:
                raise RuntimeError(f"Auth did not return an id for {email}")

            profile = client.post(
                f"{base_url}/rest/v1/profiles",
                params={"on_conflict": "user_id"},
                headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json={
                    "user_id": user_id,
                    "role": "customer",
                    "display_name": email,
                    "organization_id": workspace_id,
                    "third_party_assessment_enabled": True,
                },
            )
            if profile.status_code >= 300:
                raise RuntimeError(
                    f"Profile provisioning failed for {email} (HTTP {profile.status_code})"
                )

    return created_count, updated_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", action="append", required=True)
    args = parser.parse_args()
    try:
        emails = _normalize_emails(args.email)
        password = getpass.getpass("Shared demo password: ")
        created, updated = provision(emails, password)
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        print(f"provision_demo_users: FAILED — {exc}", file=sys.stderr)
        return 1
    print(
        f"Provisioned {len(emails)} demo users in {DEMO_NAME}: "
        f"{created} created, {updated} updated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
