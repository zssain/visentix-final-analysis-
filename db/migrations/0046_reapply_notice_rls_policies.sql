-- 0046_reapply_notice_rls_policies.sql
-- Author: engineer (remediation Phase 4) · Feature: SEC-008 · Date: 2026-08-04
--
-- CHECKLIST:
--   [x] ADDITIVE / CORRECTIVE — re-applies the org-scoped SELECT policies that
--       migration 0011 declared for privacy_notice / notice_section /
--       disclosure_clause but which the live schema dump shows are ABSENT (ledger
--       drift: 0011 is marked applied, yet its policies never materialized). This
--       does NOT rewrite applied history — 0011 stays as-is; this is a new,
--       forward corrective migration.
--   [x] IDEMPOTENT — ENABLE RLS is a no-op if already on; each policy is
--       DROP POLICY IF EXISTS then CREATE, so a re-run converges.
--   [x] RLS — these three tables are RLS-ON since 0042 but currently have NO
--       policy → deny-all. After 0042 the API uses the service-role key (bypasses
--       RLS), so this is harmless today; it becomes load-bearing the moment any
--       anon/user-JWT read path is introduced (SEC-003 direction). Restoring the
--       intended policies closes the documented "org-scoped notice isolation" gap.
--
-- Verbatim re-application of 0011 §3-5 (policies only; the column/enable steps in
-- 0011 are already in place). Depends on public.get_my_role() + public.profiles
-- (present since 0011/F10).

ALTER TABLE public.privacy_notice   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notice_section    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.disclosure_clause ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "privacy_notice_select" ON public.privacy_notice;
CREATE POLICY "privacy_notice_select" ON public.privacy_notice
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR privacy_notice.organization_id IS NULL
            OR privacy_notice.organization_id IN (
                SELECT p.organization_id FROM public.profiles p
                WHERE p.user_id = auth.uid()
            )
        )
    );

DROP POLICY IF EXISTS "notice_section_select" ON public.notice_section;
CREATE POLICY "notice_section_select" ON public.notice_section
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR notice_section.notice_id IN (
                SELECT pn.notice_id FROM public.privacy_notice pn
                WHERE pn.organization_id IS NULL
                   OR pn.organization_id IN (
                       SELECT p.organization_id FROM public.profiles p
                       WHERE p.user_id = auth.uid()
                   )
            )
        )
    );

DROP POLICY IF EXISTS "disclosure_clause_select" ON public.disclosure_clause;
CREATE POLICY "disclosure_clause_select" ON public.disclosure_clause
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND (
            public.get_my_role() IN ('sme', 'admin')
            OR disclosure_clause.section_id IN (
                SELECT ns.section_id FROM public.notice_section ns
                JOIN public.privacy_notice pn ON pn.notice_id = ns.notice_id
                WHERE pn.organization_id IS NULL
                   OR pn.organization_id IN (
                       SELECT p.organization_id FROM public.profiles p
                       WHERE p.user_id = auth.uid()
                   )
            )
        )
    );
