# Visentix — Screen Specs

Screens for the next release and the near roadmap. Order reflects build priority. Each spec is written for a UI designer: purpose, layout, key components, and states — not database detail (see `visentix-logic.md` for that).

**Recommended build order:** Advisor Note component → Continuous Monitoring dashboard (hero) → report showcase upgrade → Finding Codex → Methodology page → Quarterly Report reader → SME Workbench v2 → Framework Crosswalk (held for Carlos).

---

## 1. Advisor Note component  ·  *built — see `visentix-advisor-note.html`*

The novel, ownable piece. A single finding rendered two ways behind one switch.

- **Provenance ribbon** (top): snapshot ID (mono), formula/version + frozen date, Reproducible mark.
- **Header**: finding code chip (hover → Codex tooltip) + serif title + domain eyebrow.
- **Analyst view**: 3-up metric grid (Exposure / Cohort percentile / Confidence-VCI) with score bars; lineage chip row. Score is tappable → lineage drawer.
- **Advisor view**: gold left-ruled note — Fraunces italic lede, warm body, attribution ("The Visentix Privacy Desk") + reserved reviewer slot.
- **States**: `analyst` / `advisor`; `approved` (teal ribbon) / `draft` (gold ribbon + diagonal watermark).
- **Reused on**: the report's Disclosure Findings section, the Monitoring alert detail, and the SME Workbench.

---

## 2. Continuous Monitoring dashboard  ·  *hero of the release*

**Purpose.** Make the platform feel *alive* — the difference between "I got a report once" and "this watches the landscape for me." This is what convinces evaluators it's a real platform, not a one-shot tool. Surfaces the trend/alert logic (F-012 Trend Delta, F-013 Alert Escalation).

**Layout (desktop).**
```
┌───────────────────────────────────────────────────────────┐
│  SiteNav (navy)                                            │
├───────────────────────────────────────────────────────────┤
│  Org header · live-dot "Monitoring active" · provenance    │
├──────────────────────────────┬────────────────────────────┤
│  Overall Intelligence Score  │  Change feed (chronological)│
│  big figure + trend sparkline│  · notice updated           │
│  ▲/▼ delta vs last snapshot  │  · score moved 41→38        │
├──────────────────────────────┤  · new regulator signal     │
│  Domain scorecards (8)       │  · cohort re-benchmarked     │
│  small sparkline each,       ├────────────────────────────┤
│  color by score band         │  Alert center               │
│                              │  High / Medium, each opens  │
│                              │  an Advisor Note            │
└──────────────────────────────┴────────────────────────────┘
```

**Key components.**
- **Score-over-time sparklines** — one hero line for Overall, small ones per domain. Tabular figures. Trend delta uses ▲ teal / ▼ red, and reports `no prior history` cleanly on first assessment (don't fake a flat line).
- **Change feed** — reverse-chronological, each entry timestamped and snapshot-linked. Types: notice changed, score moved, regulator signal, cohort re-benchmarked. This is the "it's watching" proof.
- **Alert center** — High/Medium severity chips; opening one reveals the Advisor Note for that finding (reuse component #1).
- **Live-dot** — existing `.live-dot` emerald pulse = monitoring active.

**States.** First run (`no_prior_history` — hide deltas, show "baseline established"); quiet period (no changes — "No changes since [date]" as a calm empty state, not an error); active alert (High badge in nav).

**Mobile.** Stacks: score → domain cards (2-up) → change feed → alerts.

---

## 3. Report showcase upgrade  ·  *presentation work on existing 12-section report*

**Purpose.** Answer "why trust the people behind this?" Mostly styling on a surface you already have. Frame the 12 sections like an **audit-firm engagement deliverable**.

**Add around the existing sections.**
- **Cover** — Fraunces title, gold hairline rules, org metadata, overall score + VCI dial, provenance ribbon. Should look bound.
- **Scope & limitations** + **methodology statement** — short audit-style framing block near the front ("what this assessment does and does not do"). This scaffolding is *why* firm reports feel authoritative.
- **Basis of findings / signed-off-by** — reserved block for reviewer name + credential (empty house-voice for now, per DDR-003).
- **Every number** gets the lineage-drawer affordance (DDR-005); **every code** gets the Codex tooltip (DDR-006).
- **Benchmark Language Comparison** — a **clause comparison slider**: drag between "your clause" and the exemplar, with diffs highlighted. Memorable, and directly shows "we see this → you do this."
- **Reader-register toggle** — Executive / Practitioner / Plain-language (hold final names for Carlos). Same data, three renderings; both registers frozen into the snapshot.

---

## 4. Finding Codex  ·  *the TRK-007 dictionary*

**Purpose.** Governed, browsable glossary of every finding code. Public-facing candidate (marketing + trust). Source of truth for every in-report tooltip.

**Layout.** Left rail = domain filter (the 8 taxonomy domains + other). Main = searchable code list; each entry expands to canonical definition, the exposure it signals, an anonymised example pattern, and related codes. Codes shown in the same navy chip used in reports for consistency.

**States.** Search empty ("Search 40+ finding codes…"); no result (offer nearest domain, don't dead-end); code deep-link (each entry has its own URL so tooltips and PDFs can point to it).

---

## 5. Methodology / About page  ·  *"why we make what we make"*

**Purpose.** The marketing note made real. Turn the platform's discipline into the sales pitch for a skeptical audience.

**Content blocks.** The 14 formulas as a dignified list (ID + plain-language purpose, not the math) · the guardrail explained as a *principle* ("intelligence, not verdicts") · the SME review gate shown as a workflow · reproducibility explained (snapshots, lineage) · the people/company story (Visentix + SOLRAC). Fraunces headlines, generous whitespace, gold accents — this page should feel like a firm's "our standards" page.

---

## 6. Quarterly Global Privacy Intelligence Report reader  ·  *public marketing edition*

**Purpose.** The redacted, industry-wide edition is the top-of-funnel marketing engine (service model #4 in the framework). Gorgeous, public, shareable.

**Layout.** Editorial: full-bleed Fraunces cover, sector benchmark charts (Recharts), regulator heatmap, trend callouts. Honest cohort sizes always visible (`n=…`). A quiet "Assessed by Visentix" mark and a CTA into the platform.

---

## 7. SME Workbench v2  ·  *the review team's tool*

**Purpose.** Where Confirm / Edit / Dismiss happens and training labels are captured. Not customer-facing, but it's where the human voice gets authored.

**Layout.** Three-pane: source clause (left) · auto-finding + Analyst view (center) · Advisor Note editor + Codex reference (right). Confirm / Edit / Dismiss actions; dismissed findings drop from the client report. Show training-label stats (how many confirmed/edited/dismissed) as a quiet productivity readout. De-identification checker blocks exemplar approval if names/emails/URLs remain.

**States.** Queue empty; finding in edit; exemplar failing de-id check (block + highlight offending token).

---

## 8. Framework Crosswalk explorer  ·  *held for Carlos*

**Purpose.** Map the 8 domains + finding codes to NIST Privacy Framework / ISO 27701 / GDPR-CCPA references.

**Design now, copy later.** Build the explorer UI (domain → framework references, side by side). **Hold all mapping copy** until Carlos confirms it stays *descriptive*, never a compliance verdict (guardrail risk). Ship the shell; wire the language when approved.

---

## Cross-screen furniture

- **Provenance ribbon** — required on every report/dashboard surface (DDR-004).
- **Lineage drawer** — global; any score, any screen.
- **Codex tooltip** — global; any finding code, any screen.
- **View switch** — anywhere a finding appears with a human layer.
- **Live-dot** — monitoring surfaces only.
