"""
Manage local auth users stored in local_users.json.

Usage:
    python scripts/setup_local_auth.py            # seed default users
    python scripts/setup_local_auth.py add <email> <password> <role>
"""

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

USERS_FILE = Path(__file__).parent.parent / "local_users.json"

DEFAULT_USERS = [
    ("admin@visentix.com",    "VisentixDemo2026!", "admin"),
    ("sme@visentix.com",      "VisentixDemo2026!", "sme"),
    ("customer@visentix.com", "VisentixDemo2026!", "customer"),
]


def hash_password(password: str) -> tuple[str, str]:
    salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return salt, hashed


def load() -> list[dict]:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []


def save(users: list[dict]) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2))


def upsert(users: list[dict], email: str, password: str, role: str) -> None:
    salt, pw_hash = hash_password(password)
    existing = next((u for u in users if u["email"] == email), None)
    if existing:
        existing["password_hash"] = pw_hash
        existing["salt"] = salt
        existing["role"] = role
        print(f"  updated  {role:10s}  {email}")
    else:
        users.append({
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": pw_hash,
            "salt": salt,
            "role": role,
            "organization_id": None,
        })
        print(f"  added    {role:10s}  {email}")


def main() -> None:
    users = load()

    if len(sys.argv) == 5 and sys.argv[1] == "add":
        _, _, email, password, role = sys.argv
        if role not in ("customer", "sme", "admin"):
            sys.exit("role must be customer | sme | admin")
        upsert(users, email, password, role)
    else:
        print("Seeding default users into local_users.json…")
        for email, password, role in DEFAULT_USERS:
            upsert(users, email, password, role)

    save(users)
    print(f"\nSaved {len(users)} user(s) to {USERS_FILE}")


if __name__ == "__main__":
    main()
