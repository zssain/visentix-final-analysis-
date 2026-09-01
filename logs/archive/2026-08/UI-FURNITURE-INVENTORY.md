# Legacy UI Furniture — What It Did, What Replaces It

**Date:** 2026-08-31 · **Branch:** `feat/shadcn-ui-system`

Inventory of every class defined in `index.css`, `App.css` and `components/furniture.css`,
what it did, and the shadcn/Radix component that replaces it. Counts are call sites
in `.tsx` at the time of writing.

---

## 1. Replaced by a shadcn component

| Legacy class | Uses | What it did | Replacement |
|---|---:|---|---|
| `.btn` + `.btn-primary` `.btn-outline` `.btn-ghost` `.btn-danger` `.btn-sm` `.btn-xs` | 122 | Pill button; variant = colour, size = padding | **`<Button variant size>`** |
| `.card` / `.card-elevated` | 111 | White surface, border, shadow, radius | **`<Card>`** |
| `.card-head` / `.card-title` / `.card-head-row` | 14 | Card header strip with title + right-aligned actions | **`<CardHeader> <CardTitle> <CardAction>`** |
| `.badge` + `.badge-high` `.badge-elevated` `.badge-moderate` `.badge-low` `.badge-teal` `.badge-gold` `.badge-navy` `.badge-draft` `.badge-approved` | 73 | Rounded pill; **colour hard-coded per class** | **`<Badge variant>`** — see §4, this is where the palette bug lived |
| `table` element styles | — | Header row, cell padding, borders | **`<Table> <TableHeader> <TableRow> <TableCell>`** |
| `.empty-state` | 2 | Centred "nothing here" block | **Composed** — `Card` + centred stack + `Button` |
| `.notice-box` | 7 | Bordered informational callout | **`<Alert>` / `<AlertDescription>`** |
| `.spinner` | 7 | Rotating loading ring | **`<Skeleton>`** where it stands for content; spinner kept only for in-button pending |
| `.view-switch` | 2 | Two-button segmented control | **`<Tabs> <TabsList> <TabsTrigger>`** ✅ done |
| `.codex-trigger` / `.codex-tooltip` | — | Hover-only popup, **not keyboard reachable** | **`<Tooltip>`** ✅ done |
| `.lineage-drawer` / `.lineage-backdrop` / `.lineage-drawer-*` | — | Right-hand drawer; **Escape only, no focus trap** | **`<Sheet>`** ✅ done |
| `.multiselect-*` | — | Checkbox dropdown; **mousedown only** | **`<DropdownMenu> <DropdownMenuCheckboxItem>`** ✅ done |
| `.prov-ribbon` + `.ribbon-*` | — | Provenance strip | **`Card` + `Badge` + `Button`** ✅ done |
| `.score-cell` / `.score-num` | 1 | Clickable score opening lineage | **Rewritten on `Button` semantics** ✅ done |
| `.page-head` / `.ph-*` | 14 | Eyebrow + title + description + actions | **`PageHeader` on `Separator`** ✅ done |
| `.flash-notice` | 6 | Transient status banner | **`<Alert role="status">`** ✅ done |
| `.advisor-note-wrap` / `.an-*` (43 classes) | — | Finding note card | **`Card` + `Badge` + `Separator`** ✅ done |

## 2. Replaced by Tailwind utilities (no component needed)

| Legacy class | Uses | What it did | Replacement |
|---|---:|---|---|
| `.section-label` | 11 | 0.7rem bold uppercase, 0.1em tracking, muted | `text-[11px] font-semibold uppercase tracking-wider text-muted-foreground` |
| `.micro-label` | 7 | Same, smaller | same utilities |
| `.domain-eyebrow` | 2 | Same, above a title | same utilities |
| `.tabular` / `.stat-value` / `[data-numeric]` | 21 | Tabular-figure numerals | `font-data tabular-nums` |
| `.display` | 118 | Fraunces display face | `font-display` |
| `.content-grid` / `.stats-grid` | 3 | Responsive auto-fit grid | `grid [grid-template-columns:repeat(auto-fit,minmax(Xpx,1fr))]` |
| `.stat-card` | 2 | Label + big number | **`<StatTile>`** (new) |

## 3. Deleted outright — the decision moved on

| Legacy class | Why it is gone |
|---|---|
| `.intelligence-mark` / `.im-icon` | Carried **"Intelligence, not legal advice"** on 9 surfaces. Replaced by scope-at-front + disclosure-at-end in the F01–F05 review. The component outlived the decision. ✅ removed |
| `.draft-watermark-wrap` | Diagonal "DRAFT" overlay. Superseded by the ribbon's `provisional` badge, which says the same thing without obscuring the content it labels. |
| `.live-dot` (5 uses) | Pulsing green dot. Animation ran **forever, ignoring `prefers-reduced-motion`**, and green here meant "live", colliding with green = good on the standing scale. Replaced by a `verified` badge. |
| `.stripe-timeline` / `-item` | One-off decorative timeline used twice. Folded into a plain bordered list. |
| `.logo-background-watermark`, `.artwork-*`, `.login-*` (17 classes) | Login-screen-specific decoration. Rebuilt on `Card` + utilities. |

## 4. ⚠ The badge palette bug this inventory found

`.badge-*` **hard-coded a colour per class**, outside the token layer:

```
.badge-high     { color: #b91c1c }   .badge-moderate { color: #065f46 }
.badge-elevated { color: #92400e }   .badge-low      { color: #065f46 }
```

Three separate problems:

1. **These are literal hex values in a class name** — they bypass the token layer
   entirely, so the traffic-light decision (OD-13) never reached them. `.badge-moderate`
   is *green*, and it is applied to things that are middling, not good.
2. **`.badge-moderate` and `.badge-low` are the identical colour** (`#065f46`), so two
   different standings render indistinguishably.
3. **`.badge-teal` / `.badge-gold` / `.badge-draft` mix jobs** — teal and gold mean
   "verified" and "draft" (a *kind*), but they sit in the same class family as
   high/elevated/low (a *standing*). A reader cannot tell which axis a pill is on.

The replacement splits them by job, which is why `Badge` has the variants it has:

- **standing** (how good): `standing-good` · `standing-mid` · `standing-bad`
- **kind** (what it is): `provisional` · `verified` · `outline` · `secondary`

No variant defines a colour; each names a meaning and reads the token layer.

## 5. Kept as-is

| Class | Why |
|---|---|
| `.clause-chip`, `.code-chip` | Data-font identifier chips. Now `Badge variant="outline" className="font-data"`. |
| `.guardrail-banner` | One use. Folded into `Alert`. |
| `.domain-chip` | One use. Folded into `Badge`. |
| Report `.report-*` classes | The **PDF renderer shares these**. They stay until the print CSS is regenerated from the token layer — Tailwind does not reach WeasyPrint. |

---

## Order of removal

A legacy stylesheet can only be deleted once no page references it. Deleted so far:
`advisor-note.css`, `multiselect.css`. Remaining: `furniture.css` (631), `App.css` (431),
`index.css` legacy half (~300), and six page-level stylesheets — each falls as its
pages are converted.
