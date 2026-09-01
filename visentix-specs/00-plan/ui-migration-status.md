# UI Migration Status — shadcn/Tailwind v4

**Version:** 1.0 · 2026-08-31 · Branch `feat/shadcn-ui-system`
**Governing spec:** `01-foundation/design-system.md` §1, §3.1, §7

Tracks which surfaces have been rebuilt on the component system and which still
run on page-scoped CSS. **Not a decision record** — decisions live in
`open-decisions.md`; this is the work ledger.

## Done

| Surface | Route | Note |
|---|---|---|
| App shell | all | Sidebar on `sidebar-*` tokens; was a navy panel, the token is near-white, so it uses the white-background wordmark that already shipped |
| Theme toggle | all | Three states (light/dark/system), sidebar footer + mobile top bar |
| Dashboard | `/` | Card/StatTile/Badge; overall score band-first with arrival animation |
| Login | `/login` | Input/Label/Button/Alert; killed `App.css` |
| Admin Console | `/admin` | 84 inline styles → 5 |
| Methodology | `/methodology` | 35 inline styles, had no stylesheet |
| Finding Codex | `/codex` | 31 inline styles, had no stylesheet |
| Primitives | — | Button · Card · Badge · Alert · Table · Tabs · Dialog · Tooltip · DropdownMenu · Sheet · Popover · Select · Input · Label · Separator · Skeleton · ScrollArea · Progress |
| Bespoke → primitive | — | PageHeader · FlashNotice · Footer · ViewSwitch · CodexTooltip · LineageDrawer · MultiSelectDropdown · ScoreCell · ProvenanceRibbon · AdvisorNote · StatusDot |
| New | — | `MockBadge` · `StatTile` · `AnimatedNumber` |

**Deleted:** `furniture.css` (631) · `App.css` (431) · `advisor-note.css` (234) · `multiselect.css` (83) · `IntelligenceMark.tsx`.

**Codemod:** 122 `.btn` → 3 · 73 `.badge` → 4 · generic `.card` → `<Card>` · 272 hard-coded colours → tokens.

## Not yet migrated

These are **not broken** — the legacy token bridge (§1.4) means they adopted the
palette and respond to the theme — but their layout is still page-scoped CSS.

| Route | Surface | Stylesheet |
|---|---|---|
| `/assessments` | Monitor | — |
| `/review` | SME Workbench | `workbench.css` |
| `/intake` | Intake | `intake.css` (413) |
| `/reports/:id` | **Report surfaces** (24 files, ~190 inline styles) | `report.css` (278), `explain.css` (307) |
| `/bulk` | Bulk Screening | `bulk.css` |
| `/partner` | Partner Workspace | `partner.css` (186) |
| `/quarterly` | Quarterly | `quarterly.css` (310) |
| `/trust` | Trust Center | `trust.css` |
| `/vendors` | Vendor Due Diligence | `vendors.css` |
| `/rewrite` | Notice Rewrite | `rewrite.css` |
| `/crosswalk` | Framework Crosswalk | `crosswalk.css` |

Flag-masked routes (`/rewrite`, `/vendors`, `/crosswalk`, `/trust`, `/bulk`,
`/partner`, `/quarterly`) are included deliberately: a surface that is off in
v1 still ships its CSS and still has to be correct when its flag flips.

## Recommended order

1. **Report surfaces** — the artifact customers forward, and the subject of the
   language research (`../../logs/archive/2026-08/REPORT-LANGUAGE-RESEARCH-2026-08-31.md`). Highest value.
2. **Workbench + Intake** — the two daily-driver internal screens.
3. Flagged surfaces, in flag-flip order.

`index.css` cannot be deleted until every row above is done; what remains of it
is the legacy bridge plus base element rules, and each page migrated lets a
block of it go.

## Carried debt

- **`report.css` is shared with the PDF renderer.** Tailwind does not reach
  WeasyPrint and WeasyPrint does not parse `oklch()`. The PDF keeps its own
  stylesheet (owner-confirmed 2026-08-31), but its values must be **generated
  from `theme.css`**, not hand-copied — otherwise screen and print drift again.
  This is the concrete half of **OD-17**.
- **The chart ramp is sequential only.** No categorical palette exists. A
  surface needing to tell entities apart by colour must raise it as a decision,
  not generate hues (§1.3).
- **`beams-background.tsx`** on `/login` is pre-existing decorative canvas
  animation and has not been reviewed against §7's reduced-motion rule.
