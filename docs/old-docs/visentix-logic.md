# Visentix — How It Works (Logic & Flow)

The mental model behind the screens: how a notice becomes a report, what states things move through, and how the UI maps to the engine. Written so a designer can reason about *why* a screen behaves the way it does, and an engineer can see where the UI hooks in.

---

## 1. The core pipeline

A privacy notice travels through six stages. Every screen is a window onto one of them.

```
INGEST → DECOMPOSE → CLASSIFY → SCORE → BENCHMARK → REPORT → (SME GATE)
```

1. **Ingest** — notice arrives by URL, PDF, or pasted text. (URL fetch is SSRF-protected; PDF parsed defensively.) → *UI: intake form.*
2. **Decompose** — document split into sections, then individual disclosure clauses. → *UI: clause references (`C-118`) that lineage points back to.*
3. **Classify** — each clause mapped to one of 8 domains (`data_sharing`, `tracking_cookies`, `consumer_rights`, `cross_border`, `sensitive_data`, `retention`, `children_teens`, `ai_automated_decisions`) + `other`. LLM with a regex keyword fallback. → *UI: domain eyebrows, heatmap axes.*
4. **Score** — 14 versioned formulas `F-001…F-014` produce exposure/maturity/confidence figures. → *UI: metric grids, score bars, VCI dials.*
5. **Benchmark** — a peer cohort is built by similarity; the org is ranked against it. Cohort size is always reported honestly (`n=30`). → *UI: percentile cells, benchmark section, cohort chips.*
6. **Report** — 12 sections rendered in React, exportable to PDF. → *UI: the report showcase.*
7. **SME gate** — human review flips the report from draft to client-visible.

**Design consequence:** because every figure originates in a specific formula with specific inputs, the UI can *always* show lineage. That's not a nice-to-have — it's what the lineage drawer (DDR-005) is built on.

---

## 2. Data → UI mapping

| Engine concept | Where it surfaces in the UI |
| --- | --- |
| Score + formula ID + inputs + VCI + timestamp | Metric cell → **lineage drawer** |
| Finding code (`TRK-007`) from the fixed catalog | Code chip → **Codex tooltip** + PDF appendix |
| Peer cohort size `n=…` | Percentile cell, benchmark section (**never** inflated to "1,250+") |
| `report_snapshot` (frozen at publication) | **Provenance ribbon**: snapshot ID + formula version + frozen date |
| Trend delta (F-012), `no_prior_history` | Sparklines + ▲/▼ deltas; baseline state on first run |
| Alerts (F-013) | Monitoring **alert center**, severity chips |
| SME decision (Confirm/Edit/Dismiss) | Advisor Note authoring; dismissed findings drop from client report |

---

## 3. The determinism rule (why "pull twice = identical")

The feedback "check consistency if a report is pulled multiple times" is a **first-class trust requirement**, not a bug fix.

- On **publication**, the report is frozen into a snapshot: all scores, all lineage, **and the narrative prose** (both machine and Advisor text, at every reader register).
- On **render/re-pull**, the UI reads the frozen snapshot — it does **not** re-run formulas or re-generate narrative. Two pulls of the same snapshot are byte-identical.
- **Re-scoring** (new data, new formula version) creates a **new versioned snapshot**; the old one is preserved and can always be regenerated identically.
- The **provenance ribbon** exposes which snapshot you're looking at, so "identical" is verifiable, not just claimed.

**Design consequence:** the biggest determinism risk is the LLM narrative. The fix is a logic rule (freeze the text into the snapshot), and the UI's job is to *show* that it's frozen. Never regenerate narrative at render time.

---

## 4. Dual-voice content logic (Analyst / Advisor)

Every finding holds two content layers over the same underlying data:

- **Analyst layer** — deterministic, generated from formula outputs. Score, percentile, VCI, lineage chips. Always available the moment scoring completes.
- **Advisor layer** — the human reading. In the current release it's authored in a **house voice ("The Visentix Privacy Desk")**; later it becomes SME-authored/approved (governance = SME team's call). Phrased strictly in exposure/maturity/benchmark terms — **never** a legal verdict.

The **switch** just toggles which layer renders; both are stored in the snapshot so both are reproducible. The attribution slot is designed to later carry a real reviewer name + credential without a layout change.

---

## 5. State machines the UI must reflect

**Report lifecycle:** `draft → in_review → approved`.

**Gate modes** (who sees what, when):
- `strict` — customer sees nothing until approved.
- `instant_draft` *(default)* — customer sees the draft immediately. **UI:** gold watermark + gold provenance ribbon (DDR-001), *not* a yellow banner.
- `client_reviews` — customer can view the draft and leave comments.

**Finding actions (SME):** Confirm · Edit (title/description) · Dismiss (removed from client report). Every action is captured as a training label — the feedback loop for future models.

**Design consequence:** a report screen must render correctly in all three lifecycle states, and the draft treatment is a *designed* state (watermark + gold ribbon), not an afterthought.

---

## 6. The guardrail (a hard boundary the UI must respect)

A phrasing guardrail runs at report-draft time and **blocks** legal-verdict terms (`violation`, `illegal`, `unlawful`, `non-compliant`, `breach of law`, `guilty`, `liable`, …). Any attempt to output them halts compilation.

- **Copywriting rule:** all UI copy, Advisor Notes, empty states, and especially the future Framework Crosswalk stay in *exposure / maturity / likelihood / benchmark / confidence* language.
- **The guardrail is surfaced positively** as the "Intelligence, not legal advice" mark (DDR-007) — a trust signal for this audience, not a hidden disclaimer.

---

## 7. Roles (who sees which screens)

- **customer** — intake, their dashboard, approved reports (or drafts per gate mode). Sees Monitoring, report showcase, public Codex/Methodology.
- **sme** — review queue, finding actions, exemplar cleaning, approvals. Sees SME Workbench.
- **admin** — console, API health, training stats, gate-mode settings.

Access is enforced server-side (role routing, row-level security, JWT verification). **Design consequence:** the UI never *decides* access — it reflects a role it's given. Design each screen for its role; don't build one screen that tries to be all three.

---

## 8. Honesty rules that shape copy

Three platform rules that the UI must never violate in its text:
1. **Honest numbers** — show real cohort sizes (`n=30 as of 2026-06-19`); low confidence flagged, never hidden. No "1,250+", no fabricated metrics.
2. **No score without lineage** — if a figure appears, its lineage must be reachable.
3. **Reproducibility** — what you show must trace to a snapshot.

These aren't legal fine print — for this audience they're the product. The UI's job is to make them *visible and beautiful*, which is the whole thesis of the design direction.
