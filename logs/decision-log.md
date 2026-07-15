# Decision Log — append-only, newest first

Format: `YYYY-MM-DD · who · decision · one-line why`

- 2026-07-15 · Claude+Asad · Absorbed still-relevant content from the archived docs into the specs (verified against code first): LANGUAGE.md → business-logic v1.2 §2 (approved-alternative table, exposure pattern, caveats); DATA_HANDLING.md → business-logic v1.2 §6 (hosted-endpoint zero-retention policy, `HOSTED_QWEN_*`); SECURITY_MATRIX.md → F10 (route + RLS matrices); reclassification columns → schema v1.1 + intelligence-logic v1.1 §4; test count 453→633; AGENTS.md regenerated · fixed a dangling DATA_HANDLING.md reference and kept the migrated facts in the source of truth. NOTE: the coverage review's JWT ("use ES256") and table-naming ("legal_reference → finding_enforcement") suggestions were WRONG per the code — verification caught both; F10 now states ES256+HS256-fallback accurately and schema table names were left unchanged. Local test run is 610/633 (23 failures are live-DB-dependent, not verified green here).

- 2026-07-15 · Claude+Asad · Restructured repo docs to the spec-driven system: exploded the visentix-docs bundle to repo root (visentix-specs/, visentix-onboarding/, compiled AGENTS.md, AUTOMATION.md, logging-and-audit.md, .github/, logs/, scripts/build_agents_md.py, .claude/skills/spec-update/); archived 19 superseded/historical docs to docs/old-docs/ via git mv (kept SETUP/DEMO_RUNBOOK/DB_GROUND_TRUTH live); scrubbed demo creds from the archived VICBNF verification; removed 54 Windows Zone.Identifier cruft files · one source of truth, history preserved, nothing hard-deleted.

- 2026-07-15 · team · Verbal feedback made the primary inlet via the spec-update skill (skills/spec-update/); feedback-triage GitHub workflow demoted to optional async path; spec-guard, agents-sync, log-audit unchanged · feedback is usually spoken, not filed — the skill removes the ticket tax while keeping every bit of the discipline.

- 2026-07-15 · team · Report specs updated from Appendix H/I prototypes: F05 gained closing matter (Next Steps + back cover, AC-5); F12 gained a full publication section manifest (Intelligence Indicators, Benchmark Spotlight, descriptive-only Strategic Outlook, real-count cover rule, AC-5–8); design-system v1.1 adds trendColor polarity flag · prototypes are the visual target, specs now match them minus the fabricated-scale and faked-history flaws.

- 2026-07-15 · team · Merged legacy AGENTS.md into compiled AGENTS.md: kept data-protection, secrets/SSRF, STOP-and-ask, and change-report discipline; extended banned-term list (hard_rules + spec-guard + business-logic v1.1); replaced phase-named branches with Fxx-named branches · single source of agent truth, nothing lost.

- 2026-07-15 · team · Adopted spec-driven repo (visentix-specs/) + compiled AGENTS.md + feedback/audit automation · two-person eng team needs written truth and machine memory.
- 2026-07-15 · team · Audit agent files feedback issues instead of editing specs directly · keeps each agent single-purpose and human-reviewable.
