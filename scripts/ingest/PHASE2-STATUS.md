# Phase 2 (breach + sector laws) — ✅ COMPLETE & DEPLOYED (v1.0.3-pilot)

**Completed 2026-08-18.** All 50 states + DC are now assessable. All 51 breach-notification laws +
10 sector laws verified vs primary sources, ingested (51 `security_practices_disclosure` + 10 sector
obligations, all embedded), codex-linked (+60), and the 25 remaining jurisdictions added to intake.
Deployed as **v1.0.3-pilot** (commit 4e55946) — container healthy, public /health 200, intake offers
all 50 states + DC. Data snapshot: `scripts/ingest/phase2_breach_sector_data.json`.
SME follow-up: all Phase 2 refs/obligations are `sme_authored=false` (pending review); SEC-006 finding
was operator-approved as `proposed` — confirm with legal expert. Section-level pin cites flagged
UNVERIFIED in the research (NV/CT/OR/IN sector subsections) should be spot-checked before publishing.

<details><summary>Original resume checkpoint (historical)</summary>

## ✅ DONE (committed + in DB)
- **Spec** (approved + merged to remediation-2026-08-04): schema.md §2.4 **v1.3.9**, intelligence-logic.md §4 **v1.6**, decision-log entry, AGENTS.md regen. Commits `61d1933` (spec), `19ab7d8` (merge).
- **Code** (`1ae5a92`): 4 new `requirement_type`s in `ingest_state_laws.py` (`REQUIREMENT_TYPES` + `REQ_DOMAIN_MAP`); `findings.py` `DOMAIN_TO_FINDING["security"]="SEC-006"` + `DEFAULT_SEVERITY["SEC-006"]="high"`.
- **DB**: `finding_type` row `SEC-006` "Security Practices Disclosure Gap" (domain `security`, sme_authored=false).

## TAXONOMY (final, approved)
| requirement_type | domain slug | finding | applies to |
|---|---|---|---|
| `security_practices_disclosure` | `security` (NEW) | SEC-006 | ALL 50 + DC (universal breach-law security floor) |
| `biometric_disclosure` | `sensitive_data` | SEC-002 | IL, TX, WA |
| `consumer_health_data_disclosure` | `sensitive_data` | SEC-002 | WA, NV, CT |
| `data_broker_disclosure` | `data_sharing` | SH-002 | CA, VT, TX, OR |
- Broaden `retention_disclosure` (disposal) + `childrens_data_restrictions` (AADC) — no new string.
- EXCLUDED from scoring (F05 reference only): breach timelines, AG-notification thresholds, breach-letter content, credit-monitoring, data-broker registration filings.
- Does NOT trigger OD-06 (laws-as-obligations, not incidents→F-004). No scoring formula.

## ⬜ REMAINING STEPS (resume here)
1. **Verify** breach-notification citation + `reasonable_security_duty` (explicit/implied/none) for the ~46 unverified jurisdictions (all 51 minus OH/OK/OR/PA/RI below), + exact sector-law citations (BIPA/CUBI/WA-biometric; WA-MHMD/NV-SB370/CT-health; CA/VT/TX/OR data-broker). Grouped agents (~10 states each), NOT recursive aggregators (they stalled).
2. **Build data**: one `security_practices_disclosure` obligation per jurisdiction (all 51) + a breach-law `legal_reference` (citation + official_url, sme_authored=false); sector obligations for the ~8 sector states. Reuse `sb.py`/`ingest_state_laws.py` idempotent upsert pattern.
3. **Ingest** obligations + legal_reference (stdlib `sb.py ingest`).
4. **Embed** new obligations on the VM (`docker cp embed_obligations.py + .env` into azure-api-1; see deploy-topology memory).
5. **Codex-link**: add `finding_legal_reference` (breach refs → SEC-006 / DC-005; sector refs → SEC-002/SH-002).
6. **Intake**: add the ~22 no-comprehensive-law states + DC to `config/org_profile_weights.json` `rss_state_lookup` + `app/services/intake_options.py` labels → all 50+DC selectable & meaningful.
7. **Deploy** `v1.0.3-pilot` (git bundle → deploy.sh; see deploy-topology memory for the bundle-transfer + deploy.sh --env-file bug).

## VERIFIED DATA SO FAR (5 states — primary-source)
```json
[
 {"jurisdiction":"OH","breach_law_name":"Ohio Data Breach Notification Law","breach_law_citation":"Ohio Rev. Code §§ 1349.19, 1349.191, 1349.192","breach_law_url":"https://codes.ohio.gov/ohio-revised-code/section-1349.19","reasonable_security_duty":"explicit","reasonable_security_basis":"Ohio Data Protection Act (ORC Ch. 1354) — safe-harbor/affirmative-defense cybersecurity statute (defense-based, not a hard mandate)"},
 {"jurisdiction":"OK","breach_law_name":"Oklahoma Security Breach Notification Act","breach_law_citation":"24 Okla. Stat. §§ 161–166","breach_law_url":"https://law.justia.com/codes/oklahoma/title-24/section-24-163/","reasonable_security_duty":"implied-today","reasonable_security_basis":"SB 546 controller security duty effective 2027-01-01 (not in force Aug 2026); today only the breach act"},
 {"jurisdiction":"OR","breach_law_name":"Oregon Consumer Information Protection Act (OCIPA)","breach_law_citation":"ORS 646A.600–646A.628 (notification at 646A.604)","breach_law_url":"https://oregon.public.law/statutes/ors_646a.604","reasonable_security_duty":"explicit","reasonable_security_basis":"ORS 646A.622 reasonable-safeguards duty + OCPA controller duty (ORS 646A.578)"},
 {"jurisdiction":"PA","breach_law_name":"Breach of Personal Information Notification Act (BPINA)","breach_law_citation":"73 Pa. Stat. §§ 2301–2329","breach_law_url":"https://www.attorneygeneral.gov/report-a-data-breach/bpina/","reasonable_security_duty":"implied","reasonable_security_basis":"No standalone data-security statute, no comprehensive law in force; duty via common law / UTPCPL"},
 {"jurisdiction":"RI","breach_law_name":"Rhode Island Identity Theft Protection Act of 2015","breach_law_citation":"R.I. Gen. Laws §§ 11-49.3-1 et seq. (notification at 11-49.3-4)","breach_law_url":"https://webserver.rilegislature.gov/Statutes/TITLE11/11-49.3/11-49.3-4.htm","reasonable_security_duty":"explicit","reasonable_security_basis":"R.I. Gen. Laws § 11-49.3-2 risk-based information-security-program mandate"}
]
```
Note: OH is defense-based ("explicit" but soft); OK becomes explicit 2027-01-01. Applicability text should reflect these nuances.

</details>
