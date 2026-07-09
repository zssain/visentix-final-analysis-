-- Migration 0011: Local auth users table (bypasses Supabase auth service)
-- Run once against your database.

CREATE TABLE IF NOT EXISTS local_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    salt            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'customer'
                        CHECK (role IN ('customer', 'sme', 'admin')),
    organization_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_local_users_email ON local_users(email);
