# Who Does What — Our Team, Roles, and How Work Flows

We are deliberately tiny: **two engineers** and **one expert**, plus AI doing a lot of the heavy lifting. Small only works if everyone knows exactly what's theirs, what's shared, and how things hand off. This document is that agreement. When we hire, the new person's first job is to find where they fit on this page.

---

## The three seats

### The Engineers (2)

**Own:** everything that runs — the backend, the frontend, the database, the AI pipeline, deployments, and the test suite.

**Their day, roughly:** pick a feature spec from `visentix-specs/02-features/`, implement its acceptance criteria (usually with an AI coding agent doing the typing while the engineer directs and reviews), keep the test suite green, and ship.

**They decide:** how something is built — languages, libraries, architecture within the spec's constraints.

**They do NOT decide:** *what* the product claims, what a score means, what language reports use, whether a finding is correct, or whether something is safe to show a customer. Those belong to the expert and the specs.

### The Expert (1)

Our expert wears three hats, and it helps to name them separately:

**Hat 1 — The Reviewer (in the product).** Before any client report ships, the expert works through the review workbench: confirming, editing, or dismissing every finding, and writing/approving the human-voiced Advisor notes. Only the expert can flip a report from draft to approved. Every review action also trains the system.

**Hat 2 — The Business-Logic Owner (in the specs).** The scoring formulas, the taxonomy, the guardrail language, the definitions in the Codex, what counts as a peer — the expert owns the *content* of all of it. Engineers implement it faithfully; they don't reinterpret it. If a formula weight should change, that's an expert decision, recorded as a new version.

**Hat 3 — The Auditor (over our own work).** The expert periodically reviews what we build the way a skeptical customer or regulator would: Is this claim defensible? Did jargon leak into a customer screen? Does this generated sentence brush against a legal verdict? Is this data handling something we'd be comfortable explaining publicly? Audit feedback goes into the issue tracker like any other bug — no special ceremony, no hurt feelings.

**The expert does NOT:** write code, manage servers, or need to understand the codebase. If the expert ever *needs* to read code to do their job, we've failed — the product's review screens and these documents are supposed to be enough.

### The AI agents (unofficial fourth seat)

AI coding agents do much of the implementation, always directed by an engineer and always working from written specs. AI also reads and drafts inside the product itself (classifying clauses, drafting narratives) — but never decides scores and never publishes anything the guardrail filter and, for client work, the expert haven't cleared. See `09-how-we-build.md`.

---

## How work flows between us

### Flow 1 — Building a feature
1. Someone proposes it (anyone can). It becomes a short written spec.
2. **Expert reviews the spec** for correctness of the privacy/business content and guardrail safety. This is cheap to do at the spec stage and expensive to do after code exists — so it always happens first.
3. Engineers implement to the spec's acceptance criteria.
4. Expert sees the built thing in a demo (audit hat on).
5. Ship.

**The golden rule:** *the expert reviews specs and screens, not code.* Engineers translate expert knowledge into software; the specs are the shared language in the middle.

### Flow 2 — Delivering a client report
1. Customer's notice enters the pipeline (or an engineer runs it for them during the pilot phase).
2. System produces a **draft** — watermarked, held by the gate.
3. Expert works the review queue (Hat 1). Confirm / edit / dismiss.
4. Expert approves → report freezes into its snapshot → delivered.
5. Engineers are on call only if something breaks; they never edit findings.

### Flow 3 — The expert spots a problem in production
1. Expert files it in plain language ("this recommendation reads like legal advice", "this cohort feels wrong for a healthcare client").
2. Engineer triages: is it a code bug, a data problem, or a spec problem?
3. Spec problems go back through Flow 1. Code bugs get fixed with a test so they can't return.

### Flow 4 — A customer asks something nobody's sure about
Questions about **what a score means, what we claim, or anything legal-adjacent** → expert answers. Questions about **how the system behaves technically** → engineers answer. When unsure which it is, it's the expert's call first. Sales/marketing never invents an answer about methodology — that path always runs through the expert.

---

## Decision rights, at a glance

| Decision | Engineers | Expert |
|---|---|---|
| How to build it (architecture, code, tools) | ✅ decide | consulted if it affects data handling |
| What a formula/score/finding means | implement only | ✅ decide |
| Report language & guardrail questions | implement only | ✅ decide |
| A finding in a specific client report | never touch | ✅ decide |
| Whether a report ships to a client | — | ✅ decide (approval) |
| Release priorities | propose | propose | *(founders decide together)* |
| Is this safe/defensible to show publicly? | flag concerns | ✅ final say |

## When we grow

The seams above are the future job descriptions. A third engineer slots into Flow 1. A second expert starts as a Reviewer (Hat 1) under the current expert's guidance — Hats 2 and 3 stay singular longer, because the product's voice must stay consistent. A customer-facing hire lives in Flow 4 and `04-what-we-deliver.md` is their bible.
