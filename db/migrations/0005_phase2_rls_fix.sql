-- Migration 0005: Fix RLS policies to handle NULL auth.uid() gracefully
-- When no JWT user is present (anon key), auth.uid() is NULL.
-- Policies must return false (deny) instead of erroring.

-- ============================================================
-- profiles
-- ============================================================
DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
CREATE POLICY "Users can read own profile" ON profiles
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            auth.uid() = user_id
            OR EXISTS (
                SELECT 1 FROM profiles p
                WHERE p.user_id = auth.uid() AND p.role IN ('sme', 'admin')
            )
        )
    );

-- ============================================================
-- risk_finding
-- ============================================================
DROP POLICY IF EXISTS "Customer sees own org findings" ON risk_finding;
CREATE POLICY "Customer sees own org findings" ON risk_finding
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = risk_finding.organization_id
            )
        )
    );

-- ============================================================
-- report_snapshot
-- ============================================================
DROP POLICY IF EXISTS "Customer sees own org snapshots" ON report_snapshot;
CREATE POLICY "Customer sees own org snapshots" ON report_snapshot
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = report_snapshot.organization_id
            )
        )
    );

-- ============================================================
-- derived_data_item
-- ============================================================
DROP POLICY IF EXISTS "Customer sees own org derived data" ON derived_data_item;
CREATE POLICY "Customer sees own org derived data" ON derived_data_item
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = derived_data_item.organization_id
            )
        )
    );

-- ============================================================
-- organization_intelligence_profile
-- ============================================================
DROP POLICY IF EXISTS "Customer sees own org intel profile" ON organization_intelligence_profile;
CREATE POLICY "Customer sees own org intel profile" ON organization_intelligence_profile
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND (
                p.role IN ('sme', 'admin')
                OR p.organization_id = organization_intelligence_profile.organization_id
            )
        )
    );
