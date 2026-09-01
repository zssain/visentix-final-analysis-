/**
 * App — uses AuthProvider context for all auth state.
 * No imperative navigate() after sign-in. All redirects are declarative.
 */
import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import {
  Activity, FilePlus2, ClipboardCheck, Newspaper, BookMarked,
  Compass, Settings, Grid3x3, PenLine, ShieldCheck, Handshake, ScanSearch, Building2,
} from "lucide-react";

// ── Build-level surface masking (release system) ───────────────────────────
// Each maskable surface is gated by a build flag AND lazy-imported ONLY inside a
// raw `import.meta.env.VITE_SURFACE_* === "true"` check. Vite replaces the env
// ref with a string literal at build time, so Rollup DEAD-CODE-ELIMINATES the
// dynamic import() when the surface is off — the masked page's JS chunk is then
// ABSENT from the bundle (release.sh greps the dist to prove it). Do NOT hoist
// these into a helper or an object lookup: the literal check must directly wrap
// import() for DCE to fire.
//
// SECURE BY DEFAULT: maskable surfaces are OFF unless explicitly enabled, so an
// un-flagged build is the masked v1 (a client never sees bulk/partner/etc.).
// release.sh sets VITE_SURFACE_* per version from releases/<version>.yaml.
// /quarterly is a public v1 surface (real approved data) → default ON.
// NB: both routes AND nav links check `import.meta.env.VITE_SURFACE_* === "true"`
// INLINE (never via a shared object) so Rollup DCEs the whole block — even the
// nav label string — out of a masked build.
// VITE_PREVIEW_SURFACES is the documented master switch (see web/.env.example):
// one flag that opens every preview surface for internal builds, instead of
// setting seven. It was documented but never implemented — the code only ever
// read the individual flags, so the documented contract did nothing.
//
// Both operands are compile-time literals, so `false || false` still folds to
// `false` and Rollup's DCE is unaffected: an un-flagged build still has the
// masked chunks — and their nav label strings — absent from the bundle, which
// release.sh step 5 proves by grep.
const S_BULK      = import.meta.env.VITE_SURFACE_BULK      === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true";
const S_PARTNER   = import.meta.env.VITE_SURFACE_PARTNER   === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true";
const S_REWRITE   = import.meta.env.VITE_SURFACE_REWRITE   === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true";
const S_VENDORS   = import.meta.env.VITE_SURFACE_VENDORS   === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true";
const S_TRUST     = import.meta.env.VITE_SURFACE_TRUST     === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true";
const S_CROSSWALK = import.meta.env.VITE_SURFACE_CROSSWALK === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true";
const S_QUARTERLY = import.meta.env.VITE_SURFACE_QUARTERLY !== "false";

/** The flag set the registry consults. Kept next to the raw reads above so a new
 *  surface flag is added in exactly one place. */
const SURFACE_FLAGS: Record<string, boolean> = {
  BULK: S_BULK, PARTNER: S_PARTNER, REWRITE: S_REWRITE, VENDORS: S_VENDORS,
  TRUST: S_TRUST, CROSSWALK: S_CROSSWALK, QUARTERLY: S_QUARTERLY,
};

/** Icons live here, not in the registry: the registry is plain data that the
 *  route guard reads from Python, and importing React components into it would
 *  make it unreadable to that guard. */
