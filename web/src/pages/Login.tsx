/**
 * Login page — declarative redirect when session exists.
 * No imperative navigate() after signIn — the AuthProvider context update
 * triggers a re-render and the Navigate component fires.
 */
import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

function roleLanding(role: string): string {
  switch (role) {
    case "admin": return "/admin";
    case "sme": return "/review";
    default: return "/assessments";
  }
}

export function Login() {
  const { session, profile, loading, signIn } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Declarative redirect: if already authenticated, leave /login
  if (!loading && session) {
    const target = from && from !== "/" ? from : roleLanding(profile?.role ?? "customer");
    return <Navigate to={target} replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await signIn(email, password);
      // signIn sets session in context → this component re-renders →
      // the `if (!loading && session)` check above fires → Navigate renders
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-brand">
          <div style={{
            width: 56, height: 56, margin: "0 auto",
            background: "linear-gradient(135deg, #6c5ce7, #00b894)",
            borderRadius: 14, display: "flex", alignItems: "center",
            justifyContent: "center", fontSize: "1.5rem", color: "white", fontWeight: 800,
          }}>V</div>
          <h1>Visentix</h1>
          <p>Privacy Intelligence Platform</p>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email address</label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com" required autoFocus
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password" required
            />
          </div>
          <button type="submit" className="login-btn" disabled={submitting || loading}>
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
