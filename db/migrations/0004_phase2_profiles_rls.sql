-- Migration 0004: Phase 2 — Profiles table, role enum, and RLS policies
-- Applied: 2026-06-17
-- Additive only. Idempotent.

-- ============================================================
-- 1. Role enum type
-- ============================================================
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('customer', 'sme', 'admin');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- 2. Profiles table (links to auth.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS profiles (
    user_id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role            user_role NOT NULL DEFAULT 'customer',
    display_name    TEXT,
    organization_id UUID,  -- links customer to their org
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profiles_role ON profiles(role);
CREATE INDEX IF NOT EXISTS idx_profiles_org ON profiles(organization_id);

-- ============================================================
-- 3. Auto-create profile on signup (trigger)
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (user_id, role, display_name)
    VALUES (NEW.id, 'customer', NEW.raw_user_meta_data ->> 'display_name')
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- 4. RLS on profiles
-- ============================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
CREATE POLICY "Users can read own profile" ON profiles
    FOR SELECT USING (
        auth.uid() = user_id
        OR EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid() AND p.role IN ('sme', 'admin')
        )
    );

-- ============================================================
-- 5. RLS on risk_finding (customer sees own org only)
-- ============================================================
ALTER TABLE risk_finding ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Customer sees own org findings" ON risk_finding;
CREATE POLICY "Customer sees own org findings" ON risk_finding
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = risk_finding.organization_id
            )
        )
    );

-- ============================================================
-- 6. RLS on report_snapshot
-- ============================================================
ALTER TABLE report_snapshot ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Customer sees own org snapshots" ON report_snapshot;
CREATE POLICY "Customer sees own org snapshots" ON report_snapshot
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = report_snapshot.organization_id
            )
        )
    );

-- ============================================================
-- 7. RLS on derived_data_item
-- ============================================================
ALTER TABLE derived_data_item ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Customer sees own org derived data" ON derived_data_item;
CREATE POLICY "Customer sees own org derived data" ON derived_data_item
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = derived_data_item.organization_id
            )
        )
    );

-- ============================================================
-- 8. RLS on organization_intelligence_profile
-- ============================================================
ALTER TABLE organization_intelligence_profile ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Customer sees own org intel profile" ON organization_intelligence_profile;
CREATE POLICY "Customer sees own org intel profile" ON organization_intelligence_profile
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = organization_intelligence_profile.organization_id
            )
        )
    );
