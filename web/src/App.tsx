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
const S_BULK      = import.meta.env.VITE_SURFACE_BULK === "true";
const S_PARTNER   = import.meta.env.VITE_SURFACE_PARTNER === "true";
const S_REWRITE   = import.meta.env.VITE_SURFACE_REWRITE === "true";
const S_VENDORS   = import.meta.env.VITE_SURFACE_VENDORS === "true";
const S_TRUST     = import.meta.env.VITE_SURFACE_TRUST === "true";
const S_CROSSWALK = import.meta.env.VITE_SURFACE_CROSSWALK === "true";
const S_QUARTERLY = import.meta.env.VITE_SURFACE_QUARTERLY !== "false";

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
import "./App.css";

// Maskable-surface routes — registered only when the surface is on; the import()
// (and thus the chunk) vanishes from the bundle when off (see note above).
const susp = (el: React.ReactNode) => <Suspense fallback={null}>{el}</Suspense>;
const maskedRoutes: React.ReactNode[] = [];
if (import.meta.env.VITE_SURFACE_REWRITE === "true") {
  const NoticeRewrite = lazy(() => import("./pages/rewrite/NoticeRewrite").then(m => ({ default: m.NoticeRewrite })));
  maskedRoutes.push(<Route key="rewrite" path="/rewrite" element={
    <ProtectedRoute allowedRoles={["sme", "admin"]}>{susp(<NoticeRewrite />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_VENDORS === "true") {
  const VendorDueDiligence = lazy(() => import("./pages/vendors/VendorDueDiligence").then(m => ({ default: m.VendorDueDiligence })));
  maskedRoutes.push(<Route key="vendors" path="/vendors" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<VendorDueDiligence />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_CROSSWALK === "true") {
  const FrameworkCrosswalk = lazy(() => import("./pages/crosswalk/FrameworkCrosswalk").then(m => ({ default: m.FrameworkCrosswalk })));
  maskedRoutes.push(<Route key="crosswalk" path="/crosswalk" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<FrameworkCrosswalk />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_TRUST === "true") {
  const TrustCenter = lazy(() => import("./pages/trust/TrustCenter").then(m => ({ default: m.TrustCenter })));
  maskedRoutes.push(<Route key="trust" path="/trust" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<TrustCenter />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_PARTNER === "true") {
  const PartnerPortal = lazy(() => import("./pages/partner/PartnerPortal").then(m => ({ default: m.PartnerPortal })));
  maskedRoutes.push(<Route key="partner" path="/partner" element={
    <ProtectedRoute allowedRoles={["partner_admin", "admin"]}>{susp(<PartnerPortal />)}</ProtectedRoute>} />);
}
if (import.meta.env.VITE_SURFACE_BULK === "true") {
  const BulkAnalysis = lazy(() => import("./pages/bulk/BulkAnalysis").then(m => ({ default: m.BulkAnalysis })));
  maskedRoutes.push(<Route key="bulk" path="/bulk" element={
    <ProtectedRoute allowedRoles={["admin"]}>{susp(<BulkAnalysis />)}</ProtectedRoute>} />);
}

function NavLink({ to, label, children, onClick }: { to: string; label?: string; children?: React.ReactNode; onClick?: () => void }) {
  const location = useLocation();
  // Mark as active if pathname starts with this route (except "/" which is exact)
  const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
  return (
    <Link to={to} className={`nav-link ${active ? "active" : ""}`} aria-label={label ?? undefined} onClick={onClick}>
      {children}
    </Link>
  );
}

function RoleBasedHome() {
  const { profile } = useAuth();
  if (profile?.role === "admin") return <Navigate to="/admin" replace />;
  if (profile?.role === "sme")   return <Navigate to="/review" replace />;
  // Gate the partner redirect behind the build flag too, so the "/partner" string
  // is DCE-stripped from a masked build (v1) — otherwise it leaks into the bundle
  // and fails the release.sh masked-surface grep. In v1 (S_PARTNER=false) a
  // partner_admin (not a v1-provisioned role) falls through to the customer home.
  if (S_PARTNER && profile?.role === "partner_admin") return <Navigate to="/partner" replace />;
  return <CustomerDashboard />;
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
    <div className="app-layout">
      {session && (
        <>
          {/* Mobile top bar — hamburger + brand; hidden on desktop where the
              sidebar is always visible. */}
          <div className="mobile-topbar">
            <button
              className="nav-hamburger"
              aria-label={navOpen ? "Close menu" : "Open menu"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen(o => !o)}
            >
              {navOpen ? "✕" : "☰"}
            </button>
            <img src="/wordmark logo for dark background.png" alt="Visentix" className="nav-logo" />
          </div>

          {/* Drawer backdrop (mobile only, when open) */}
          {navOpen && <div className="side-backdrop" onClick={closeNav} aria-hidden="true" />}

          {/* Sidebar nav — grouped so the growing route list stays scannable.
              Nav labels match each page's title/eyebrow so "where am I" is never ambiguous.
              Maskable surfaces show only when their build flag is on AND role allows. */}
          <nav className={`side-nav ${navOpen ? "open" : ""}`} role="navigation" aria-label="Main navigation">
            <div className="side-brand">
              <img src="/wordmark logo for dark background.png" alt="Visentix" className="nav-logo" />
            </div>

            <div className="side-links">
              <div className="side-group">
                <div className="side-group-label">Workspace</div>
                <NavLink to="/assessments" onClick={closeNav}><Activity size={17} aria-hidden /> Monitor</NavLink>
                <NavLink to="/intake" onClick={closeNav}><FilePlus2 size={17} aria-hidden /> Intake</NavLink>
                {S_REWRITE && (role === "sme" || role === "admin") && (
                  <NavLink to="/rewrite" onClick={closeNav}><PenLine size={17} aria-hidden /> Rewrite</NavLink>
                )}
                {S_VENDORS && role === "admin" && (
                  <NavLink to="/vendors" onClick={closeNav}><Building2 size={17} aria-hidden /> Vendors</NavLink>
                )}
                {(role === "sme" || role === "admin") && (
                  <NavLink to="/review" onClick={closeNav}><ClipboardCheck size={17} aria-hidden /> Workbench</NavLink>
                )}
              </div>

              <div className="side-group">
                <div className="side-group-label">Intelligence</div>
                {S_QUARTERLY && (
                  <NavLink to="/quarterly" onClick={closeNav}><Newspaper size={17} aria-hidden /> Quarterly</NavLink>
                )}
                {S_CROSSWALK && role === "admin" && (
                  <NavLink to="/crosswalk" onClick={closeNav}><Grid3x3 size={17} aria-hidden /> Crosswalk</NavLink>
                )}
                <NavLink to="/codex" onClick={closeNav}><BookMarked size={17} aria-hidden /> Codex</NavLink>
                <NavLink to="/methodology" onClick={closeNav}><Compass size={17} aria-hidden /> Methodology</NavLink>
                {S_TRUST && role === "admin" && (
                  <NavLink to="/trust" onClick={closeNav}><ShieldCheck size={17} aria-hidden /> Trust Center</NavLink>
                )}
              </div>

              {S_PARTNER && role === "partner_admin" && (
                <div className="side-group">
                  <div className="side-group-label">Partner</div>
                  <NavLink to="/partner" onClick={closeNav}><Handshake size={17} aria-hidden /> Partner Workspace</NavLink>
                </div>
              )}
              {role === "admin" && (
                <div className="side-group">
                  <div className="side-group-label">Administration</div>
                  <NavLink to="/admin" onClick={closeNav}><Settings size={17} aria-hidden /> Admin</NavLink>
                  {S_PARTNER && (
                    <NavLink to="/partner" onClick={closeNav}><Handshake size={17} aria-hidden /> Partner</NavLink>
                  )}
                  {S_BULK && (
                    <NavLink to="/bulk" onClick={closeNav}><ScanSearch size={17} aria-hidden /> Bulk</NavLink>
                  )}
                </div>
              )}
            </div>

            {/* User area pinned to the bottom */}
            <div className="side-user">
              <span className="nav-role">{role ?? ""}</span>
              <button
                onClick={signOut}
                className="nav-signout"
                id="nav-signout-btn"
                aria-label="Sign out"
              >
                Sign Out
              </button>
            </div>
          </nav>
        </>
      )}

      <div className="app-main">
      <div className={fullBleed ? "" : "main-content"}>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/codex"       element={<FindingCodex />} />
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
              <Link to="/" className="btn btn-primary" style={{ marginTop: 24, display: "inline-flex" }}>
                Go Home
              </Link>
            </div>
          } />

          {/* Root → role-based landing */}
          <Route path="/" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <RoleBasedHome />
            </ProtectedRoute>
          } />

          {/* Assessments / monitoring dashboard */}
          <Route path="/assessments" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <CustomerDashboard />
            </ProtectedRoute>
          } />

          {/* Intake — new and with existing assessment context */}
          <Route path="/intake" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <Intake />
            </ProtectedRoute>
          } />
          <Route path="/intake/:assessmentId" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <Intake />
            </ProtectedRoute>
          } />

          {/* SME Workbench */}
          <Route path="/review" element={
            <ProtectedRoute allowedRoles={["sme", "admin"]}>
              <ReviewQueue />
            </ProtectedRoute>
          } />

          {/* Admin (admin role always reaches admin — spec v1) */}
          <Route path="/admin" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminConsole />
            </ProtectedRoute>
          } />

          {/* Report view */}
          <Route path="/reports/:assessmentId" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <ReportPage />
            </ProtectedRoute>
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      {!fullBleed && <Footer />}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ExplainProvider>
          <AppRoutes />
        </ExplainProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
