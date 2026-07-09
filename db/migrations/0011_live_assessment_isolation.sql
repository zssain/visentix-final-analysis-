-- Migration 0011: RLS on privacy_notice, notice_section, disclosure_clause
-- Protects live customer uploads via org-scoped policies.
-- Seed corpus rows (organization_id IS NULL) remain visible to all authenticated users.
-- ADDITIVE ONLY: new column (if missing), enable RLS, new policies.

-- ============================================================
-- 1. Ensure organization_id is nullable on privacy_notice
--    (column already exists; this is a safety no-op if it's already nullable)
-- ============================================================
ALTER TABLE privacy_notice
    ALTER COLUMN organization_id DROP NOT NULL;

-- ============================================================
-- 2. Enable RLS on all three tables
-- ============================================================
ALTER TABLE privacy_notice      ENABLE ROW LEVEL SECURITY;
ALTER TABLE notice_section       ENABLE ROW LEVEL SECURITY;
ALTER TABLE disclosure_clause    ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 3. privacy_notice — has organization_id directly
-- ============================================================
DROP POLICY IF EXISTS "privacy_notice_select" ON privacy_notice;
CREATE POLICY "privacy_notice_select" ON privacy_notice
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR privacy_notice.organization_id IS NULL  -- public seed corpus
            OR privacy_notice.organization_id IN (
                SELECT p.organization_id FROM public.profiles p
                WHERE p.user_id = auth.uid()
            )
        )
    );

-- ============================================================
-- 4. notice_section — scoped via join to parent privacy_notice
-- ============================================================
DROP POLICY IF EXISTS "notice_section_select" ON notice_section;
CREATE POLICY "notice_section_select" ON notice_section
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR notice_section.notice_id IN (
                SELECT pn.notice_id FROM privacy_notice pn
                WHERE pn.organization_id IS NULL
                   OR pn.organization_id IN (
                       SELECT p.organization_id FROM public.profiles p
                       WHERE p.user_id = auth.uid()
                   )
            )
        )
    );

-- ============================================================
-- 5. disclosure_clause — scoped via join to notice_section → privacy_notice
-- ============================================================
DROP POLICY IF EXISTS "disclosure_clause_select" ON disclosure_clause;
CREATE POLICY "disclosure_clause_select" ON disclosure_clause
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR disclosure_clause.section_id IN (
                SELECT ns.section_id FROM notice_section ns
                JOIN privacy_notice pn ON pn.notice_id = ns.notice_id
                WHERE pn.organization_id IS NULL
                   OR pn.organization_id IN (
                       SELECT p.organization_id FROM public.profiles p
                       WHERE p.user_id = auth.uid()
                   )
            )
        )
    );
