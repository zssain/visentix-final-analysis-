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
            <div className="logo-icon" aria-hidden="true">V</div>
            <span>Visentix</span>
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
            <NavLink to="/codex">
              Codex
            </NavLink>
            <NavLink to="/methodology">
              Methodology
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
