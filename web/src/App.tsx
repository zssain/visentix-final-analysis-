/**
 * App — uses AuthProvider context for all auth state.
 * No imperative navigate() after sign-in. All redirects are declarative.
 */
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
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
import "./App.css";

function NavLink({ to, label, children }: { to: string; label?: string; children?: React.ReactNode }) {
  const location = useLocation();
  // Mark as active if pathname starts with this route (except "/" which is exact)
  const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
  return (
    <Link to={to} className={`nav-link ${active ? "active" : ""}`} aria-label={label ?? undefined}>
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
  // Login is the only full-bleed route; everything else (including the public
  // /codex and /methodology pages) gets the standard content container.
  const fullBleed = location.pathname === "/login";

  return (
    <div className="app-layout">
      {session && (
        <nav className="top-nav" role="navigation" aria-label="Main navigation">
          {/* Brand */}
          <div className="nav-brand">
            <img src="/wordmark logo for dark background.png" alt="Visentix" className="nav-logo" />
          </div>
          <div className="nav-divider" aria-hidden="true" />

          {/* Primary nav */}
          {/* Nav labels match each page's title/eyebrow so "where am I" is never ambiguous */}
          <div className="nav-links">
            <NavLink to="/assessments">
              Monitor
            </NavLink>
            <NavLink to="/intake">
              Intake
            </NavLink>
            {(role === "sme" || role === "admin") && (
              <NavLink to="/review">
                Workbench
              </NavLink>
            )}
            {role === "admin" && (
              <NavLink to="/admin">
                Admin
              </NavLink>
            )}
            {role === "admin" && (
              <NavLink to="/partner">
                Partner
              </NavLink>
            )}
            {role === "admin" && (
              <NavLink to="/bulk">
                Bulk
              </NavLink>
            )}
            <NavLink to="/codex">
              Codex
            </NavLink>
            <NavLink to="/methodology">
              Methodology
            </NavLink>
            <NavLink to="/quarterly">
              Quarterly
            </NavLink>
          </div>

          {/* User area */}
          <div className="nav-user">
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
      )}

      <div className={fullBleed ? "" : "main-content"}>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/codex"       element={<FindingCodex />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/quarterly"   element={<QuarterlyReport />} />
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
