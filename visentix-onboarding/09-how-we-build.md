# How We Build — Specs, AI, and a Two-Person Engineering Team

This explains, in plain terms, how a team of two engineers plus one expert ships a product this ambitious — and why we work the way we do. The technical version lives in `visentix-specs/README.md`; this is the human version.

---

## The core idea: write it down first

Before anything gets built, it gets written down in plain, structured documents called **specs**:

- **Foundation specs** — the unchanging truths: what our data looks like, what our formulas are, what our business rules and design rules are.
- **Feature specs** — one document per feature: what it's for, what it touches, how it behaves, and a checklist of exactly what "done" means (we call those *acceptance criteria*).
- **Plans** — what we're finishing now and where we're heading.

The rule is simple: **specs change before code changes.** If we discover mid-build that a spec is wrong, we fix the spec first, get it agreed, and *then* fix the code. It feels slower for an afternoon and saves weeks.

## Why bother, with only three people?

Three reasons, and they're all about being small:

**1. The expert can't read code — and shouldn't have to.** Our expert owns all the business logic: formulas, definitions, guardrail language, what counts as a fair comparison. Specs are how that knowledge gets into the product *verifiably*. The expert reviews a two-page document, not ten thousand lines of Python. The specs are the shared language between the person who knows privacy and the people who know software.

**2. AI does most of the typing — and AI needs written instructions.** Our engineers direct AI coding agents that do the bulk of implementation. An AI agent with a precise spec ("build exactly these acceptance criteria, touch only these tables, run these tests") produces excellent work. An AI agent with a vague verbal wish produces confident nonsense. Specs are literally what makes the AI leverage safe.

**3. Memory.** With two engineers, nobody is a backup for anybody. If everything lives in one person's head, a vacation is an outage. The specs *are* the institutional memory — which is also why this onboarding pack exists.

## What a build cycle looks like

1. **Someone proposes** a feature — anyone can, including the expert or a customer request.
2. **A spec is written** using our template: purpose, who it's for, what data it touches, how it behaves, acceptance criteria, and which tests must pass.
3. **The expert reviews the spec** — is the privacy content right? Does anything risk the guardrail? This review takes minutes at the paper stage and would take days after code exists.
4. **An engineer + AI agent implement it.** The engineer loads the foundation docs and the feature spec into the AI's context and directs it: implement these criteria, nothing more. The engineer reviews everything the AI produces — AI is the typist, never the decider.
5. **The tests gate it.** Every feature spec names the tests that must pass. Our suite (450+ tests and growing) must be fully green before anything merges. When a bug is fixed, a test is added so it can never quietly return.
6. **The expert sees the built thing** in a demo (their auditor hat) before it counts as done.
7. **The spec gets a checkmark** and reality and paper agree again.

## The rules AI agents follow (worth knowing even if you never touch code)

- **Never invent numbers.** Formulas, weights, thresholds, and taxonomy codes come from the specs, versioned. An AI may not "improve" a weight on its own.
- **Never generate verdict language.** The banned-term rule applies to AI output doubly.
- **Never hardcode a display value.** Every number on a screen must come from real data — this is why our "mock tracker" (the list of temporary fake values) must be empty before anything ships to a client.
- **Always leave a trail.** Commits reference feature IDs; changes to formulas reference version numbers. Our product promises lineage to customers; our process practices lineage on itself.

## What this means for you

**If you're a new engineer:** your job is more *directing and verifying* than typing. Your craft shows in how precisely you scope work for the AI, how ruthlessly you review its output, and how green you keep the tests.

**If you're the expert (or a future one):** you have real power here without touching code. A sentence you change in a spec changes the product. Use it — and know that if a spec confuses you, the spec is wrong, not you.

**If you're business-facing:** when a customer asks "can it do X?", the honest answer path is: check the feature specs (what exists and what's planned), and never promise anything that isn't written down yet — instead, bring the request back and it may *become* a spec.

## The quiet payoff

This way of working mirrors the product itself. Visentix sells *explainable, versioned, reviewable intelligence* — and it is built by an explainable, versioned, reviewable process. When a customer or auditor someday asks "how do you know your system does what you claim?", our answer is the same one our reports give: *here are the receipts.*
