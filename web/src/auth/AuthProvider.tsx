/* eslint-disable react-refresh/only-export-components -- standard context pattern: provider + hook co-exported; HMR full-reload is acceptable here */
/**
 * AuthProvider — local auth (no Supabase auth service).
 * Calls POST /auth/login on the FastAPI backend, stores the JWT in
 * localStorage, and exposes session + profile via context.
 */
import { createContext, useContext, useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type UserRole = "customer" | "sme" | "admin" | "partner_admin";

export interface AuthProfile {
  role: UserRole;
  organizationId: string | null;
}

interface LocalSession {
  access_token: string;
  user: { id: string; email: string };
}

interface AuthContextValue {
  session: LocalSession | null;
  user: { id: string; email: string } | null;
  profile: AuthProfile | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const SESSION_KEY = "visentix-auth-session";
const PROFILE_KEY = "visentix-auth-profile";

// Prod builds MUST set VITE_API_BASE_URL; localhost fallback is dev-only.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

function readLocalSession(): LocalSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (raw) return JSON.parse(raw) as LocalSession;
  } catch { /* storage unavailable or corrupt — treat as absent, non-fatal */ }
  return null;
}

function readLocalProfile(): AuthProfile | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (raw) return JSON.parse(raw) as AuthProfile;
  } catch { /* storage unavailable or corrupt — treat as absent, non-fatal */ }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<LocalSession | null>(readLocalSession);
  const [profile, setProfile] = useState<AuthProfile | null>(readLocalProfile);
  // No async bootstrap needed — everything is in localStorage.
  const [loading] = useState(false);

  const user = session ? session.user : null;

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string };
      throw new Error(body.detail ?? "Login failed");
    }

    const data = await res.json() as {
      access_token: string;
      user_id: string;
      email: string;
      role: string;
      organization_id: string | null;
    };

    const newSession: LocalSession = {
      access_token: data.access_token,
      user: { id: data.user_id, email: data.email },
    };
    const newProfile: AuthProfile = {
      role: data.role as UserRole,
      organizationId: data.organization_id ?? null,
    };

    try { localStorage.setItem(SESSION_KEY, JSON.stringify(newSession)); } catch { /* storage unavailable or corrupt — treat as absent, non-fatal */ }
    try { localStorage.setItem(PROFILE_KEY, JSON.stringify(newProfile)); } catch { /* storage unavailable or corrupt — treat as absent, non-fatal */ }

    setProfile(newProfile);
    setSession(newSession);
  }, []);

  const signOut = useCallback(async () => {
    try { localStorage.removeItem(SESSION_KEY); } catch { /* storage unavailable or corrupt — treat as absent, non-fatal */ }
    try { localStorage.removeItem(PROFILE_KEY); } catch { /* storage unavailable or corrupt — treat as absent, non-fatal */ }
    setSession(null);
    setProfile(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ session, user, profile, loading, signIn, signOut }),
    [session, user, profile, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
