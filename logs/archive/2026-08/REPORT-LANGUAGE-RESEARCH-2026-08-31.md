# Report Language & Presentation — Market Research
**Date:** 2026-08-31 · **Method:** 5-angle web research, 25 sources fetched, 109 claims extracted, 25 adversarially verified (3-vote), **10 killed**, 9 findings survived synthesis.
**Status:** Evidence input. No spec has been changed on the basis of this document.

## How to read this
This research was run adversarially: every claim got three independent verification votes and needed 2/3 to survive. **Ten of twenty-five claims were killed**, including several that sounded authoritative. Killed claims are listed in full at the bottom — they matter as much as the survivors, because three of them are things we might otherwise have adopted.

**The dominant weakness is domain transfer.** Not one verified source concerns B2B SaaS privacy assessment reports. Evidence comes from UK statutory audit (ICAEW), internal audit (IIA), US securities prospectuses (SEC), US intelligence analysis (ICD 203), US court self-help/UPL doctrine, and cybersecurity ratings (Bitsight). Every application to our report is **analogical** and should be stated as such in any spec change.

---

## What survived — and what it means for Visentix

### 1. Plain, positive, lightly qualified *(high confidence)*
ICAEW's Auditor Reporting Lab (May 2026), on commissioned discourse analysis by Prof. Veronika Koller (Lancaster), recommends: emphasise what *was* done rather than defensively what was not; short simple sentences; avoid hyperbole; prune stacked qualifiers.

It names **pervasive hedging** — piled-up modal verbs and conditionals like *"might or might not emerge"*, *"if it was concluded that a breach had occurred"* — as producing *"unnecessarily complex sentences"* and *"the impression of a high level of subjectivity"*.

But it draws the line explicitly: *"No-one would thank auditors for being definitive where genuine uncertainty exists."*

Trust research surfaced during verification (van der Bles et al., PNAS 2020; RSOS 2023 replication; Dries et al. 2024) sharpens this: **quantified/banded uncertainty preserves trust where vague verbal hedging erodes it.**

> **Visentix read:** This is direct support for band-first presentation and against hedge-stacking. It supports the no-negative-framing rule already in `business-logic.md` §, and it argues our honest-absence strings ("Not recorded") are correct in kind but should be stated once, cleanly, not defensively repeated.

---

### 2. Don't assert your own credibility — substantiate it *(medium confidence)*
ICAEW: *"the use of 'legitimation', often involving hyperbole, can inadvertently undermine the value of work performed in the eyes of a sceptical reader — exactly the opposite of what is intended... when applied selectively it may also give the impression that less effort was exercised in other areas."*

Verification attached two limits: this is practitioner observation, **not measured reader response**; and standard assurance vocabulary ("in our professional judgement") is *not* the target — self-congratulatory effort and scale claims are ("extensive", "deep experience", "global team").

> **Visentix read:** Rated medium and domain-untested — B2B vendor reports conventionally *do* carry methodology framing. The defensible move is to substantiate credibility **externally** (published method, named validators, disclosed cohort) rather than adjectivally. That is a marketing-copy constraint more than a report constraint.

---

### 3. The credible-report skeleton is the assurance-engagement structure *(high confidence)*
From the IIA Audit Report Writing Toolkit:

| Component | Note |
|---|---|
| Objective | explicit |
| **Scope — including named scope limitations** | limitations sit *inside* scope |
| Background | |
| Conclusions | |
| Observations **ordered by significance** | each with a criticality rating + condition/criteria/cause/effect |
| Recommendations | |
| Action plans | with **owner and target date** |
| Distribution list | |

Seven mandatory quality attributes: *"accurate, objective, clear, concise, constructive, complete, and timely"*, with *"content and level of detail... determined by the needs of the audience"* and explicit permission for *"different formats/versions that are customized for the audience"*.

**Currency correction — important.** The toolkit cites the superseded 2017 IPPF. Since 9 January 2025 the operative source is the **2024 Global Internal Audit Standards**: the seven attributes are now **Standard 11.2**, required final-engagement content is **Standard 15.1**. Citing "Standard 2420" to an audit-literate third-party reader would itself read as out of date. Also: under the 2024 Standards an **overall engagement rating is optional**, appearing only in Considerations for Implementation.

> **Visentix read:** Our six-part structure already approximates this. Two gaps: we have no **action plans with owner and target date**, and no **distribution list**. The audience-customisation permission is direct support for a board version vs a specialist version.

---