const ROUTE_ICONS: Record<string, typeof Activity> = {
  "/assessments": Activity,
  "/intake": FilePlus2,
  "/workbench": ClipboardCheck,
  "/quarterly": Newspaper,
  "/finding-codes": BookMarked,
  "/methodology": Compass,
  "/admin": Settings,
  // Maskable paths are keys too, so they must be gated exactly like the routes
  // themselves — an unconditional key puts a masked path string back into the
  // bundle that DCE just removed from the registry.
  ...(S_REWRITE   ? { "/rewrite": PenLine } : {}),
  ...(S_VENDORS   ? { "/vendors": Building2 } : {}),
  ...(S_CROSSWALK ? { "/crosswalk": Grid3x3 } : {}),
  ...(S_TRUST     ? { "/trust": ShieldCheck } : {}),
  ...(S_PARTNER   ? { "/partner": Handshake } : {}),
  ...(S_BULK      ? { "/screening": ScanSearch } : {}),
};

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/theme/ThemeProvider";
import { ThemeToggle } from "@/theme/ThemeToggle";
import { NAV_GROUPS, ROUTES, ROUTE_REDIRECTS, navFor } from "@/routes/registry";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { ProtectedRoute }        from "./auth/ProtectedRoute";
import { ExplainProvider }       from "./report/explain/ExplainContext";
import { Login }                 from "./pages/Login";
import { CustomerDashboard }     from "./pages/customer/Dashboard";
import { Intake }                from "./pages/customer/Intake";
import { ReviewQueue }           from "./pages/sme/ReviewQueue";
import { AdminConsole }          from "./pages/admin/Console";
import { ReportPage }            from "./pages/ReportPage";
import { FindingCodex }          from "./pages/FindingCodex";
import { Methodology }           from "./pages/Methodology";
import { QuarterlyReport }       from "./pages/quarterly/QuarterlyReport";
import { Privacy }               from "./pages/legal/Privacy";
import { Terms }                 from "./pages/legal/Terms";
import { Footer }                from "./components/Footer";
import { TasksProvider }         from "./jobs/TasksProvider";
import { TaskTracker }           from "./jobs/TaskTracker";

