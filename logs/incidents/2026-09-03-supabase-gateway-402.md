# Incident: Supabase gateway blocks demo-user provisioning

**Date:** 2026-09-03 · **Filed by:** engineer · **Severity:** blocking

## What happened
The idempotent internal-demo provisioning utility reached the configured Supabase project but both Auth and REST returned HTTP 402. The failure occurred during the initial workspace lookup, before the utility created an organization row or any user identity. Direct database connectivity remained available and the additive migrations had already applied successfully.

## Root cause
The project gateway is rejecting Auth and REST requests because of external Supabase project state, quota, or billing posture. The response code establishes the gateway-level block; the exact account-side reason is not available inside the application workspace.

## What stopped it / how it was found
Provisioning fails closed on every non-success response and reports only the status code, never the upstream body or any credential. No attempt was made to insert directly into Supabase's Auth schema because that would bypass the supported credential lifecycle.

## Proposed lesson
Add an Auth-and-REST readiness check to the deployment runbook before provisioning or release rehearsals. A reachable TCP port is insufficient evidence that the Supabase APIs are usable.

## References
- `scripts/db/provision_demo_users.py`
- `visentix-specs/02-features/F10-auth-and-tenancy.md`
