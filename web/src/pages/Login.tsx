import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../auth/AuthProvider";
import { PerspectiveArt } from "./public/shared";
import "./public/website.css";
import "./login.css";

export function Login() {
  const { session, loading, signIn } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [infoMessage, setInfoMessage] = useState("");

  if (!loading && session) {
    const target = from && from !== "/" && from !== "/login" ? from : "/workspace";
    return <Navigate to={target} replace />;
  }
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setInfoMessage(""); setSubmitting(true);
    try { await signIn(email, password); }
    catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
      setSubmitting(false);
    }
  }

  return <div className="public-site login-page">
    <section className="login-form-panel">
      <header className="login-header"><Link to="/" aria-label="Visentix home" className="site-wordmark">visentix.</Link><Link to="/" className="login-back"><ArrowLeft size={13}/>Back to website</Link></header>
      <div className="login-form-wrap"><div className="site-eyebrow"><span/>Your Visentix workspace</div><h1>Welcome back.</h1><p className="login-intro">Sign in to your privacy intelligence workspace.</p>
        {error && <div className="login-message login-error" role="alert" id="login-error">{error}</div>}
        {infoMessage && <div className="login-message" role="status" id="reset-help">{infoMessage}</div>}
        <form onSubmit={handleSubmit} aria-label="Sign in" className="login-form">
          <div className="login-field"><label htmlFor="email-input">Email address</label><input id="email-input" name="email" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com" required autoFocus /></div>
          <div className="login-field"><div className="login-label-row"><label htmlFor="password-input">Password</label><button type="button" className="login-reset" aria-describedby={infoMessage?"reset-help":undefined} onClick={()=>setInfoMessage("Please contact your Visentix administrator to reset your password.")}>Forgot password?</button></div><div className="login-password"><input id="password-input" name="password" type={showPassword?"text":"password"} autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password" required/><button type="button" className="login-password-toggle" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?"Hide password":"Show password"} aria-pressed={showPassword}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></div>
          <button type="submit" className="login-submit" disabled={submitting||loading} aria-busy={submitting}>{submitting?"Signing in...":"Sign In"}<ArrowUpRight size={18}/></button>
        </form>
        <div className="login-access"><span>New to Visentix?</span><Link to="/pricing">Explore plans & access<ArrowUpRight size={13}/></Link></div>
      </div>
      <footer className="login-footer"><span>© {new Date().getFullYear()} Visentix</span><div><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link></div></footer>
    </section>
    <aside className="login-brand-panel" aria-label="About Visentix"><div className="login-brand-heading"><span className="site-kicker">The privacy intelligence platform</span><h2>A clearer view.<br/><em>A stronger perspective.</em></h2><p>Your disclosures. Their context.<br/>The evidence that connects them.</p></div><div className="login-art"><PerspectiveArt/></div><div className="login-brand-bottom"><span>Evidence.</span><span>Context.</span><span>Confidence.</span></div></aside>
  </div>;
}
