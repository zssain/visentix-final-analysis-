-- Migration 0006: Fix infinite recursion in RLS policies
-- The profiles policy cannot query profiles itself.
-- Solution: use a SECURITY DEFINER helper function to check role,
-- bypassing RLS on the lookup.

-- ============================================================
-- Helper function (SECURITY DEFINER bypasses RLS for the lookup)
-- ============================================================
CREATE OR REPLACE FUNCTION public.get_my_role()
RETURNS TEXT AS $$
    SELECT role::TEXT FROM public.profiles WHERE user_id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- ============================================================
-- profiles — user reads own; sme/admin reads all
-- ============================================================
DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
CREATE POLICY "Users can read own profile" ON profiles
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            auth.uid() = user_id
            OR public.get_my_role() IN ('sme', 'admin')
        )
    );

-- ============================================================
-- risk_finding
-- ============================================================
DROP POLICY IF EXISTS "Customer sees own org findings" ON risk_finding;
CREATE POLICY "Customer sees own org findings" ON risk_finding
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR risk_finding.organization_id IN (
                SELECT p.organization_id FROM public.profiles p
                WHERE p.user_id = auth.uid()
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
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR report_snapshot.organization_id IN (
                SELECT p.organization_id FROM public.profiles p
                WHERE p.user_id = auth.uid()
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
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR derived_data_item.organization_id IN (
                SELECT p.organization_id FROM public.profiles p
                WHERE p.user_id = auth.uid()
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
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR organization_intelligence_profile.organization_id IN (
                SELECT p.organization_id FROM public.profiles p
                WHERE p.user_id = auth.uid()
            )
        )
    );
