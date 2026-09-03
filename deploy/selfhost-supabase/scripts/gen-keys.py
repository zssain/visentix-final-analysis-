#!/usr/bin/env python3
"""Generate the shared secret + the anon / service_role API keys for a self-hosted
Supabase stack.

Self-hosted Supabase is HS256: GoTrue, PostgREST and Storage all verify JWTs with
one shared JWT_SECRET, and the anon / service_role keys are themselves long-lived
JWTs signed with that same secret. The Visentix app is already compatible — its
token verifier falls back to HS256 with `supabase_jwt_secret` (app/auth.py).

Run:  python3 gen-keys.py
Copy the three printed values into deploy/selfhost-supabase/.env.

Uses only PyJWT (already a project dependency). No network, deterministic-free.
"""
from __future__ import annotations

import secrets
import jwt  # PyJWT

# 10-year lifetime for the anon/service keys (matches Supabase's own self-host demo).
IAT = 1_700_000_000          # fixed, pre-2024 epoch — value is irrelevant, avoids clock reads
EXP = IAT + 10 * 365 * 24 * 3600


def mint(secret: str, role: str) -> str:
    return jwt.encode(
        {"role": role, "iss": "supabase", "iat": IAT, "exp": EXP},
        secret,
        algorithm="HS256",
    )


def main() -> None:
    jwt_secret = secrets.token_urlsafe(48)          # >= 40 chars, required by GoTrue
    postgres_password = secrets.token_urlsafe(24)
    anon_key = mint(jwt_secret, "anon")
    service_key = mint(jwt_secret, "service_role")

    print("# ---- paste into deploy/selfhost-supabase/.env ----")
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print(f"JWT_SECRET={jwt_secret}")
    print(f"ANON_KEY={anon_key}")
    print(f"SERVICE_ROLE_KEY={service_key}")
    print()
    print("# ---- and into the Visentix app .env (deploy/azure/.env on the VM) ----")
    print("SUPABASE_URL=http://kong:8000")
    print(f"SUPABASE_ANON_KEY={anon_key}")
    print(f"SUPABASE_SERVICE_ROLE_KEY={service_key}")
    print(f"SUPABASE_JWT_SECRET={jwt_secret}")


if __name__ == "__main__":
    main()
