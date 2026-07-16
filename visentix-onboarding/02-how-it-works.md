# How Visentix Works — The Journey of a Privacy Notice

No code, no math. This is the story of what happens between "a customer pastes in a link" and "an executive reads a beautiful report." Seven stops on the journey.

Our shorthand for it: **Ingest → Normalize → Classify → Benchmark → Score → Explain → Deliver.**

---

## Stop 1 — Intake: the notice arrives

A customer gives us their privacy notice as a web link, a PDF, or pasted text. We fetch it safely (the system checks the link isn't trying to trick us into fetching something it shouldn't — the customer just sees a quiet "verified source" checkmark), and we record exactly what we received, when, and from where. If the same notice changes later, we'll know, because we keep a fingerprint of every version.

*Why it matters:* everything downstream must be traceable back to "this exact document, captured on this exact date."

## Stop 2 — Decomposition: cutting it into sentences that matter

A privacy notice is a wall of text. We slice it into **clauses** — individual statements like "we may share your information with trusted partners." Each clause gets an ID (like C-118), so from now on we can point at a specific sentence instead of waving at the whole document.

The customer actually watches this happen on the intake screen: the original document on the left, the extracted clauses filling in on the right. Clicking a clause highlights where it came from. This is the first taste of our "every claim has a receipt" promise.

## Stop 3 — Classification: sorting the clauses

Each clause is sorted into one of eight topic areas: consumer rights, data collection, sharing, retention, AI, security, tracking, and cross-border transfers. Our AI does this sorting, and — importantly — it records **how confident it was** about each one. A confident classification flows straight through; a shaky one gets flagged for a human to look at.

## Stop 4 — Profiling & peer selection: who should we compare them to?

Before we score anything, we build a profile of the *company*: its industry, roughly how much regulatory attention it should expect, how sensitive its data is, how mature its privacy program looks, how sophisticated the organization is, whether it has enforcement history, and how mature its AI disclosures are.

That profile determines the **peer group** (we call it a *cohort*): companies genuinely similar across those dimensions. If we can't find enough truly similar peers, we widen the circle a little — and we *say so*, and lower our confidence accordingly. We never quietly pretend a small or loose comparison group is a strong one.

*The fairness rule:* a regional retailer gets compared to regional retailers, not to Amazon.

## Stop 5 — Scoring: the formula layer

Now the deterministic machinery runs. A set of versioned formulas (they have IDs like F-002, F-010) combines the clauses, the profile, the peer group, and our regulator and enforcement knowledge into scores: overall exposure, benchmark percentile, regulator exposure, disclosure maturity, AI transparency, and more. Weak spots become **findings**, each stamped with a code from our dictionary (like TRK-007 for a tracking-disclosure issue).

Two things to know:

- **The AI does not decide the scores.** AI helps read and sort text; the scores come from fixed, versioned formulas. Same inputs, same outputs, every time. That's what makes the numbers defensible.
- **Every score carries a confidence rating** (we call it the VCI). If confidence is too low, we don't show the number at all — we'd rather say less than mislead.

## Stop 6 — Expert review: the human gate

Before anything reaches a client, our expert opens the review workbench. For each finding they see the source clause, the machine's analysis, and a space to write the human summary. They can **confirm** it, **edit** it, or **dismiss** it (dismissed findings vanish from the client report). Every one of those decisions is also saved as training data, so the system keeps getting smarter about what our expert would say.

The workbench also has a safety net: if example language is going to be reused in reports for other customers, it must first be scrubbed of any names, emails, or web addresses — and the system physically blocks approval until it's clean.

## Stop 7 — Delivery: the report, frozen forever

Finally, the reviewed intelligence is assembled into the 12-section report — executive summary, risk dashboard, benchmark comparisons, regulator exposure heatmap, findings, recommendations, and a full traceability section. Every finding is shown two ways: the **Analyst view** (the machine's precise reading — grids and numbers) and the **Advisor view** (a warm, human-written note). One switch flips between them.

At delivery we take a **snapshot**: everything in the report — every number, every word of prose — is frozen with an ID like S-2041. Pull that report again in five years and it will be identical. If our formulas improve next month, old reports don't silently change; new assessments simply use the new versions.

## …and then it keeps going

Delivery isn't the end. The monitoring dashboard watches for changes: the customer's notice was edited, their score moved, a regulator made a relevant announcement, their peer group shifted. Meaningful changes appear in a change feed and, if serious, become alerts. That ongoing heartbeat is what turns a one-time report into a subscription.

---

## The whole journey on one line

**A document goes in → it becomes labeled sentences → the company gets a fair peer group → formulas turn it into scores with receipts → an expert blesses it → a frozen, beautiful report comes out → and the system keeps watching.**
