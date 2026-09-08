/**
 * THE route registry — one declaration per routed screen.
 *
 * Before this file the same route was described in four places that could
 * disagree, and did: the <Route> element, the sidebar <NavLink>, the page's own
 * PageHeader eyebrow/title, and design-system §6's route map. Measured drift at
 * the time of writing: `/bulk` was "Bulk Analysis" in the spec and "Bulk
 * Screening" in code; `/partner` had two different nav labels; five routes were
 * absent from the spec map entirely; and every role + feature-flag rule lived
 * only inside App.tsx, so "who can see this" was not answerable without reading
 * JSX.
 *
 * Rules:
 *   - A screen appears in the sidebar iff it declares `group` AND `navLabel`.
 *   - `roles: undefined` means public (no auth). Otherwise the listed roles.
 *   - `surface` names the build flag that masks it; undefined = always present.
 *   - `title` must match the page's PageHeader title, and `navLabel` its eyebrow
 *     (DDR-008), except for editorial pages and public website heroes that carry their own cover.
 *
 * scripts/check_routes.py compares this file against design-system §6 and fails
 * on any disagreement, so the spec and the code cannot drift again.
 */

export type Role = "customer" | "sme" | "admin" | "partner_admin";
export type NavGroup = "workspace" | "intelligence" | "administration";

export interface RouteDef {
  /** URL path as registered with the router. */
  path: string;
  /** Screen title — must equal the page's PageHeader title. */
  title: string;
  /** Sidebar label. Omit to keep the route out of the nav. */
  navLabel?: string;
  /** Sidebar group. Omit to keep the route out of the nav. */
  group?: NavGroup;
  /** Roles allowed. Omit for a public, unauthenticated route. */
  roles?: Role[];
  /** Build flag that masks this surface. Omit if always present. */
  surface?: "BULK" | "PARTNER" | "REWRITE" | "VENDORS" | "TRUST" | "CROSSWALK" | "QUARTERLY";
  /** Editorial pages carry their own full-bleed cover instead of PageHeader
   *  (recorded DDR-008 exception). */
  editorialCover?: boolean;
  /** Why this screen exists, in one line a non-author can check. */
  purpose: string;
}

/* Build-time flags, read as RAW literals so Rollup can fold them.
 *
 * A maskable route's entry must be dead-code-eliminated from a masked build,
 * strings and all: release.sh step 5 greps the bundle to prove that a masked
 * surface's path and title are ABSENT. Declaring them as plain array members
 * would bundle them unconditionally — which is exactly the leak this guard
 * exists to catch, and which this registry originally introduced.
 *
 * `false ? [{...}] : []` folds at build time and the object never ships. Do NOT
 * hoist these into a helper or an object lookup: the literal check must sit
 * directly in the expression for the fold to happen. */
const PREVIEW   = import.meta.env.VITE_PREVIEW_SURFACES === "true";
const F_REWRITE   = import.meta.env.VITE_SURFACE_REWRITE   === "true" || PREVIEW;
const F_VENDORS   = import.meta.env.VITE_SURFACE_VENDORS   === "true" || PREVIEW;
const F_CROSSWALK = import.meta.env.VITE_SURFACE_CROSSWALK === "true" || PREVIEW;
const F_TRUST     = import.meta.env.VITE_SURFACE_TRUST     === "true" || PREVIEW;
const F_PARTNER   = import.meta.env.VITE_SURFACE_PARTNER   === "true" || PREVIEW;
const F_BULK      = import.meta.env.VITE_SURFACE_BULK      === "true" || PREVIEW;

