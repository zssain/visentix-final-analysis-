# UI and app-truth audit — 2026-09-08

## Verdict and scope

The application, documentation and UI are **not fully consistent**. The public
website integration is implemented, but the issues below remain open. This is a
local audit, not a production readiness certificate or a live corpus census.

Pulled `origin/main` with fast-forward from `6e2710a` to `2c7dc5e` before work.
Changes are on `codex/F08-F10-public-site-audit`. The owner approved a single
frontend with public pages and an authenticated workspace, then deferred website
redesign and prioritized the actual app UI. No backend/data changes were made.

Authority: the four foundation specs define intended behavior; feature specs
and approved amendments define acceptance criteria. Code establishes implemented
behavior; test results establish only the tested behavior. Dated deployment notes
do not prove today's deployment state. This audit records discrepancies without
changing governed formulas, thresholds, permissions, or historical snapshots.

## Evidence and coverage

[Browser evidence](2026-09-08-ui/evidence.json) records 26 route/role combinations
at 375, 768 and 1280px: 78 captures, no uncaught page errors in those states.
This includes all canonical page surfaces in the route registry, the eight
imported website pages, and representative role access. Redirects and role
boundaries are additionally covered by the integration tests.

Browser requests were intercepted: empty lists, explicit unavailable responses,
one monitoring baseline, and the existing report test fixture. Authentication
was a synthetic local session, not a real login. Preview-only surfaces were
enabled for inspection; production masks remain unchanged. No real API writes,
notices, customer records, or credentials were used. Additional dark-theme checks
covered assessments, intake, report and partner at mobile/desktop widths. External
fonts were blocked, so screenshots use fallback fonts. These are responsive and
selected interaction checks, not exhaustive accessibility certification or every
populated workflow state. Selected screenshots are retained alongside the JSON.

| Surface | State examined | Outcome / remaining concern |
| --- | --- | --- |
| Assessments + monitoring | Empty list, baseline, unavailable secondary data | Responsive; misleading stable/no-alert messaging; multiple empty cards repeat the intake action |
| Intake | Form, profile fields, analysis scope | Responsive; long mobile form; actual submit/processing covered by existing tests, not live service |
| Report | Existing 12-section fixture, draft | Horizontal overflow; score/benchmark rendering concerns below |
| Workbench | Empty queue + source review | Responsive; live populated review and approvals not exercised |
| Admin | Empty/unavailable jobs and stats | Responsive; no real batch trigger or gate change performed |
| Screening | Empty jobs + table source review | Responsive empty state; analyst access and score coloring mismatch |
| Partner | Empty clients + dialog source review | Responsive; custom dialog lacks shared modal behavior |
| Rewrite | Empty/error inputs + source review | Responsive; displayed heading differs from registry |
| Quarterly | No publication + source review | Responsive; rejected network request lacks completion handling |
| Methodology | Anonymous view | Static descriptions and unusable metadata request |
| Finding Codes | Anonymous view | Authentication failure reads like an empty catalog |
| Vendors / Crosswalk / Trust | Preview surfaces | Responsive sampled states; mocked/preview status must remain visible and gated |
| Login / Unauthorized / Privacy / Terms | Public/denied states | Responsive; Unauthorized does not use shared PageHeader |
| Eight website routes | Anonymous and signed-in navigation | Integrated, responsive; no website redesign attempted |

## Findings, in remediation order

### A01 — P1: monitoring can publish scores below the confidence floor (F04/F07)

[monitoring.py](../../app/services/monitoring.py), `get_trend`, copies stored
scores into `overall` and domain series before testing only for non-null overall.
It returns confidence separately without suppressing values below 40.
`get_alerts` also returns the escalation score independently of confidence and
supplies `F-013_v1` when recorded formula lineage is absent.
[MonitoringHero](../../web/src/pages/customer/MonitoringHero.tsx) does not supply
the missing customer-facing suppression. This contradicts Hard Rules 4/5 and the
no-invented-lineage rule. Code-path finding; no claim that a live tenant currently
has a below-floor row. Fix at the response boundary and test low/missing confidence,
including domain values and alerts; preserve source rows.

### A02 — P1: peer distribution mixes score and percentile coordinates (F05/F04)

[PeerDistribution](../../web/src/report/sections/PeerDistribution.tsx) plots
`grid`/`peers.x` with the same x-scale as the organization's `percentile` and its
percentile confidence interval. The [producer](../../app/services/scoring/peer_distribution.py)
computes density over raw scores and includes a separate `org_score`. The UI type
omits that field and labels the axis as percentile. For example, a score of 60 at
the 85th percentile is marked at x=85 on a score-density curve. The missing-alpha
fallback also prints a 95% interval without recorded alpha. Resolve the visual
contract in the F-015 amendment before changing presentation; do not calculate
new statistics in React or alter frozen data.

### A03 — P1: draft reports overflow at every tested width (F05)

