import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { BeamsBackground } from "../components/ui/beams-background";

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
  const [showPassword, setShowPassword] = useState(false);
  const [infoMessage, setInfoMessage] = useState("");

  // Declarative redirect: if already authenticated, leave /login
  if (!loading && session) {
    const target = from && from !== "/" ? from : roleLanding(profile?.role ?? "customer");
    return <Navigate to={target} replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInfoMessage("");
    setSubmitting(true);
    try {
      await signIn(email, password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="login-split-container">
      {/* Form Pane */}
      <div className="login-form-pane">
        <div className="login-brand-header">
          <img src="/wordmark logo for white background.png" alt="Visentix" className="login-logo" />
        </div>

        <div className="login-form-wrapper">
          <h1>Sign in</h1>
          <p className="login-subtitle">Access the Privacy Intelligence Platform</p>

          {error && <div className="login-error" role="alert">{error}</div>}
          
          {infoMessage && (
            <div className="notice-box gold" style={{ marginBottom: 20 }} role="status">
              {infoMessage}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="email-input">Email address</label>
              <input
                id="email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoFocus
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="password-input">Password</label>
              <div className="password-input-wrapper">
                <input
                  id="password-input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div className="login-actions-row">
              <button type="submit" className="login-btn-pill" disabled={submitting || loading}>
                {submitting ? "Signing in..." : "Sign In"}
              </button>
              <a 
                href="#forgot" 
                className="forgot-link" 
                onClick={(e) => { 
                  e.preventDefault(); 
                  setInfoMessage("Please contact your Visentix administrator to reset your password."); 
                }}
              >
                Forgot password?
              </a>
            </div>
          </form>

          <div className="signup-prompt">
            Don't have an account?{" "}
            <a 
              href="#contact" 
              onClick={(e) => { 
                e.preventDefault(); 
                setInfoMessage("Please reach out to the Visentix onboarding desk to register."); 
              }}
            >
              Contact Desk
            </a>
          </div>
        </div>

        <div className="login-footer-mark">
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            © Visentix · Privacy Intelligence Platform
          </span>
        </div>
      </div>

      {/* Artwork Pane */}
      <div className="login-artwork-pane">
        <div className="artwork-card">
          <BeamsBackground>
            <div className="artwork-card-content">
              <div className="login-artwork-logo-container">
                <div className="logo-background-watermark" />
                <img src="/logo.png" className="login-artwork-logo" alt="Visentix Logo" />
              </div>
              <div className="artwork-eyebrow">Privacy Intelligence</div>
              <div className="artwork-title">Compared to whom, with what exposure, at what confidence.</div>
              <div className="artwork-subtitle">
                Evidence-driven privacy notice benchmarking and continuous exposure monitoring for legal and regulatory advisory.
              </div>
            </div>
          </BeamsBackground>
        </div>
      </div>
    </div>
  );
}
