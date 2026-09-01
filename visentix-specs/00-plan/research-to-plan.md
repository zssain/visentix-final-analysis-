# Research → Plan

**Version:** 1.0 · 2026-08-31
**Source:** `logs/archive/2026-08/REPORT-LANGUAGE-RESEARCH-2026-08-31.md`
(25 sources, 109 claims extracted, 25 adversarially verified, **10 killed**, 9 survived)

Maps every surviving finding to what it changed, what it still requires, and
what it explicitly does **not** license. Kept because the research is the reason
for several current decisions, and a finding with no plan attached quietly
becomes an opinion.

> **Standing caveat, repeated because it matters:** not one verified source
> concerns B2B SaaS privacy reports. The evidence is UK statutory audit (ICAEW),
> internal audit (IIA), US securities prospectuses (SEC), US intelligence
> analysis (ICD 203), UPL doctrine, and cybersecurity ratings (Bitsight). **Every
> application below is analogical and must be stated as such** — including in
> any spec that cites it.

---

## Shipped

| Finding | What it changed |
|---|---|
| **Disclosed evidence quality** (ICD 203 Tradecraft Standard 1) | **RPT-007 source summary** — per-judgment rests-on + evidence-base strength, plus named strengths and limitations. Frozen into the snapshot, never recomputed. Evidence-base strength is stated *separately from the score* |
| **No document-specific acronyms** (SEC: *"don't create new jargon that's unique to your document"*) | VCI → "Confidence", PGMS → "Privacy programme maturity", `/codex` → `/finding-codes`, house mock codes out of user-facing copy. `scripts/check_acronyms.py` |
| **Observations ordered by significance** (IIA) | **Fixed 2026-08-31.** Findings were sorted *alphabetically by code*, and takeaways/recommendations took `findings[:5]` — so a low-severity `AI-004` displaced a high-severity `SH-002` because A precedes S. Now ordered by severity → score → code, the last for determinism (Hard Rule 6) |
| **Substantiate credibility externally, don't assert it** | Marketing-voice titles flagged: "Trust Language Studio" is promotional for what is an *illustrative* rewrite (A1 in `blocked-work.md`) |

## Required, not yet built

| Finding | Gap | Blocked on |
|---|---|---|
| **Action plans with owner + target date** (IIA 15.1) | Recommendations name no owner and are due never. **The largest structural gap against every assurance skeleton in the research** | Product — does assignment exist at all? Inventing an owner breaks honest-numbers |
| **Distribution list** (IIA) | We have none. For a report designed to be *forwarded*, "who was this issued to" is the reader's first orientation question, and its absence is conspicuous to an audit-literate reader | Product — do we record recipients? |
| **Criticality rating + condition/criteria/cause/effect per observation** (IIA) | We carry severity and evidence. We do **not** carry *criteria* (what was expected) or *effect* (what follows) as structured fields | Schema + expert |
| **Named dispute/appeal path** (Bitsight, open even to non-customers, published resolution times) | Nothing exists — no endpoint, no screen, no process | Product; staffing before code |
| **Quantified band-to-outcome validation** | We assert bands mean something; nothing measures it against outcomes | Expert + data we do not yet have |
| **Published, versioned methodology with change notice** | `/methodology` exists but is not versioned and announces no changes in advance | Cheap; unqueued |
| **Hedging audit** (ICAEW: stacked qualifiers read as high subjectivity) | No guard checks generated prose for piled-up modal verbs | Cheap; a guard like the banned-term filter |
| **Executive summary that selects, not summarises** (SEC) | Ours is generated prose of fixed shape; nobody has measured whether it *orients* | Needs a read-through, not code |

## Adopted as constraints — things the research told us NOT to do

| Rule | Why |
|---|---|
| **Never borrow another vendor's effect size or superlative** | Bitsight's "5x" is commissioned, ~2019-20, and Marsh McLennan measures ~3x on the same question. Take the *pattern* — name the validator, quantify the link, publish cohort size and date — never the number |
| **Quantified bands over verbal hedging** | Trust research (PNAS 2020, replicated 2023): banded uncertainty preserves trust where vague hedging erodes it. But ICAEW: *"No-one would thank auditors for being definitive where genuine uncertainty exists"* — prune stacked qualifiers, never the uncertainty itself |
| **Cite IIA 2024 Standards 11.2 / 15.1, never 2017 IPPF 2420** | The toolkit the research surfaced cites a superseded framework. Citing "2420" to an audit-literate reader would itself read as out of date |
| **An overall engagement rating is optional** | Under the 2024 Standards it appears only as a better practice, not a requirement. Our single headline score is a choice, not a compliance obligation |

## What the research did NOT settle

| Question | Status |
|---|---|
| **PDF presentation** — typography, page density, dial/heatmap conventions, traffic-light vs colourblind-safe, WCAG contrast | **Angle returned nothing.** The one design claim attempted was *refuted 0-3*. OD-17's palette half rests on computation (`check_contrast.mjs`), not on this research |
| **Where the disclosure belongs** — front vs back | No evidence. Our bookend pattern is supported only by *inference* (IIA puts scope limitations inside scope; ICD 203 pairs source summary with judgments). Stated as inference in F05 |
| **Source-summary placement** — appendix vs front matter | Same gap. Currently at the head of the appendix |
| **Forwardability** — what non-buyers actually look for | **No claim survived verification.** Every forwardability decision we make is reasoning, not evidence |
| **A band vocabulary to borrow** | ICD 203's likelihood lexicon was **refuted 0-3** — the most transferable thing in the search, and it did not survive. **OD-14 has nothing off-the-shelf left** |
| **Whether "must" is safe** | The surviving legal test is *applying law to a specific party's facts* — which is what a "must" does in a per-customer report. Three sharper corollaries were refuted 0-3. **This hardened OD-16 rather than resolving it** |

---

## Plan changes this forces

1. **Two new items enter the blocked list**: distribution list, and criticality/criteria/cause/effect as structured fields. Neither was previously tracked.
2. **A methodology-versioning task** joins the unblocked queue — small, and it is half of what makes a published score survive scrutiny.
3. **A hedging guard** joins the unblocked queue, alongside the banned-term filter it would sit next to.
4. **OD-14 and OD-16 are harder, not easier.** Any plan that assumed research would unblock them was wrong; both now need the expert with no borrowable standard behind them.
5. **No design decision may cite this research.** Angle 3 produced nothing verifiable.
