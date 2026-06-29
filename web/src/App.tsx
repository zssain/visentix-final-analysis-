/**
 * App — uses AuthProvider context for all auth state.
 * No imperative navigate() after sign-in. All redirects are declarative.
 */
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Login } from "./pages/Login";
import { CustomerDashboard } from "./pages/customer/Dashboard";
import { ReviewQueue } from "./pages/sme/ReviewQueue";
import { AdminConsole } from "./pages/admin/Console";
import { ReportPage } from "./pages/ReportPage";
import "./App.css";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const active = location.pathname === to;
  return (
    <Link to={to} className={`nav-link ${active ? "active" : ""}`}>
      {children}
    </Link>
  );
}

function AppRoutes() {
  const { session, profile, signOut } = useAuth();
  const role = profile?.role;

  return (
    <div className="app-layout">
      {session && (
        <nav className="top-nav">
          <div className="nav-brand">
            <div className="logo-icon">V</div>
            <span>Visentix</span>
          </div>
          <div className="nav-links">
            <NavLink to="/">Assessments</NavLink>
            {(role === "sme" || role === "admin") && (
              <NavLink to="/review">Review Queue</NavLink>
            )}
            {role === "admin" && (
              <NavLink to="/admin">Admin</NavLink>
            )}
          </div>
          <div className="nav-user">
            <span className="nav-role">{role ?? ""}</span>
            <button onClick={signOut} className="nav-signout">Sign Out</button>
          </div>
        </nav>
      )}

      <div className={session ? "main-content" : ""}>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<Login />} />
          <Route path="/unauthorized" element={
            <div style={{ padding: 60, textAlign: "center" }}>
              <h2 style={{ color: "var(--danger)" }}>403 — Access Denied</h2>
              <p style={{ color: "var(--text-secondary)", marginTop: 8 }}>
                You do not have permission to view this page.
              </p>
              <Link to="/" className="btn btn-primary" style={{ marginTop: 24, display: "inline-flex" }}>
                Go Home
              </Link>
            </div>
          } />

          {/* Protected — customer */}
          <Route path="/" element={
            <ProtectedRoute allowedRoles={["customer", "sme", "admin"]}>
              <CustomerDashboard />
            </ProtectedRoute>
          } />

          {/* Protected — sme */}
          <Route path="/review" element={
            <ProtectedRoute allowedRoles={["sme", "admin"]}>
              <ReviewQueue />
            </ProtectedRoute>
          } />

          {/* Protected — admin */}
          <Route path="/admin" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <AdminConsole />
            </ProtectedRoute>
          } />

          {/* Protected — report view (all authenticated roles) */}
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
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
