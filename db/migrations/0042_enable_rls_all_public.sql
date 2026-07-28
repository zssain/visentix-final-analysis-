-- 0042_enable_rls_all_public.sql
-- SECURITY FIX — closes Supabase advisor `rls_disabled_in_public`.
--
-- Enables ROW LEVEL SECURITY and REVOKEs anon/authenticated grants on EVERY
-- public base table that currently has rowsecurity=false (38 tables as of
-- 2026-07-29 — see logs/incidents/2026-07-29-rls-disabled-public-tables.md for
-- the full inventory + exposure proof).
--
-- DENY-BY-DEFAULT: no policies are created. That is correct and safe here:
--   * the API reads/writes via PostgREST with the SERVICE-ROLE key (app/db.py),
--     which BYPASSES RLS;
--   * migrations + the APScheduler jobstore connect as the DB owner over direct
--     Postgres, which also BYPASSES RLS;
--   * the web client NEVER uses the anon key for data (no createClient/.from in
--     web/src; the anon key touches only the public JWKS endpoint).
-- So every legitimate access path is unaffected; only anon/authenticated
-- PostgREST access (the exposure) is closed.
--
-- IDEMPOTENT: the block only touches tables where rowsecurity=false, so a second
-- run finds none and does nothing. Additive (no DROP/DELETE, no data touched).
--
-- The 38 tables covered (origin migration in brackets; "base" = pre-0001 corpus):
--   Customer/tenant: organization[base], privacy_notice[base], notice_section[base],
--     disclosure_clause[base], source_record[base], monitoring_event[base],
--     org_notification_setting[0037], finding_clause[base], finding_enforcement[base],
--     finding_legal_reference[0016], clause_obligation[base], obligation[base]
--   Partner (secrets): partner[0039], partner_api_key[0039], partner_workspace[0039]
--   Backend/internal: alert_delivery[0037], job_run[0037], bulk_job[0038],
--     bulk_job_row[0038], feed_access_log[0039], gold_label[0036], clause_rewrite[0041],
--     recommendation_evidence[0041], quarterly_metric[0040], quarterly_snapshot[0040],
--     litigation[0037], litigation_event[base], training_label[0008]
--   Reference/corpus: finding_type[0001], formula_version[base], recommendation_library[0001],
--     regulator[base], legal_reference[0016], enforcement_record[base],
--     explainability_reference[0015], exemplar[0001], benchmark_cluster[base],
--     benchmark_membership[base]

DO $$
DECLARE
  t            text;
  cnt          int := 0;
  revoke_roles text;
BEGIN
  -- Build the revoke target from roles that actually exist (Supabase: anon,
  -- authenticated) so this is portable to a plain Postgres without those roles.
  SELECT string_agg(quote_ident(rolname), ', ')
    INTO revoke_roles
    FROM pg_roles
   WHERE rolname IN ('anon', 'authenticated');

  FOR t IN
    SELECT c.relname
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND c.relrowsecurity = false
     ORDER BY c.relname
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    IF revoke_roles IS NOT NULL THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM %s', t, revoke_roles);
    END IF;
    cnt := cnt + 1;
    RAISE NOTICE '0042 locked down: public.%', t;
  END LOOP;

  RAISE NOTICE '0042: RLS enabled + anon/authenticated grants revoked on % public table(s).', cnt;
END $$;
