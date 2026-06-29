/**
 * AuthProvider — single source of truth for session + profile + loading.
 *
 * Rules:
 * - loading=true until the first auth event resolves (never redirect during loading).
 * - signIn/signOut update context; callers NEVER call navigate() imperatively.
 * - Profile (role) is fetched once session is set, in background.
 * - Uses ANON key only — service-role key NEVER appears here.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

export type UserRole = "customer" | "sme" | "admin";

export interface AuthProfile {
  role: UserRole;
  organizationId: string | null;
}

interface AuthContextValue {
  session: Session | null;
  user: User | null;
  profile: AuthProfile | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<AuthProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    // 1. Get initial session
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (mounted) {
        setSession(s);
        if (s?.user) {
          fetchProfile(s.user.id);
        } else {
          setLoading(false);
        }
      }
    }).catch(() => {
      if (mounted) setLoading(false);
    });

    // 2. Subscribe to auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, s) => {
        if (!mounted) return;
        setSession(s);
        if (s?.user) {
          fetchProfile(s.user.id);
        } else {
          setProfile(null);
          setLoading(false);
        }
      },
    );

    async function fetchProfile(userId: string) {
      try {
        const { data } = await supabase
          .from("profiles")
          .select("role, organization_id")
          .eq("user_id", userId)
          .single();

        if (mounted) {
          setProfile({
            role: (data?.role as UserRole) ?? "customer",
            organizationId: data?.organization_id ?? null,
          });
        }
      } catch {
        if (mounted) {
          setProfile({ role: "customer", organizationId: null });
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function signIn(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    // Do NOT navigate here — the onAuthStateChange callback will update session,
    // which triggers a re-render, and the declarative redirect fires.
  }

  async function signOut() {
    await supabase.auth.signOut();
    setSession(null);
    setProfile(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({ session, user: session?.user ?? null, profile, loading, signIn, signOut }),
    [session, profile, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
