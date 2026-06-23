import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthGuard } from "./components/AuthGuard";
import { useAuth } from "./hooks/useAuth";
import { Login } from "./pages/Login";
import { CustomerDashboard } from "./pages/customer/Dashboard";
import { ReviewQueue } from "./pages/sme/ReviewQueue";
import { AdminConsole } from "./pages/admin/Console";

export default function App() {
  const { session, role, loading, signIn, signOut } = useAuth();
  const isAuth = !!session;

  return (
    <BrowserRouter>
      {isAuth && (
        <nav style={{ padding: "8px 16px", borderBottom: "1px solid #e0e0e0", display: "flex", gap: 16, alignItems: "center" }}>
          <strong>Visentix</strong>
          {(role === "customer" || role === "admin") && <a href="/">Assessments</a>}
          {(role === "sme" || role === "admin") && <a href="/review">Review Queue</a>}
          {role === "admin" && <a href="/admin">Admin</a>}
          <button onClick={signOut} style={{ marginLeft: "auto" }}>Sign Out</button>
        </nav>
      )}

      <main style={{ padding: 24 }}>
        <Routes>
          <Route path="/login" element={<Login onSignIn={signIn} />} />
          <Route path="/unauthorized" element={<p>403 — You do not have access to this page.</p>} />

          <Route
            path="/"
            element={
              <AuthGuard role={role} allowedRoles={["customer", "sme", "admin"]} isAuthenticated={isAuth} loading={loading}>
                <CustomerDashboard />
              </AuthGuard>
            }
          />

          <Route
            path="/review"
            element={
              <AuthGuard role={role} allowedRoles={["sme", "admin"]} isAuthenticated={isAuth} loading={loading}>
                <ReviewQueue />
              </AuthGuard>
            }
          />

          <Route
            path="/admin"
            element={
              <AuthGuard role={role} allowedRoles={["admin"]} isAuthenticated={isAuth} loading={loading}>
                <AdminConsole />
              </AuthGuard>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
