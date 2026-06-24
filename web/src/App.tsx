import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthGuard } from "./components/AuthGuard";
import { useAuth } from "./hooks/useAuth";
import { Login } from "./pages/Login";
import { CustomerDashboard } from "./pages/customer/Dashboard";
import { ReviewQueue } from "./pages/sme/ReviewQueue";
import { AdminConsole } from "./pages/admin/Console";
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

function AppContent() {
  const { session, role, loading, signIn, signOut, user } = useAuth();
  const isAuth = !!session;

  return (
    <div className="app-layout">
      {isAuth && (
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
            <span className="nav-role">{role}</span>
            <button onClick={signOut} className="nav-signout">Sign Out</button>
          </div>
        </nav>
      )}

      <div className={isAuth ? "main-content" : ""}>
        <Routes>
          <Route path="/login" element={<Login onSignIn={signIn} />} />
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

          <Route path="/" element={
            <AuthGuard role={role} allowedRoles={["customer", "sme", "admin"]} isAuthenticated={isAuth} loading={loading}>
              <CustomerDashboard />
            </AuthGuard>
          } />

          <Route path="/review" element={
            <AuthGuard role={role} allowedRoles={["sme", "admin"]} isAuthenticated={isAuth} loading={loading}>
              <ReviewQueue />
            </AuthGuard>
          } />

          <Route path="/admin" element={
            <AuthGuard role={role} allowedRoles={["admin"]} isAuthenticated={isAuth} loading={loading}>
              <AdminConsole />
            </AuthGuard>
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
      <AppContent />
    </BrowserRouter>
  );
}