export const ROUTES: RouteDef[] = [
  { path: "/", title: "Home", editorialCover: true, purpose: "Public website page." },
  { path: "/pricing", title: "Plans & Subscriptions", editorialCover: true, purpose: "Product plans and contact pricing." },
  { path: "/solutions/continuous-monitoring", title: "Continuous Monitoring", editorialCover: true, purpose: "Monitoring subscription overview." },
  { path: "/solutions/white-label", title: "White-Label Intelligence", editorialCover: true, purpose: "Partner product overview." },
  { path: "/platform", title: "The Visentix Platform", editorialCover: true, purpose: "Public website page." },
  { path: "/solutions", title: "Solutions", editorialCover: true, purpose: "Public website page." },
  { path: "/solutions/notice-assessment", title: "Privacy Notice Intelligence Assessment", editorialCover: true, purpose: "Public website page." },
  { path: "/solutions/quarterly-report", title: "Quarterly Report Overview", editorialCover: true, purpose: "Public website page." },
  { path: "/resources", title: "Resources & Insights", editorialCover: true, purpose: "Public website page." },
  { path: "/about", title: "About Visentix", editorialCover: true, purpose: "Public website page." },
  { path: "/contact", title: "Contact", editorialCover: true, purpose: "Public website page." },

  // ── Workspace ────────────────────────────────────────────────────────────
  {
    path: "/assessments", title: "Your Assessments",
    navLabel: "Assessments", group: "workspace",
    roles: ["customer", "sme", "admin"],
    // NOT "/monitor". This screen lists assessments and their standing. The
    // continuous-monitoring capability is MonitoringHero, which renders nothing
    // while its three endpoints are unpopulated — so naming the route "monitor"
    // promised a capability the screen does not deliver, and reserved the word
    // the real feature will need. (Owner-decided 2026-08-31.)
    purpose: "List of this organization's assessments with their current standing.",
  },
  {
    path: "/intake", title: "Submit a Privacy Notice",
    navLabel: "Intake", group: "workspace",
    roles: ["customer", "sme", "admin"],
    purpose: "Start an assessment; work continues in the background.",
  },
  ...(F_REWRITE ? ([{
    path: "/rewrite", title: "Trust Language Studio",
    navLabel: "Rewrite", group: "workspace",
    roles: ["sme", "admin"], surface: "REWRITE",
    purpose: "Draft clearer notice language against the assessed original.",
  }] as RouteDef[]) : []),
  ...(F_VENDORS ? ([{
    path: "/vendors", title: "Vendor Due Diligence",
    navLabel: "Vendors", group: "workspace",
    roles: ["admin"], surface: "VENDORS",
    purpose: "Screen a vendor's public notice and record a procurement decision.",
  }] as RouteDef[]) : []),
  {
    path: "/workbench", title: "SME Workbench",
    navLabel: "Workbench", group: "workspace",
    roles: ["sme", "admin"],
    purpose: "Review findings and de-identify exemplars before a report is approved.",
  },

  // ── Intelligence ─────────────────────────────────────────────────────────
  {
    path: "/quarterly", title: "Quarterly Intelligence Report",
    navLabel: "Quarterly", group: "intelligence",
    surface: "QUARTERLY", editorialCover: true,
    purpose: "Public corpus-wide intelligence for the quarter.",
  },
  ...(F_CROSSWALK ? ([{
    path: "/crosswalk", title: "Framework Crosswalk",
    navLabel: "Crosswalk", group: "intelligence",
    roles: ["admin"], surface: "CROSSWALK",
    purpose: "How our domains and finding codes relate to external frameworks.",
  }] as RouteDef[]) : []),
  {
    path: "/finding-codes", title: "Finding Code Definitions",
    navLabel: "Finding Codes", group: "intelligence",
    // "Codex" was a house coinage on a reader-facing public page — the same
    // class of vendor jargon as VCI and PGMS (design-system §2 acronym rule).
    purpose: "Definition of every finding code and its linked legal references.",
  },
  {
    path: "/methodology", title: "How Visentix Works",
    navLabel: "Methodology", group: "intelligence",
    purpose: "The formulas, the review gate, and the reproducibility guarantees.",
  },
  ...(F_TRUST ? ([{
    path: "/trust", title: "Trust Center",
    navLabel: "Trust Center", group: "intelligence",
    roles: ["admin"], surface: "TRUST", editorialCover: true,
    purpose: "Public statement of what we claim, what we do not, and how data is handled.",
  }] as RouteDef[]) : []),

  // ── Administration ───────────────────────────────────────────────────────
  {
    path: "/admin", title: "Admin Console",
    navLabel: "Admin", group: "administration",
    roles: ["admin"],
    purpose: "System health, gate mode, batch operations and training-label stats.",
  },
  ...(F_PARTNER ? ([{
    path: "/partner", title: "Partner Portal",
    navLabel: "Partner", group: "administration",
    roles: ["admin", "partner_admin"], surface: "PARTNER",
    purpose: "Partner-scoped client list and white-labelled report delivery.",
  }] as RouteDef[]) : []),
  ...(F_BULK ? ([{
    path: "/screening", title: "Bulk Screening",
    navLabel: "Screening", group: "administration",
    roles: ["admin"], surface: "BULK",
    purpose: "Screen many notices at once for draft-grade triage.",
  }] as RouteDef[]) : []),

  // ── Routed but not in the nav ────────────────────────────────────────────
  {
    path: "/reports/:assessmentId", title: "Report",
    roles: ["customer", "sme", "admin"],
    editorialCover: true,
    purpose: "The frozen report for one assessment — the artifact a customer forwards.",
  },
  { path: "/login",        title: "Sign in",       purpose: "Authentication." },
  { path: "/privacy",      title: "Privacy",       purpose: "Our own privacy notice (legal, public)." },
  { path: "/terms",        title: "Terms",         purpose: "Our own terms (legal, public)." },
  { path: "/unauthorized", title: "Not permitted", purpose: "Shown when a role reaches a screen it may not see." },
  {
    path: "/workspace", title: "Workspace",
    roles: ["customer", "sme", "admin", "partner_admin"],
    purpose: "Role-based redirect to the right home screen.",
  },
];

/**
 * Paths that moved. Kept as permanent redirects: a report link or a bookmark a
 * customer already holds must not 404 because we renamed a screen.
 *
 * `/intake/:assessmentId` is NOT here — it is deleted rather than redirected.
 * It has had no caller since intake became a background job, and redirecting it
 * would preserve a URL shape that no longer means anything.
 */
export const ROUTE_REDIRECTS: Record<string, string> = {
  "/monitor": "/assessments",
  "/codex": "/finding-codes",
  "/review": "/workbench",
  // Gated for the same reason the entry is: a redirect naming a masked path
  // puts that path back in the bundle, and there is nothing to redirect TO
  // when the surface is absent.
  ...(F_BULK ? { "/bulk": "/screening" } : {}),
};

export const NAV_GROUPS: { id: NavGroup; label: string }[] = [
  { id: "workspace",      label: "Workspace" },
  { id: "intelligence",   label: "Intelligence" },
  { id: "administration", label: "Administration" },
];

/** Routes for one group that this role + flag set may actually see. */
export function navFor(group: NavGroup, role: string | undefined, flags: Record<string, boolean>) {
  return ROUTES.filter(r =>
    r.group === group &&
    r.navLabel &&
    (!r.surface || flags[r.surface]) &&
    (!r.roles || (role !== undefined && r.roles.includes(role as Role)))
  );
}