The report fixture produces document widths 2680/2922/3056px at viewport widths
375/768/1280px. [The watermark](../../web/src/index.css) rotates a pseudo-element
spanning the full report height without containing its overflow. Disabling only
that pseudo-element in the browser reduces desktop width to 1280px, confirming
its contribution. Mobile still measures 632px: content's minimum width is a
second problem. Constrain decorative overflow and repair mobile layout/min-width
at the source; do not hide meaningful tables globally. Recheck all report sections
and PDF layout with long organization names and populated evidence.

### A04 — P1: immutable snapshot PDF bytes fail the existing gate (F05)

`tests/test_pdf_determinism.py::test_frozen_snapshot_pdf_is_byte_identical` failed
in the isolated baseline run. This is already tracked as OD-18, not introduced by
the website integration. The reproducibility promise is stronger than the
observed gate. Keep the failure open and diagnose rendering determinism; do not
weaken the test or silently amend the promise.

### A05 — P2: absence and cohort protections are incomplete in report renderers

[Cover](../../web/src/report/sections/Cover.tsx) passes absent `overall_score` as
zero to ScoreDial. A missing value must remain absent. [BenchmarkIntelligence](../../web/src/report/sections/BenchmarkIntelligence.tsx)
accepts any positive cohort size for percentile and peer-marker display, including
1–9. [CohortLabel](../../web/src/report/CohortLabel.tsx) only cautions below 10;
10–19 relies on optional `methodology.low_confidence` elsewhere in the section.
The foundation requires low-confidence treatment below 20 and suppresses
comparative statements below the governed floor. Server suppression may protect
current payloads, but these renderers do not safely handle legacy or incomplete
payloads. Define and test those states without generating replacement figures.

### A06 — P1: methodology and dictionary do not meet their public data contract (F08)

[Methodology](../../web/src/pages/Methodology.tsx) calls authenticated `api.get`
for `/formulas/method-version`; the backend registers the public endpoint at
`/api/formulas/method-version`. Consequently the public page cannot load that
metadata as written. Its fourteen descriptions are a local constant rather than
the F08 AC-4 data source. Its confidence description conflates report confidence
and per-object confidence, and its universal expert-review statement ignores the
supported instant-draft mode.

[FindingCodex](../../web/src/pages/FindingCodex.tsx) is publicly routed but calls
a JWT-required client and protected backend route. Errors are swallowed and read
as zero codes/no matches. F08 AC-3 deep-link expansion is also absent; the legacy
redirect does not preserve the hash. Resolve the intended public catalog response
contract before changing backend access, then distinguish unavailable from empty.
The new website Resources page explicitly describes the current sign-in limit.

### A07 — P1: the specified screening analyst cannot authenticate (F10/F19)

F19 and the bulk router allow `admin | analyst`, but
[authentication.py](../../app/services/authentication.py) accepts only customer,
sme, admin and partner_admin; frontend roles/registry also exclude analyst.
Thus the analyst journey is not delivered. Decide whether analyst is a supported
role and then reconcile authentication, tenancy, permissions, UI and tests together.
Do not simply relax the route guard.

### A08 — P2: unavailable monitoring data becomes reassurance (F07)

[MonitoringHero](../../web/src/pages/customer/MonitoringHero.tsx) catches endpoint
errors as null, then renders the feed/alert empty states when another panel has
data. A baseline can coexist with failed event/alert calls yet say the monitored
notices are stable and there are no active alerts. A baseline alone does not prove
that scheduled monitoring ran. Distinguish unavailable, not configured, baseline,
and a successful empty response. Existing alert cards also do not implement the
specified Advisor Note/drill-down journey.

### A09 — P2: keyboard navigation reaches the closed mobile sidebar (F10/design)

At 375px, Tab reaches hidden Assessments/Intake/Quarterly links at x=-244px.
[App.tsx](../../web/src/App.tsx) translates the mobile rail offscreen without
removing it from keyboard navigation. Use the shared accessible drawer primitive
with focus restoration and modal behavior. Its all-caps navigation group headings
also conflict with DDR-010's divider/spacing treatment.

### A10 — P2: screening reverses maturity color meaning; sort headers are mouse-only

[BulkAnalysis](../../web/src/pages/bulk/BulkAnalysis.tsx) sends `r.overall` through
`scoreBandColor`, the exposure palette, although F-010 is maturity. Higher maturity
can therefore receive high-exposure coloring. Resolve polarity from the governed
metric definition. Sortable table headings use `onClick` on `th` without keyboard
controls; use buttons and expose sort direction.

### A11 — P2: partner modal bypasses shared accessible dialogs

[PartnerPortal](../../web/src/pages/partner/PartnerPortal.tsx)'s New Client overlay
is custom nested divs. It lacks dialog semantics, focus trapping and Escape handling,
contrary to the Radix requirement. Replace it with the shared dialog without
changing tenant creation semantics. Populated partner workflows still need a
separate end-to-end test with isolated server fixtures.

### A12 — P2: quarterly network rejection leaves loading unresolved

[QuarterlyReport](../../web/src/pages/quarterly/QuarterlyReport.tsx) only clears
loading in a fulfilled `fetchPublic(...).then(...)`; rejected fetch is uncaught.
HTTP failure and offline/network failure are different states. Add an explicit
failure/retry state; never render a fabricated report or publication count.

