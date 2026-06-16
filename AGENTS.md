# AGENTS.md — Visentix MVP Engineering Rules
You are building the Visentix Privacy Intelligence MVP. Read this file fully
before every task. These rules override any instinct to be "helpful" by taking
shortcuts. When a rule and a task instruction conflict, STOP and ask the human.
## 0. What Visentix is (so you make the right calls)
Visentix turns public privacy notices into benchmark-driven privacy INTELLIGENCE.
It answers "compared to whom, with what exposure, at what confidence" — it NEVER
answers "is this legal / compliant / a violation." Output is exposure, maturity,
likelihood, benchmark, and confidence language only.
## 1. The build is MID-FLIGHT — protect existing data
A normalized corpus already lives in Supabase. You did not create it and you must
not endanger it.
- NEVER run DROP, TRUNCATE, DELETE, or destructive ALTER on existing tables.
- NEVER delete, move, or overwrite files in the `raw-artifacts` storage bucket.
- ALWAYS introspect the live schema (information_schema / Supabase) BEFORE writing
a migration. Migrations are ADDITIVE only (new tables, new nullable columns,
new indexes). If a change is not additive, STOP and ask.
- NEVER re-run NLP classification over the existing 3,655 clauses or recompute the
stored F-001 scores in place. New computations write to NEW rows/columns/versions.
- Treat these as read-only inputs unless a task explicitly says to populate a
documented NULL column: organization, source_record, privacy_notice,
notice_section, disclosure_clause, obligation, enforcement_record, regulator,
litigation_event, monitoring_event, formula_version, benchmark_membership.
## 2. Intelligence philosophy (non-negotiable product rules)
- The model CLASSIFIES and PHRASES. It never invents a claim, number, score,
finding, or recommendation. Scores come from the formula engine; findings come
from the fixed finding-type catalog; recommendations come from the authored
library. The LLM only smooths tone over pre-computed, guardrailed statements.
- PHRASING GUARDRAIL: banned legal-verdict terms must never appear in any
customer-facing text: "violation", "violates", "illegal", "unlawful",
"non-compliant", "breach of law", "guilty", "liable". Use exposure/likelihood
language. The guardrail runs at draft time and must hard-fail the build of a
report if a banned term is present.
- HONEST NUMBERS: benchmarking runs on ~30 orgs. Always attach the real cohort
size + date and a low-confidence label when n is small. NEVER print "1,250+"
or any fabricated scale anywhere.
- Every derived value MUST store: the formula_version id used, its input refs
(source_id / clause_id / regulator_id / benchmark_population), a VCI confidence
score, and a generated_at timestamp. No score without lineage.
- REPRODUCIBILITY: never silently overwrite a historical score. Re-scoring writes
a new versioned row and freezes a snapshot. Reports must regenerate identically
from their stored snapshot.
## 3. Secrets, keys, and data handling
- Secrets ONLY via environment variables loaded from `.env`. `.env` is gitignored.
Maintain `.env.example` with KEYS and dummy values only.
- NEVER hardcode or print: Supabase URL, anon key, service-role key, database
connection string, or any model API key. Never echo them in logs or commits.
- The Supabase SERVICE-ROLE key is server-side only. The browser/React app uses
the ANON key only, and relies on Row Level Security. Never ship the service key to the client.
- Enable and respect Row Level Security on any table exposed to the client.
- When sending notice text to a HOSTED model endpoint, use a provider configured
for zero-retention / no-training, set via env. Log that text was sent, never
log the full text of customer notices. Minimize what is sent.
- URL upload = SSRF risk. Block requests to private/link-local/loopback ranges
(10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1) and cloud metadata
endpoints (169.254.169.254). Validate scheme is http/https only.
- Validate uploads: enforce max size, allowed MIME types (pdf/html/plain), and
parse PDFs defensively (no shell-outs to untrusted tooling).
## 4. How you work
- Always work on a feature branch named for the phase (e.g. `phase-3-embeddings`).
Never commit directly to main.
- One module = one branch = one commit (or a small tidy set). Write a clear commit
message listing every file changed and every table/column added.
- Before editing, summarize in 3-5 lines: what you will change, which files, which
tables, and confirm it is additive. If risky or ambiguous, ask first.
- After finishing, OUTPUT a short change report: files touched, tables/columns
added, migrations created, how to run it, and any follow-ups.
- Do not install packages you do not use. Pin versions. Keep a requirements.txt
(Python) and package.json (JS) tidy.
- Network egress is restricted. If a needed domain is blocked, report it; do not
attempt workarounds.
## 5. Testing & security after EVERY module
- Every module ships with tests (pytest for Python, vitest/jest for JS). A module
is not "done" until its tests pass and you have run the security checklist for
that phase.
- Never weaken or skip a test to make the build pass. If a test legitimately needs
to change, explain why in the change report.
## 6. When to STOP and ask the human
- Any non-additive schema change.
- Any operation that could touch existing rows or the raw-artifacts bucket.
- Any place a real number is missing and you are tempted to fabricate one.
- Any banned-term guardrail failure you cannot resolve by rephrasing from the
template library.
- Any secret that would otherwise have to be hardcoded.
