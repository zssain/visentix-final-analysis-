import { useState } from "react";

interface LoginProps {
  onSignIn: (email: string, password: string) => Promise<void>;
}

export function Login({ onSignIn }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await onSignIn(email, password);
      // Don't navigate — App.tsx will auto-redirect via isAuth check on /login route
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
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
          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