### A13 — P2: route-title and feature-status checks leave visible drift

Registry/design table titles differ from actual headings: Partner Portal versus
Partner Workspace, Trust Language Studio versus Illustrative Clause Rewrite,
Quarterly Intelligence Report versus Global Privacy Intelligence Report.
Unauthorized uses an h2 rather than PageHeader. Existing route guards validate
registry/table/router structure, not rendered titles, so their pass does not mean
these screens meet the design contract. Pick canonical wording in specs first.

## App truth and documentation reconciliation

| Area | Implemented truth observed in code | Documentation action / deployment limit |
| --- | --- | --- |
| Public site / auth entry | Eight public pages share `web/`; `/workspace` applies role landing; existing auth retained | Approved F08/F10 amendment records this integration; no second frontend project |
| F01 intake | Async submission/status, decomposition, profiling UI and background tasks exist | Original explorer ACs must be read with later amendments; no fresh live intake performed |
| F02 pipelines / F23 re-assessment | Connector/job and re-assessment code exists | Do not equate code with active production schedules; Sep-03 activation blockers remain unverified |
| F03–F05 intelligence/report | Deterministic service and immutable-snapshot pathways exist | A01–A05 prevent unconditional trust/reproducibility claims; deployment and cohort census unverified |
| F06 review | Queue and decision endpoints are wired | Empty browser state plus tests/source review; populated approval path not live-tested |
| F07 monitoring | Trend/event/alert/delivery routes and UI exist | Source availability, scheduling and A01/A08 need separate acceptance; old Monitor nav wording is stale |
| F08 knowledge pages | Pages exist; public metadata/catalog behavior incomplete | Update endpoint/public access ACs and remove unconditional review claim after contract decision |
| F09 administration | Gate/job UI wired | No administrative mutations performed in this audit |
| F10 auth / tenancy | Custom JWT; four accepted roles; app-layer org boundary | F10's RLS-OFF reference-table paragraph contradicts schema deny-by-default and migration 0042; reconcile from schema/migrations, not a live assumption; A07 open |
| F11/F12/F14 | Historical predecessors | Preserve superseded banners; use successor F20/F21/F18 rather than their old mocked-status summaries |
| F13/F15/F16 | Preview/masked surfaces | Public wording in older specs does not authorize unmasking; backend/readiness remains conditional |
| F17 evaluation | Backend/evaluation artifacts exist; proposed UI route absent | Proposed does not mean no code; document backend and UI status separately |
| F18 rewrite | Real illustrative rewrite service and UI | Governed/guardrailed output, not an invented recommendation engine; title mismatch remains |
| F19/F20/F21 | Bulk/partner/quarterly services and UI exist beyond original mocks | Broad in-progress status is insufficient to identify remaining ACs; do not mark shipped merely because endpoints exist |
| F26 firm roles/audit | Own-user audit endpoint and middleware shipped in code; firm roles explicitly deferred | Distinguish audit-only backend from a complete account-management or firm-role UI; live persistence unverified |

`00-plan/remaining-work.md` still describes report-CSS generation as future work,
although `scripts/build_report_css.py` and its guard exist. Its history discussion
must distinguish the existing assessment endpoint from missing history UI fields.
The specs README's blanket green-suite statement cannot serve as a current test
receipt given OD-18. Keep historical counts/date claims in their dated records.

Proposed reconciliation order: fix confidence/lineage and report contracts;
resolve public catalog and analyst role intent; update feature AC status against
code/tests; then update remaining-work and generated summaries. Formula changes,
new comparative language and production activation still require their existing
expert/owner decisions. No such decisions were silently made by this audit.

## Product/UI direction for the next app pass

Retain the existing theme, PageHeader, ScoreCell, lineage controls and report
section system. Consolidate the assessment empty state into one clear intake
entry, show monitoring only with honest configuration/data states, and make
report reading the first responsive-layout priority. Standardize titles and
use existing Radix dialogs/drawers. Keep dense expert tools in their role-specific
surfaces; do not redesign the website as part of this app pass.

## Validation receipt

- Baseline: 22 Vitest files / 211 tests passed; production build and repository guards passed.
- Integration: 23 Vitest files / 228 tests passed; production build passed.
- Isolated backend baseline: **1 failed, 1013 passed, 268 skipped**, 197 warnings.
  Failure: frozen-snapshot PDF byte identity. No tests were weakened or disabled.
  Existing service-dependent skips are reported, not counted as live validation.
- Python used the existing 3.12 virtualenv; CI uses 3.13. The isolated tracked-file
  copy excluded real environment files and supplied dummy configuration; no live
  corpus writes were allowed. Backend code was unchanged after this run.
- Build retains a large-chunk warning (main JS approximately 1 MB uncompressed).
  No new dependencies were installed. Consider route splitting separately.
- Guard checks are structural/pattern checks, not proof of domain correctness.

See the [change report](../change-reports/2026-09-08-F08-F10-public-site-and-audit.md)
for exact integration scope and run instructions.
