/**
 * AuthProvider — manages auth with fully manual session persistence.
 * Bypasses Supabase's built-in session storage which doesn't work
 * reliably with sb_publishable_ key format.
 */
import { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import type { ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

export type UserRole = "customer" | "sme" | "admin";

export interface AuthProfile {
  role: UserRole;
  organizationId: string | null;
}

interface AuthContextValue {
  session: Session | null;
  user: { id: string; email: string } | null;
  profile: AuthProfile | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const SESSION_KEY = "visentix-auth-session";
const PROFILE_KEY = "visentix-auth-profile";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      if (raw) return JSON.parse(raw) as Session;
    } catch {}
    return null;
  });
  const [profile, setProfile] = useState<AuthProfile | null>(() => {
    // Also restore profile from localStorage so role is correct on reload
    try {
      const raw = localStorage.getItem(PROFILE_KEY);
      if (raw) return JSON.parse(raw) as AuthProfile;
    } catch {}
    return null;
  });
  const [loading, setLoading] = useState(true);

  const user = session?.user ? { id: session.user.id, email: session.user.email ?? "" } : null;

  // Fetch profile when session changes
  useEffect(() => {
    if (!session?.user?.id) {
      setProfile(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    Promise.resolve(
      supabase
        .from("profiles")
        .select("role, organization_id")
        .eq("user_id", session.user.id)
        .single()
    ).then(({ data }) => {
        if (!cancelled) {
          const prof = {
            role: (data?.role as UserRole) ?? "customer",
            organizationId: data?.organization_id ?? null,
          };
          try { localStorage.setItem(PROFILE_KEY, JSON.stringify(prof)); } catch {}
          setProfile(prof);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProfile({ role: "customer", organizationId: null });
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [session?.user?.id]);

  // On mount: check if Supabase has a session (it may not with sb_publishable_ keys)
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (s) {
        setSession(s);
        try { localStorage.setItem(SESSION_KEY, JSON.stringify(s)); } catch {}
      }
      // If no Supabase session but we have one in localStorage, keep it
      // (already initialized in useState)
    }).catch(() => {});
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    if (data.session) {
      // Save to localStorage AND React state
      try { localStorage.setItem(SESSION_KEY, JSON.stringify(data.session)); } catch {}

      // Fetch profile BEFORE setting session — so role is ready on first render
      let role: UserRole = "customer";
      let orgId: string | null = null;
      try {
        const { data: p } = await supabase
          .from("profiles")
          .select("role, organization_id")
          .eq("user_id", data.session.user.id)
          .single();
        if (p?.role) role = p.role as UserRole;
        if (p?.organization_id) orgId = p.organization_id;
      } catch {}

      const prof = { role, organizationId: orgId };
      try { localStorage.setItem(PROFILE_KEY, JSON.stringify(prof)); } catch {}
      setProfile(prof);
      setSession(data.session);
      setLoading(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    try { await supabase.auth.signOut(); } catch {}
    try { localStorage.removeItem(SESSION_KEY); } catch {}
    try { localStorage.removeItem(PROFILE_KEY); } catch {}
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
