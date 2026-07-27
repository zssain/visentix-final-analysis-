# Ingestion connectors — licensing & use notes

## Princeton-Leuven privacy-policy corpus (`princeton.py`, family `princeton_leuven`)

⚠️ **RESEARCH-USE LICENSING MUST BE VERIFIED BEFORE ANY COMMERCIAL BENCHMARK OR
PUBLICATION USE.**

The Princeton-Leuven Longitudinal Privacy-Policy corpus (and the per-sector CSVs
derived from it) is an academic research dataset. Its license terms for **commercial
benchmarking, redistribution, or publication** have **not** been confirmed by legal.

- **Current permitted use (pending verdict):** INTERNAL model **training / evaluation**
  only. Imported notices are flagged `organization.origin='princeton_leuven'` and land
  with truthful ~2019 freshness, so CQS gating keeps them out of ACTIVE benchmark
  populations.
- **NOT yet permitted:** using these notices (or metrics derived from them) in any
  customer-facing benchmark, published report, or commercial deliverable.

**This is an open decision requiring an expert/legal verdict** — record it in
`visentix-specs/00-plan/open-decisions.md` before promoting this corpus to any
commercial/benchmark use. Until then the importer deliberately writes **no**
`benchmark_membership` rows.

## Other connectors
- `edgar.py` (sec_edgar), `hhs_ocr.py`, `ftc.py`, `cppa.py`, `state_ag.py`,
  `_enforcement.py` — see each module's docstring for source and licensing posture.
