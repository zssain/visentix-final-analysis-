# Onboarding Checklists — Your First Week, by Role

Print your section. Check the boxes. Ask questions loudly — asking is the culture here.

---

## New Engineer — Week One

### Day 1 — Understand the product (no code yet)
- [ ] Read `01-what-is-visentix.md`, `02-how-it-works.md`, `06-the-rules-we-never-break.md`
- [ ] Skim `03-words-we-use.md`; bookmark it
- [ ] Watch (or run) the demo end to end: submit a notice, see the report
- [ ] Say back to a teammate, in your own words, why we never say "compliant." If you can't, re-read Rule 1 — this one question is our real onboarding exam.

### Day 2 — Environment & code
- [ ] Clone the repo; follow SETUP.md (Python venv, Ollama local LLM, embedding model, Postgres/Supabase, `npm` for the web app)
- [ ] Run the backend (`uvicorn`, check `/health` and `/docs`) and frontend (Vite dev server)
- [ ] Run the full test suite (`pytest` + `vitest`) — it must be green before you touch anything. If it isn't, that's your first bug report.

### Day 3 — The specs
- [ ] Read `visentix-specs/README.md` (the spec-driven workflow) and `09-how-we-build.md` here
- [ ] Read the four foundation docs: schema, business-logic, intelligence-logic, design-system
- [ ] Pick any screen in the app and find its feature spec; verify reality matches the spec. Report any drift you find — spotting drift is a gift.

### Day 4 — First contribution
- [ ] Take a small item from the MVP completion plan (a mock-wiring task is ideal — self-contained, real)
- [ ] Implement it with an AI agent per `09-how-we-build.md`; keep tests green; reference the feature ID in your commits
- [ ] Get it reviewed by the other engineer

### Day 5 — Meet the expert
- [ ] Sit with the expert for one review-queue session; watch Confirm/Edit/Dismiss happen
- [ ] Ask them: "what do you wish the product did better?" Write the answers down; file the good ones.

## New Expert / Reviewer — Week One

### Day 1 — The product and your seat
- [ ] Read `01-what-is-visentix.md`, `05-who-does-what.md` (your three hats), `06-the-rules-we-never-break.md`
- [ ] Read `04-what-we-deliver.md` — this is what your approval stands behind

### Day 2 — The vocabulary and the method
- [ ] Read `02-how-it-works.md` and `03-words-we-use.md`
- [ ] Read the Methodology page inside the product; confirm every formula description makes sense to you — if any doesn't, it gets rewritten until it does (that's the standard, not a favor)

### Day 3 — Shadow reviewing
- [ ] Sit with the current expert through a full review queue
- [ ] Learn the de-identification flow: try to approve an exemplar containing an email and watch the system block you

### Day 4 — Supervised reviewing
- [ ] Work a queue yourself with the current expert watching; discuss every Edit and Dismiss
- [ ] Practice the Advisor-note voice: warm, plain, no verdict language — read a few approved ones first

### Day 5 — The auditor hat
- [ ] Click through every customer-facing screen looking for: verdict language, jargon leaks, numbers without lineage, dishonest-feeling displays
- [ ] File everything you find, however small. Your fresh eyes are most valuable this week.

## New Business / Customer-Facing Person — Week One

- [ ] Read `01-what-is-visentix.md`, `04-what-we-deliver.md`, `07-customer-journeys.md`
- [ ] Learn the three sentences you'll say most:
  - "We show you how your privacy notice compares to your true peers — with the evidence one click away."
  - "It's intelligence, not legal advice — that's exactly why lawyers trust it."
  - "Every number in the report can show you where it came from."
- [ ] Learn what we never promise: legal conclusions, compliance certification, guarantees about regulator behavior
- [ ] Know the escalation rule: methodology and legal-adjacent questions go to the expert, always — never improvise those answers
- [ ] Do the demo yourself three times until the "click a score, see the lineage" moment is muscle memory — it's the close.

## Everyone, by end of week one

- [ ] You can explain the product to a friend in two sentences
- [ ] You know what a snapshot is and why reports never change
- [ ] You know Rule 1 cold
- [ ] You know who to ask about what (`05-who-does-what.md`)
- [ ] You've filed at least one issue, idea, or doc fix — day-one eyes see things the rest of us have gone blind to
