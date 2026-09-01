import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { BeamsBackground } from "../components/ui/beams-background";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff } from "lucide-react";
import { ThemeToggle } from "@/theme/ThemeToggle";

function roleLanding(role: string): string {
  switch (role) {
    case "admin": return "/admin";
    case "sme": return "/workbench";
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
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Form pane */}
      <div className="flex flex-col justify-between p-6 md:p-10">
        <div className="flex items-center justify-between">
          <img src="/wordmark logo for white background.png" alt="Visentix" className="h-7 w-auto dark:hidden" />
          <img src="/wordmark logo for dark background.png" alt="Visentix" className="hidden h-7 w-auto dark:block" />
          <ThemeToggle />
        </div>

        <div className="mx-auto w-full max-w-sm py-12">
          <h1 className="font-sans text-3xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Access the Privacy Intelligence Platform</p>

          {error && <Alert variant="destructive" className="mt-6" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}
          {infoMessage && (
            <Alert className="mt-6" role="status">
              <AlertDescription>{infoMessage}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email-input">Email address</Label>
              <Input
                id="email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoFocus
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="password-input">Password</Label>
              <div className="relative">
                <Input
                  id="password-input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-9 w-9 text-muted-foreground"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-3">
              <Button type="submit" disabled={submitting || loading}>
                {submitting ? "Signing in..." : "Sign In"}
              </Button>
              <a
                href="#forgot"
                className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                onClick={(e) => {
                  e.preventDefault();
                  setInfoMessage("Please contact your Visentix administrator to reset your password.");
                }}
              >
                Forgot password?
              </a>
            </div>
          </form>

          <p className="mt-6 text-sm text-muted-foreground">
            Don't have an account?{" "}
            <a
              href="#contact"
              className="font-medium text-foreground underline-offset-4 hover:underline"
              onClick={(e) => {
                e.preventDefault();
                setInfoMessage("Please reach out to the Visentix onboarding desk to register.");
              }}
            >
              Contact Desk
            </a>
          </p>
        </div>

        <span className="text-xs text-muted-foreground">
          © Visentix · Privacy Intelligence Platform
        </span>
      </div>

      {/* Artwork pane — hidden below lg; it is decoration, not content. */}
      {/* Blueish-teal wash (hue ~205 matches the beam palette): a soft tint in
          light mode, a deep saturated ground in dark mode. */}
      <div className="relative hidden overflow-hidden bg-[oklch(0.945_0.032_205)] dark:bg-[oklch(0.235_0.045_210)] lg:m-4 lg:block lg:rounded-2xl">
        <BeamsBackground>
          <div className="flex h-full flex-col justify-center gap-4 p-12">
            <img src="/logo.png" className="mb-2 h-14 w-14" alt="" aria-hidden="true" />
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Privacy Intelligence
            </div>
            <h2 className="font-sans text-3xl font-semibold leading-tight tracking-tight text-balance">
              Compared to whom, with what exposure, at what confidence.
            </h2>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
              Evidence-driven privacy notice benchmarking and continuous exposure monitoring for legal and regulatory advisory.
            </p>
          </div>
        </BeamsBackground>
      </div>
    </div>
  );
}
