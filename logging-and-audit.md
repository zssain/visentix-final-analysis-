# Logging & AI Audit — Catch Errors Once, Never Repeat Them

**The principle:** every action leaves a trace; an AI auditor periodically reads the traces; every real lesson becomes a spec change. The goal is not logging for logging's sake — it's that **the same mistake can never surprise us twice**, because the first occurrence permanently changed the written truth we build from.

This plugs into the existing feedback loop. Audits don't create a new process — they *feed the one we already have*: audit findings become `feedback` issues → triage agent drafts spec PRs → expert/engineer approve → AGENTS.md regenerates. One loop, two inlets (humans and logs).

```
                  humans (expert, customers, devs)
                        │  feedback issue form
                        ▼
   logs ──► [weekly log-audit agent] ──► feedback issues ──► triage ──► spec PRs
    ▲              │                                                      │
    │              └──► audit report PR (logs/audits/)                    ▼
    │                                                          lessons ledger entry
    └── every action, always                                   (visentix-specs/04-lessons)
```

---

## 1. The three logs

We keep exactly three human-curated logs (plus normal machine logs). Few enough to actually maintain; each answers one question.

### 1a. Decision log — "why is it this way?"
`logs/decision-log.md` — one line per meaningful decision that isn't already captured in a spec changelog: tool choices, tradeoffs taken under pressure, things we decided NOT to do. Append-only, newest first. One sentence of context is enough; the point is that six months from now nobody re-litigates a settled question because the reasoning was lost.

### 1b. Incident log — "what went wrong?"
`logs/incidents/YYYY-MM-DD-short-slug.md`, one file per incident, from the template. An *incident* is anything that cost us more than an hour or touched a hard rule: a bug that reached the expert or a customer, a pipeline that produced a wrong score, an agent that did something out of scope, a deploy that broke, a guardrail near-miss. Blameless by rule — incident files name causes, never people. **If you're unsure whether something counts, it counts.** Filing takes five minutes; the template asks only what the audit needs.

### 1c. Agent-run log — "what did the AI do?"
Automatic, no typing: every automated agent run already leaves its trail in GitHub (Action run logs, the PRs/comments it created, commits referencing feature IDs). Our conventions make this trail auditable — feature IDs in commits, `auto-drafted` labels, issue links in PR bodies. For *local* AI-assisted work, the engineer's obligation is lighter: the resulting PR description states what was AI-implemented and which acceptance criteria it targets. That's the log.

Machine/application logs (backend errors, pipeline failures, test-suite history) stay where they naturally live (server logs, CI history); the audit agent reads CI history via the GitHub API and anything you export into `logs/exports/` (e.g., a weekly grep of production ERROR lines — one cron job, no product changes needed).

## 2. The weekly AI audit

The `log-audit.yml` workflow runs every Monday (and on demand). The agent:

1. **Reads the week's traces**: new incident files, decision-log entries, failed CI runs and their causes, merged PRs (checking spec-reference discipline), and any `logs/exports/` dumps.
2. **Looks for patterns, not just events**: the same test flaking three times, two incidents with the same root cause, agent PRs repeatedly needing the same correction, a guardrail term that keeps almost slipping in — patterns are where spec changes hide.
3. **Writes the audit report** as a PR adding `logs/audits/YYYY-MM-DD-audit.md`: what happened, patterns found, and a short list of **proposed lessons** — each phrased as "what should the specs/AGENTS.md say so this can't recur?"
4. **Files one `feedback` issue per actionable lesson.** From there the *existing* triage loop takes over and drafts the actual spec edits. The audit agent itself never edits specs — separation keeps each agent simple and reviewable.
5. **Checks the ledger**: verifies previously-accepted lessons actually landed (spec merged, guard added) and flags any that stalled.

Humans review the audit PR like any other. Boring audits ("nothing notable, 0 lessons") are a feature — merge and move on.

## 3. The lessons ledger

`visentix-specs/04-lessons/lessons.md` is the permanent memory: one row per accepted lesson — what happened, root cause, and **the link to the spec change or CI guard that makes it unrepeatable**. A lesson without a resulting change isn't closed. When a new engineer asks "why does the spec insist on X?", the answer is one ledger lookup away.

Rule of gradation for what a lesson produces, strongest first:
1. **A CI/automated guard** (best — machines remember perfectly): new test, new spec-guard check, new lint rule.
2. **A spec/AGENTS.md change** (good — every future agent run inherits it).
3. **A checklist/onboarding change** (weakest — use only when 1–2 don't apply).
Prefer moving lessons *up* this ladder over time.

## 4. What this asks of each person, honestly

- **Engineers:** append one line to the decision log when you make a judgment call; file an incident when something bites; keep putting Fxx IDs in commits. Total cost: minutes per week.
- **The expert:** read the weekly audit PR (it's short) and the drafted spec PRs it spawns. Your audit hat, with the evidence pre-gathered.
- **Nobody:** writes status reports. The audit is generated *from* the traces of real work, never as extra work.
