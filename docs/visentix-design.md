# Visentix — Design Decision Records (DDRs)

Design decisions for the next release, aimed at Carlos's circle of **regulators, legal officers, and advisors**. These are the visual/interaction equivalent of ADRs: each one pins a choice, why it was made, and what we rejected — so the decision can be defended later, the same way this audience defends its own findings.

Design tokens are unchanged from the existing system (Deep Navy `#09234F`, Executive Blue `#005FA3`, Teal `#55C7B3`, Soft White `#F7F8FA`, Warm Gray `#D9DDE2`, Subtle Gold `#C8A46A`, plus `#F87171` red / `#10b981` emerald for status). Fonts: Fraunces (serif/display), Inter (UI), Source Sans 3 (data/numerics). These DDRs govern *how* those tokens are used, not the tokens themselves.

---

## Design principle for this audience

Consumer "premium" is gloss and motion. **Legal-and-regulator "premium" is confident stillness plus evidence everywhere.** Lawyers trust footnotes. So every distinctive move points at one thing: *provenance made beautiful*. Motion exists only to reveal evidence, never to decorate.

---

## DDR-001 — Draft state uses a gold watermark, not a yellow banner

- **Context.** The MVP shows unreviewed reports with a yellow warning banner (`instant_draft` gate mode). For a legal audience, yellow reads as *error / broken*, which cheapens a deliverable meant to feel like a firm's work product.
- **Decision.** Replace the yellow banner with (a) a subtle **gold diagonal watermark** "DRAFT — PENDING EXPERT REVIEW" behind the content, and (b) a **gold-tinted provenance ribbon** at the top of the artifact. Approved state uses the teal "Reproducible" ribbon.
- **Rationale.** Gold reads as *provisional and prestigious* rather than *broken*. Same information, opposite emotional register. The watermark is unmistakable up close but never shouts.
- **Rejected.** Yellow banner (reads as error); red (reads as failure); no indicator at all (unacceptable — draft status must be legible at a glance for a legal reader).

## DDR-002 — Dual-voice content model: the Advisor Note + view switch

- **Context.** Feedback asked for a "computer response and a human response" that "feels like a privacy expert, regulator, and lawyer."
- **Decision.** Every finding carries two layers behind one **Analyst / Advisor** switch.
  - **Analyst view** — the machine reading. Source Sans, tabular figures, bordered metric grid, lineage chips. Cold, precise, deterministic.
  - **Advisor view** — the human reading. Fraunces italic lede, warm body copy, a thin **gold left-rule**, and an attribution block. No legal verdicts.
- **Rationale.** The visual inversion (data-grid vs. gold-ruled prose) *is* the message: two ways of knowing the same finding. The switch is the most memorable moment in the demo.
- **Rejected.** Showing both stacked always (dilutes the contrast, doubles the scroll); tabs labelled "Data / Summary" (generic — "Analyst / Advisor" names the two personas the audience recognises).

## DDR-003 — House voice fills the attribution slot now; SME name later

- **Context.** We want the Advisor Note to look *authored* today, but governance of who authors it is Carlos's/SMEs' call later.
- **Decision.** Ship a named house persona — **"The Visentix Privacy Desk"** — in the attribution slot. The component reserves a visible **"reviewer & credential" slot** directly beneath it, styled but empty, ready to hold a real SME name once expert review is enabled.
- **Rationale.** Solves the demo (looks human-authored) without pre-empting the governance decision. The empty slot is honest and forward-looking rather than a placeholder that looks unfinished.
- **Rejected.** Anonymous "Summary" (loses the human signal); inventing fake reviewer names (dishonest to a legal audience — a fast way to lose trust).

## DDR-004 — Provenance ribbon is a required element on every report/dashboard surface

- **Context.** "Consistency if a report is pulled multiple times" — the trust risk is that a regenerated report reads differently.
- **Decision.** A **provenance ribbon** appears on every report page and dashboard: monospace **snapshot ID** (`S-2041`), **formula/version + frozen date**, and a **"Reproducible" mark** (teal when approved, gold when draft). Pulling the same report twice must be byte-identical, and the ribbon says so.
- **Rationale.** It's the firm's engagement stamp. For this audience it does more selling than any animation because it says "we can defend every digit and reproduce it on demand."
- **Rejected.** Burying provenance in a footer or an "info" modal (evidence should be ambient, not hunted for).

## DDR-005 — Click-any-number lineage drawer

- **Context.** "No score without lineage" is already a platform rule; the UI wasn't surfacing it.
- **Decision.** Any score is tappable (dotted underline affordance). Clicking slides a right-hand **lineage drawer**: formula ID + version, input references (clause, regulator, jurisdiction), cohort size, VCI, snapshot ID, frozen timestamp, and the formula in plain form.
- **Rationale.** This single interaction sells a regulator. It turns "trust our number" into "here's exactly how we got it." Motion is justified because it *reveals evidence*.
- **Rejected.** Tooltip-only (too small for the lineage detail); separate "methodology" page (breaks the reader's flow — evidence should be one tap from the claim).

## DDR-006 — Finding-code tooltips everywhere; the Codex is the source of truth

- **Context.** "Dictionary of shortforms like TRK-007." Codes without a governed glossary are a liability.
- **Decision.** Every finding code (`TRK-007`, `SH-002`, `RT-003`…) is a hover/focus target that shows its canonical Codex definition inline, and every PDF auto-appends the relevant Codex entries as an appendix. The **Finding Codex** screen is the single browsable source of truth.
- **Rationale.** Auditing firms live and die by their glossary. A governed code dictionary is proprietary methodology, not just UX convenience — and it's IP-relevant per the framework doc.
- **Rejected.** Leaving codes undefined in-context (forces the reader to leave the report to understand it).

## DDR-007 — The guardrail is a visible trust mark, not a hidden disclaimer

- **Context.** The platform never issues legal verdicts (banned-term guardrail).
- **Decision.** A small, quiet **"Intelligence, not legal advice"** mark sits at the foot of findings and reports — designed, not buried in legalese.
- **Rationale.** A consumer would ignore it; a lawyer respects that we understand our own lane. It converts a disclaimer into a *trust signal*.
- **Rejected.** Long legal disclaimer footer (nobody reads it, and it reads defensive); no mark at all (misses a chance to signal discipline).

---

## Quality floor (applies to every screen)

Responsive to mobile · visible keyboard focus on all interactive elements · `prefers-reduced-motion` respected (evidence still reachable, just without the slide) · numerics always tabular (`font-variant-numeric: tabular-nums`) so figures align in tables · gold reserved for *provisional/premium*, teal for *verified/live*, red only for genuine low-score exposure.

## Open decisions (waiting on Carlos)

- **Framework crosswalk language.** Any mapping to NIST/ISO/GDPR must stay *descriptive* ("relates to CCPA §1798.120"), never *verdict* ("complies with"). Design the explorer, hold the copy until Carlos confirms the guardrail extension.
- **Reader registers.** Executive / Practitioner / Plain-language toggle — approved in principle; final register names and defaults pending.