// Maskable-surface routes — registered only when the surface is on; the import()
// (and thus the chunk) vanishes from the bundle when off (see note above).
const susp = (el: React.ReactNode) => <Suspense fallback={null}>{el}</Suspense>;
const maskedRoutes: React.ReactNode[] = [];
if (import.meta.env.VITE_SURFACE_REWRITE === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true") {
  const NoticeRewrite = lazy(() => import("./pages/rewrite/NoticeRewrite").then(m => ({ default: m.NoticeRewrite })));
  maskedRoutes.push(<Route key="rewrite" path="/rewrite" element={
    <ProtectedRoute allowedRoles={["sme", "admin"]}>{susp(<NoticeRewrite />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_VENDORS === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true") {
  const VendorDueDiligence = lazy(() => import("./pages/vendors/VendorDueDiligence").then(m => ({ default: m.VendorDueDiligence })));
  maskedRoutes.push(<Route key="vendors" path="/vendors" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<VendorDueDiligence />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_CROSSWALK === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true") {
  const FrameworkCrosswalk = lazy(() => import("./pages/crosswalk/FrameworkCrosswalk").then(m => ({ default: m.FrameworkCrosswalk })));
  maskedRoutes.push(<Route key="crosswalk" path="/crosswalk" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<FrameworkCrosswalk />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_TRUST === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true") {
  const TrustCenter = lazy(() => import("./pages/trust/TrustCenter").then(m => ({ default: m.TrustCenter })));
  maskedRoutes.push(<Route key="trust" path="/trust" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<TrustCenter />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_PARTNER === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true") {
  const PartnerPortal = lazy(() => import("./pages/partner/PartnerPortal").then(m => ({ default: m.PartnerPortal })));
  maskedRoutes.push(<Route key="partner" path="/partner" element={
    <ProtectedRoute allowedRoles={["partner_admin", "admin"]}>{susp(<PartnerPortal />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_BULK === "true" || import.meta.env.VITE_PREVIEW_SURFACES === "true") {
  const BulkAnalysis = lazy(() => import("./pages/bulk/BulkAnalysis").then(m => ({ default: m.BulkAnalysis })));
  maskedRoutes.push(<Route key="bulk" path="/screening" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<BulkAnalysis />)}</ProtectedRoute>} />);
}

function NavLink({ to, label, children, onClick }: { to: string; label?: string; children?: React.ReactNode; onClick?: () => void }) {
  const location = useLocation();
  // Mark as active if pathname starts with this route (except "/" which is exact)
  const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-3 h-9 text-sm font-medium transition-colors no-underline",
        "[&>svg]:size-[17px] [&>svg]:shrink-0",
        active
          ? "bg-sidebar-primary text-sidebar-primary-foreground"
          : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      )}
      aria-label={label ?? undefined}
      onClick={onClick}
    >
      {children}
    </Link>
  );
}

/** Roles come from the registry, never re-typed at the call site — a role list
 *  that disagrees with the registry is exactly the drift this replaces. */
function Guarded({ path, children }: { path: string; children: React.ReactNode }) {
  const def = ROUTES.find(r => r.path === path);
  if (!def) throw new Error(`Route ${path} is not declared in routes/registry.ts`);
  if (!def.roles) return <>{children}</>;
  return <ProtectedRoute allowedRoles={def.roles}>{children}</ProtectedRoute>;
}

function RoleBasedHome() {
  const { profile } = useAuth();
  if (profile?.role === "admin") return <Navigate to="/admin" replace />;
  if (profile?.role === "sme")   return <Navigate to="/workbench" replace />;
  // Gate the partner redirect behind the build flag too, so the "/partner" string
  // is DCE-stripped from a masked build (v1) — otherwise it leaks into the bundle
  // and fails the release.sh masked-surface grep. In v1 (S_PARTNER=false) a
  // partner_admin (not a v1-provisioned role) falls through to the customer home.
  if (S_PARTNER && profile?.role === "partner_admin") return <Navigate to="/partner" replace />;
  // Redirect, not render: `/` and `/assessments` must not be two URLs for the
  // same screen.
  return <Navigate to="/assessments" replace />;
}

function AppRoutes() {
  const { session, profile, signOut } = useAuth();
  const role = profile?.role;
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  // Login is the only full-bleed route; everything else (including the public
  // /codex and /methodology pages) gets the standard content container.
  const fullBleed = location.pathname === "/login";

  const closeNav = () => setNavOpen(false);

  return (
    <div className="flex min-h-screen bg-background">
      {session && (
        <>
          {/* Mobile top bar — hamburger + brand; hidden on desktop where the
              sidebar is always visible. */}
          <div className="md:hidden fixed top-0 inset-x-0 z-40 h-14 flex items-center gap-3 px-4 bg-sidebar border-b border-sidebar-border">
            <button
              className="inline-flex items-center justify-center size-9 rounded-md text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
              aria-label={navOpen ? "Close menu" : "Open menu"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen(o => !o)}
            >
              {navOpen ? "✕" : "☰"}
            </button>
            <img src="/wordmark logo for white background.png" alt="Visentix" className="h-6 w-auto" />
            <div className="ml-auto"><ThemeToggle /></div>
          </div>

          {/* Drawer backdrop (mobile only, when open) */}
          {navOpen && <div className="md:hidden fixed inset-0 z-40 bg-black/40" onClick={closeNav} aria-hidden="true" />}

          {/* Sidebar nav — grouped so the growing route list stays scannable.
              Nav labels match each page's title/eyebrow so "where am I" is never ambiguous.
              Maskable surfaces show only when their build flag is on AND role allows. */}
          <nav
            className={cn(
              "fixed md:sticky top-0 z-50 h-screen w-64 shrink-0 flex flex-col",
              "bg-sidebar border-r border-sidebar-border",
              "transition-transform duration-200 ease-out md:transition-none",
              "motion-reduce:transition-none",
              navOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
            )}
            role="navigation"
            aria-label="Main navigation"
          >
            <div className="h-16 flex items-center px-5 border-b border-sidebar-border shrink-0">
              <img src="/wordmark logo for white background.png" alt="Visentix" className="h-7 w-auto" />
            </div>

            {/* Built from the route registry — the nav cannot list a screen the
                registry does not declare, and cannot disagree with it about the
                label, the role rule or the feature flag. */}
            <div className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-6">
              {NAV_GROUPS.map(group => {
                const items = navFor(group.id, role, SURFACE_FLAGS);
                if (items.length === 0) return null;
                return (
                  <div key={group.id} className="flex flex-col gap-0.5">
                    <div className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {group.label}
                    </div>
                    {items.map(r => {
                      const Icon = ROUTE_ICONS[r.path];
                      return (
                        <NavLink key={r.path} to={r.path} onClick={closeNav}>
                          {Icon && <Icon size={17} aria-hidden />} {r.navLabel}
                        </NavLink>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            {/* User area pinned to the bottom */}
            <div className="shrink-0 border-t border-sidebar-border p-3 flex items-center justify-between gap-2">
              <span className="text-xs font-medium capitalize text-muted-foreground truncate">{role ?? ""}</span>
              <ThemeToggle />
              <Button
                onClick={signOut}
                variant="ghost"
                size="sm"
                id="nav-signout-btn"
                aria-label="Sign out"
              >
                Sign Out
              </Button>
            </div>
          </nav>
        </>
      )}

      <div className="flex-1 min-w-0 flex flex-col pt-14 md:pt-0">
      <div className={fullBleed ? "" : "mx-auto w-full max-w-[1400px] px-5 py-7 md:px-8 md:py-8"}>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/finding-codes"       element={<FindingCodex />} />
          <Route path="/methodology" element={<Methodology />} />
          {/* /quarterly is public by design (F21 — approved+suppressed data only). */}
          <Route path="/quarterly"   element={<QuarterlyReport />} />
          {/* Legal — public, unauthenticated, linked from the footer. */}
          <Route path="/privacy"     element={<Privacy />} />
          <Route path="/terms"       element={<Terms />} />

          {/* Maskable surfaces — registered ONLY when their build flag is on.
              When off, the route is absent (URL falls through to "*" → home) AND
              the page's chunk is excluded from the bundle. */}
          {maskedRoutes}

          <Route path="/unauthorized" element={
            <div style={{ padding: 60, textAlign: "center" }}>
              <h2 style={{ color: "var(--red)" }}>403 — Access Denied</h2>
              <p style={{ color: "var(--text-secondary)", marginTop: 8 }}>
                You do not have permission to view this page.
              </p>
              <Button asChild style={{ marginTop: 24, display: "inline-flex" }}><Link to="/">
                Go Home
              </Link></Button>
            </div>
          } />

          {/* Root → role-based landing */}
          {/* `/` is a redirect, never a screen. It used to render
              CustomerDashboard directly, which made it a second URL for the
              same screen as /assessments — two addresses for one thing. */}
          <Route path="/" element={<Guarded path="/"><RoleBasedHome /></Guarded>} />

          {/* Monitor (was /assessments — the nav and the title both said Monitor,
              only the URL said assessments) */}
          <Route path="/assessments" element={<Guarded path="/assessments"><CustomerDashboard /></Guarded>} />

          {/* Intake — new and with existing assessment context */}
          <Route path="/intake" element={<Guarded path="/intake"><Intake /></Guarded>} />

          {/* Workbench (was /review — "review" also collides with the customer's
              own report review, which is a different thing entirely) */}
          <Route path="/workbench" element={<Guarded path="/workbench"><ReviewQueue /></Guarded>} />

          {/* Admin (admin role always reaches admin — spec v1) */}
          <Route path="/admin" element={<Guarded path="/admin"><AdminConsole /></Guarded>} />

          {/* Report view */}
          <Route path="/reports/:assessmentId" element={<Guarded path="/reports/:assessmentId"><ReportPage /></Guarded>} />

          {/* Renamed screens keep their old URL working. A report link or a
              bookmark a customer already holds must not 404 because we renamed
              a screen. `/intake/:assessmentId` is deliberately NOT here: it is
              deleted, not redirected — it has had no caller since intake became
              a background job, and redirecting it would preserve a URL shape
              that no longer means anything. */}
          {Object.entries(ROUTE_REDIRECTS).map(([from, to]) => (
            <Route key={from} path={from} element={<Navigate to={to} replace />} />
          ))}

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      {!fullBleed && <Footer />}
      </div>

      {/* Assessments keep running when you leave the page — this is the surface
          that makes leaving safe. Renders nothing when there is nothing to
          report (DDR-011). */}
      {session && <TaskTracker />}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ExplainProvider>
          <TasksProvider>
            <ThemeProvider><TooltipProvider delayDuration={200}><AppRoutes /></TooltipProvider></ThemeProvider>
          </TasksProvider>
        </ExplainProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