### 4. Third-party credibility rests on disclosed evidence quality *(high confidence)*
ICD 203 Analytic Standards (2015, amended 2022, in force), Tradecraft Standard 1: products *"should identify underlying sources and methodologies upon which judgments are based"* and describe *"accuracy and completeness... age and continued currency of information... source access, validation, motivation, possible bias, or expertise."*

**Source summary statements** are *"strongly encouraged"* to give *"a holistic assessment of the strengths or weaknesses in the source base and explain which sources are most important to key analytic judgments."*

*(Precision note: the standard's own verb is "should".)*

> **Visentix read:** This is the analytic-standards analogue of our provenance ribbon and cohort label — and it validates them strongly. It also asks for something we don't do: a **holistic statement of which evidence drives the key judgments**, not just per-number lineage.

---

### 5. The legal-advice line: options, not selection *(medium confidence)*
Greacen, *Legal Information vs. Legal Advice: A 25-Year Retrospective*, Judicature (Duke Law, 2022): *"Staff can inform a litigant of his or her options and the steps needed to carry out an option. Staff cannot suggest which option the litigant should pursue."* Echoed in Minnesota, Indiana and California Judicial Council self-help guidance (updated 2024).

**⚠ Three sharper corollaries were REFUTED 0-3 and must not be relied on:**
- the "who/what/when/where/how vs should/whether" vocabulary test
- "information is facts about the law, advice is a recommendation"
- "the dichotomy is the accepted US standard of practice"

The stricter general UPL test — **applying law to a specific party's facts** — is the one that actually bites on a per-customer assessment. Even a tailored options list can edge toward advice if the report asserts what the law requires of *that customer's* particular facts. Greacen concedes the line is unclear in many situations; Yale Law Journal (*The Overreach of Limits on Legal Advice*) argues it is drawn too restrictively.

> **Visentix read:** This is the finding with the most direct bearing on **OD-16 (must vs should modality)** — and it cuts *against* the simple reading. "Must = mandatory" phrasing asserts what the law requires of this customer's facts, which is the exact test that bites. **OD-16 should not be closed on this research alone; it needs the expert.**

---

### 6. What makes a score survive scrutiny *(high confidence)*
Bitsight publishes, and demonstrably operates:
- **How the score is constructed** — asset mapping, what data types are evaluated
- **A named dispute/correction/appeal body** — the Policy Review Board, *"available to all rated entities"*, and *"even if an organization is not a Bitsight customer, they are able to challenge results"*
- **A published case log** (to Oct 2025) adjudicating both data accuracy (stale DNS, spoofed domains, breach attribution) **and methodology** (SMTP/SSLv3 grading; detected-vs-vulnerable comparison model), with SLAs (target 7–10 business days; 2023 averages 4 days disputed assets, 6 disputed findings)
- **Quantified band-to-outcome validation** — companies rated ≤500 *"almost 5 times as likely to suffer a publicly-disclosed data breach"* than those ≥700, attributed to AIR Worldwide / IHS Markit, ~27,000 companies, two-year window

### 7. …and why not to copy their claims *(medium confidence)*
Verification surfaced three live disputes:
1. Those validations were **commissioned by Bitsight** and date to ~2019–2020 — "third-party" means externally conducted, not disinterested or peer-reviewed.
2. **The effect size is not a constant.** Marsh McLennan reports under 1% breach probability at 700+ vs roughly 3% below 500 — about **3x, not 5x**.
3. The superlative *"only security rating company with third-party validation"* is contested, with SecurityScorecard asserting Bitsight's *"scoring method lacks public validation"*.

> **Visentix read:** Take the **pattern**, never the numbers. Publish cohort size and data date; express results as **bands with stated ranges** rather than a bare point number; disclose small-sample/low-confidence explicitly rather than rendering a confident-looking score.
>
> This is strong support for the turn-1 instruction that **the band leads the number**, and for our existing low-confidence cohort label. The unbuilt piece is an **appeal path** — we have no way for a rated organisation to challenge a finding.

---

### 8. Cover and executive summary: orient and select, don't summarise *(high confidence)*
SEC Plain English Handbook (1998; basis of in-force 17 CFR 230.421(b)-(d)):

- *"A cover page should be an introduction, an inviting entryway... not telling everything all at once... you'll need to strip away much of what is conventionally placed there, but which is not required."*
- *"A summary should orient the reader, highlighting the most important points... Many summaries now seem as long as the document itself and consist merely of paragraphs copied straight from the body."*
- *"introducing defined terms on the cover page and in the summary discourages many readers from getting beyond the first pages."*
- *"don't create new jargon that's unique to your document in the form of acronyms or other words."*

Rule 421(d) binds (for a prospectus's cover, summary and risk factors): short sentences; definite, concrete, everyday words; active voice; tabular/bullet presentation for complex material; no legal jargon or highly technical business terms; **no multiple negatives**.

*(Honest limits: the handbook says it is published "only for your general information"; the doctrine is cut the **non-required** conventional filler, not cut everything; and the SEC frames the goal as **clarity, not brevity**.)*

> **Visentix read:** Direct, near-verbatim support for the acronym rule already in `design-system.md` §. Established terms (GDPR, CCPA) are fine; **vendor-coined shorthand the reader must memorise is not** — which indicts **PGMS, VCI and DDR/DIR codes** anywhere a customer can see them. Our exec summary should shrink, not grow.

---

## ⚠ The biggest result: the design angle returned nothing

**Angle 3 (PDF presentation & design) is effectively unanswered**, and so is the placement half of angle 5.

The single design-specific claim attempted — that the SEC prescribes serif body with sans-serif headings, ≤2 typefaces, 10–12pt body, ragged-right setting and no all-caps blocks — was **REFUTED 0-3** and must not be repeated as SEC guidance.

Nothing verified was obtained on:
- typography or page density for print/PDF
- **traffic-light risk colour vs colourblind-safe practice and WCAG contrast** ← *this is OD-17, still open*
- heatmap, dial or gauge conventions
- benchmark visuals
- **front-vs-back placement of the disclosure statement** ← *we have already shipped a decision here*

The nearest supported inference is **structural, not visual**: both the IIA (scope limitations inside the scope section) and ICD 203 (source summary accompanying the judgments) place limitations **forward, with the method**. That supports a front scope/method statement plus a conventional back-page disclosure — i.e. **the bookend pattern we already built** — **but it is inference, not evidence.**

---

## Killed claims (do not cite these)

| Claim | Vote | Purported source |
|---|---|---|
| SEC prescribes serif body / ≤2 typefaces / 10–12pt / ragged-right / no all-caps | 0-3 | SEC Handbook |
| ICD 203 mandates two fixed 7-term likelihood scales with numeric probability bands | 0-3 | ICD 203 |
| ICD 203 requires confidence and likelihood kept in separate sentences | 0-3 | ICD 203 |
| ICD 203 requires typographic separation of evidence from judgment; linchpin assumptions; change-indicators | 1-2 | ICD 203 |
| The legal information/advice dichotomy is the accepted 25-year US standard of practice | 0-3 | Judicature |
| "Information = facts about law; advice = a recommendation" | 0-3 | Judicature |
| The "who/what/when/where/how vs should/whether" vocabulary test | 0-3 | Judicature |
| plainlanguage.gov makes audience-fit the first rule | 0-3 | plainlanguage.gov |
| Plain Writing Act framed as obligation-and-benefits comprehension requirement | 0-3 | plainlanguage.gov |
| Active voice prescribed because it assigns responsibility; passive is the biggest defect | 0-3 | plainlanguage.gov |

**The ICD 203 likelihood-lexicon kill is the costly one.** A standardised probability lexicon would have been the ready-made answer for expressing severity and confidence consistently — it was the most directly transferable thing in the whole search, and it did not survive. We still need a verified basis for band vocabulary. That keeps **OD-14 open**.

---

## Open questions this research did not close
1. PDF presentation — typography, page density, cover content, dial/heatmap conventions, traffic-light colour vs colourblind-safe palettes and WCAG contrast. **(OD-17)**
2. Where a "not legal advice" disclosure conventionally sits in high-value commercial reports, and whether front-loading depresses perceived value. Our bookend decision currently rests on inference.
3. What actually drives **forwardability** — no claim on this survived verification.
4. Whether regulators or professional bodies (state bars, ICO/EU DPAs, IAPP) say anything specific about non-lawyers publishing regulatory findings, beyond the court-staff UPL analogy. **(bears on OD-16)**
5. Given the ICD 203 lexicon was refuted, what verified alternative exists for expressing severity and confidence in bands. **(OD-14)**

---

## Recommended next steps
- **Do not** run `spec-update` on this yet. Findings 1, 3, 4, 6, 7 and 8 are ready to inform spec edits; findings 2 and 5 need the expert first.
- **Two additions are clearly supported and currently missing:** action plans with owner and target date (IIA), and a holistic source-summary statement naming which evidence drives the key judgments (ICD 203).
- **One gap is strategic, not editorial:** we have no appeal or dispute path for a rated organisation. Bitsight treats that as core ratings governance, open even to non-customers.
- **Angle 3 needs a second, narrower research pass** before OD-17 can close.
