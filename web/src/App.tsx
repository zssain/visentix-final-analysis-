/**
 * App — uses AuthProvider context for all auth state.
 * No imperative navigate() after sign-in. All redirects are declarative.
 */
import { useState } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import {
  Activity, FilePlus2, ClipboardCheck, Newspaper, BookMarked,
  Compass, Settings, Grid3x3, PenLine, ShieldCheck, Handshake, ScanSearch, Building2,
} from "lucide-react";

// Pilot builds hide the post-MVP surfaces that still render mock data
// (M-15..M-28: Quarterly, Bulk, Crosswalk, Rewrite, Trust Center, Partner,
// Vendors). Their routes stay registered (reachable by URL for internal QA)
// but are unlinked from the nav unless VITE_PREVIEW_SURFACES=true. Default off
// → a pilot client only sees real-data surfaces. See ENGINEERING-CLOSEOUT §7.
const PREVIEW_SURFACES = import.meta.env.VITE_PREVIEW_SURFACES === "true";
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
import { PartnerPortal }         from "./pages/partner/PartnerPortal";
import { BulkAnalysis }          from "./pages/bulk/BulkAnalysis";
import { FrameworkCrosswalk }    from "./pages/crosswalk/FrameworkCrosswalk";
import { NoticeRewrite }         from "./pages/rewrite/NoticeRewrite";
import { TrustCenter }           from "./pages/trust/TrustCenter";
import { VendorDueDiligence }    from "./pages/vendors/VendorDueDiligence";
import "./App.css";

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
              Nav labels match each page's title/eyebrow so "where am I" is never ambiguous. */}
          <nav className={`side-nav ${navOpen ? "open" : ""}`} role="navigation" aria-label="Main navigation">
            <div className="side-brand">
              <img src="/wordmark logo for dark background.png" alt="Visentix" className="nav-logo" />
            </div>

            <div className="side-links">
              <div className="side-group">
                <div className="side-group-label">Workspace</div>
                <NavLink to="/assessments" onClick={closeNav}><Activity size={17} aria-hidden /> Monitor</NavLink>
                <NavLink to="/intake" onClick={closeNav}><FilePlus2 size={17} aria-hidden /> Intake</NavLink>
                {PREVIEW_SURFACES && (
                  <NavLink to="/rewrite" onClick={closeNav}><PenLine size={17} aria-hidden /> Rewrite</NavLink>
                )}
                {PREVIEW_SURFACES && (
                  <NavLink to="/vendors" onClick={closeNav}><Building2 size={17} aria-hidden /> Vendors</NavLink>
                )}
                {(role === "sme" || role === "admin") && (
                  <NavLink to="/review" onClick={closeNav}><ClipboardCheck size={17} aria-hidden /> Workbench</NavLink>
                )}
              </div>

              <div className="side-group">
                <div className="side-group-label">Intelligence</div>
                {PREVIEW_SURFACES && (
                  <NavLink to="/quarterly" onClick={closeNav}><Newspaper size={17} aria-hidden /> Quarterly</NavLink>
                )}
                {PREVIEW_SURFACES && (
                  <NavLink to="/crosswalk" onClick={closeNav}><Grid3x3 size={17} aria-hidden /> Crosswalk</NavLink>
                )}
                <NavLink to="/codex" onClick={closeNav}><BookMarked size={17} aria-hidden /> Codex</NavLink>
                <NavLink to="/methodology" onClick={closeNav}><Compass size={17} aria-hidden /> Methodology</NavLink>
                {PREVIEW_SURFACES && (
                  <NavLink to="/trust" onClick={closeNav}><ShieldCheck size={17} aria-hidden /> Trust Center</NavLink>
                )}
              </div>

              {role === "admin" && (
                <div className="side-group">
                  <div className="side-group-label">Administration</div>
                  <NavLink to="/admin" onClick={closeNav}><Settings size={17} aria-hidden /> Admin</NavLink>
                  {PREVIEW_SURFACES && (
                    <NavLink to="/partner" onClick={closeNav}><Handshake size={17} aria-hidden /> Partner</NavLink>
                  )}
                  {PREVIEW_SURFACES && (
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
          <Route path="/quarterly"   element={<QuarterlyReport />} />
          <Route path="/crosswalk"   element={<FrameworkCrosswalk />} />
          <Route path="/trust"       element={<TrustCenter />} />
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

          {/* Trust Language Studio (F14) — customer trust tool */}
          <Route path="/rewrite" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <NoticeRewrite />
            </ProtectedRoute>
          } />

          {/* Vendor Due Diligence (F16) — procurement workflow */}
          <Route path="/vendors" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <VendorDueDiligence />
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

          {/* Admin */}
          <Route path="/admin" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminConsole />
            </ProtectedRoute>
          } />

          {/* Partner Portal (F11) — no `partner` role yet (F10 tenancy dependency);
              gated to admin for demo access until partner tenancy lands. */}
          <Route path="/partner" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <PartnerPortal />
            </ProtectedRoute>
          } />

          {/* Bulk Analysis (F12) — sensitive/contract-gated capability;
              gated to admin pending contract-based access control. */}
          <Route path="/bulk" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <BulkAnalysis />
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
