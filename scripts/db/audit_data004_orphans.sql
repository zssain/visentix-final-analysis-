-- DATA-004 orphan audit — RUN THIS (read-only) before VALIDATE CONSTRAINT / NOT NULL.
-- It reports rows that would violate the new FKs so they can be quarantined/repaired
-- (never destroyed). Zero rows everywhere → safe to VALIDATE + tighten NOT NULL.

-- risk_finding: org_id present but not in organization
SELECT 'risk_finding.organization_id orphan' AS check, count(*) AS n
FROM public.risk_finding rf
LEFT JOIN public.organization o ON o.organization_id = rf.organization_id
WHERE rf.organization_id IS NOT NULL AND o.organization_id IS NULL;

-- risk_finding: notice_id present but not in privacy_notice
SELECT 'risk_finding.notice_id orphan' AS check, count(*) AS n
FROM public.risk_finding rf
LEFT JOIN public.privacy_notice pn ON pn.notice_id = rf.notice_id
WHERE rf.notice_id IS NOT NULL AND pn.notice_id IS NULL;

-- risk_finding: null owners (would block a future NOT NULL on scored rows)
SELECT 'risk_finding.organization_id NULL' AS check, count(*) AS n
FROM public.risk_finding WHERE organization_id IS NULL;
SELECT 'risk_finding.notice_id NULL' AS check, count(*) AS n
FROM public.risk_finding WHERE notice_id IS NULL;

-- report_snapshot: org_id orphan
SELECT 'report_snapshot.organization_id orphan' AS check, count(*) AS n
FROM public.report_snapshot rs
LEFT JOIN public.organization o ON o.organization_id = rs.organization_id
WHERE rs.organization_id IS NOT NULL AND o.organization_id IS NULL;

-- organization_intelligence_profile: org_id orphan
SELECT 'organization_intelligence_profile.organization_id orphan' AS check, count(*) AS n
FROM public.organization_intelligence_profile oip
LEFT JOIN public.organization o ON o.organization_id = oip.organization_id
WHERE oip.organization_id IS NOT NULL AND o.organization_id IS NULL;

-- After all counts are 0 (or offenders quarantined), enforce fully:
--   ALTER TABLE public.risk_finding VALIDATE CONSTRAINT risk_finding_organization_id_fkey;
--   ALTER TABLE public.risk_finding VALIDATE CONSTRAINT risk_finding_notice_id_fkey;
--   ALTER TABLE public.report_snapshot VALIDATE CONSTRAINT report_snapshot_organization_id_fkey;
--   ALTER TABLE public.organization_intelligence_profile
--     VALIDATE CONSTRAINT organization_intelligence_profile_organization_id_fkey;
-- And (only if the org/notice NULL counts above are 0 for scored rows) tighten:
--   ALTER TABLE public.risk_finding ALTER COLUMN organization_id SET NOT NULL;  -- scored rows
