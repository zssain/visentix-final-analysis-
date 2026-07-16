# Classification Rubric — Which Kind of Feedback Is This?

Read this when the class isn't obvious. The test question for each class, then worked examples including the tricky ones.

## The one-question tests

| Class | The test |
|---|---|
| **spec-change** | "If the specs already said this, would the feedback disappear?" → yes |
| **guardrail** | "Does this touch verdict language, honesty of numbers, jargon register, lineage, or anything in the hard rules?" → yes (guardrail is spec-change with an alarm bell) |
| **code-bug** | "Do the specs already say the right thing, and the software just doesn't do it?" → yes |
| **lesson** | "Did something already bite us, and could it bite again if nothing written changes?" → yes |
| **idea** | "Is this a new capability rather than a correction of an existing promise?" → yes |
| **question** | "Is the person asking, not telling?" → yes |

When two classes both fit, precedence: **guardrail > lesson > spec-change > code-bug > idea > question.**

## Worked examples

**"The GC said the Recommendations section reads like legal advice."**
→ **guardrail.** Even if no literal banned term appears, the *register* is a hard-rule concern. Edit F05's guardrail notes and/or the recommendation-library guidance; flag for expert; check whether specific phrases should join the banned list.

**"The cohort footer showed n=30 but the customer's real cohort was 12."**
→ **code-bug** if the specs already demand live-queried n (they do — Hard Rule 7, M-12). The spec is right; the wiring isn't. Output a bug note citing F03/F07 and the AC. It ALSO becomes a **lesson** if this reached a customer — then do both: bug note + ledger row.

**"The expert thinks retention findings should weigh state-law exposure more heavily."**
→ **spec-change**, but the *content* is a formula-weight change — you may NOT pick the number. Draft the intelligence-logic.md edit with the weight as `<PROPOSED: expert to confirm>`, note the formula_version bump it implies, and put it squarely in "Needs human."

**"A customer asked if we can score their vendor's notices too."**
→ **idea** (vendor due-diligence mode — it's already parked in 03-ideas; add the demand signal as a note under it rather than duplicating).

**"Why does the report say 'exposure' instead of 'risk of violation'?"**
→ **question.** Answer from business-logic.md §2 and onboarding rule 1. Do not edit anything. If they push back and *want* it changed → that's new feedback, class **guardrail**, and the summary says hard-rule changes need expert + engineer joint approval.

**"The demo crashed when the notice URL redirected to a PDF."**
→ **code-bug** (F01 intake handles PDF; if redirect-to-PDF isn't in the spec's states, it's ALSO a **spec-change**: add the state + an AC). Split into two items.

**"We keep forgetting to update the MOCK TRACKER when we wire a mock."**
→ **lesson.** Recommend the strongest guard: a spec-guard CI check (e.g., PR touching a mocked component must touch the tracker) beats a reminder in a doc. Ledger row Status = Open until the check exists.

**"Marketing wants to say '10,000+ clauses analyzed' on the site."**
→ **guardrail**, hard stop. Hard Rule 7 bans fabricated scale; real counts from the corpus are fine. The edit, if any, is documentation of the *approved phrasing pattern* ("real counts from frozen snapshots only"), plus a firm "Needs human: expert" flag.

## Edge cases

- **Feedback about these docs themselves** (onboarding, playbook, this skill): still spec-change — the onboarding pack and skill files are versioned truth too; expert approves content changes.
- **Feedback that's really a priority call** ("we should build white-label sooner"): not a spec edit — it's a plan change. Edit `00-plan/full-app-roadmap.md` (spec-change class, but call out that release re-sequencing is a founders' decision in "Needs human").
- **Contradictory feedback** (expert said X last month, says not-X today): make today's edit, but the changelog entry must reference the reversal, and the decision-log line should capture *why* it changed — reversals without recorded reasons get re-litigated forever.
- **Feedback you disagree with:** draft it faithfully anyway, then state your concern once, clearly, in "Open questions." You're the scribe with judgment, not the decider.
