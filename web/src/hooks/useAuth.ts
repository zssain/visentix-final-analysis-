/**
 * Auth hook — manages Supabase session + user role.
 */
import { useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

export type UserRole = "customer" | "sme" | "admin" | null;

interface AuthState {
  session: Session | null;
  user: User | null;
  role: UserRole;
  loading: boolean;
}

export function useAuth(): AuthState & {
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
} {
  const [state, setState] = useState<AuthState>({
    session: null,
    user: null,
    role: null,
    loading: true,
  });

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      updateState(session);
    }).catch(() => {
      setState(s => ({ ...s, loading: false }));
    });

    // Listen for changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      updateState(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  function updateState(session: Session | null) {
    if (!session?.user) {
      setState({ session: null, user: null, role: null, loading: false });
      return;
    }

    // Set session IMMEDIATELY so isAuth becomes true (fixes redirect race)
    setState((prev) => ({
      session,
      user: session.user,
      role: prev.role ?? "customer",
      loading: false,
    }));

    // Then fetch role in background (non-blocking)
    supabase
      .from("profiles")
      .select("role")
      .eq("user_id", session.user.id)
      .single()
      .then(({ data, error }) => {
        if (data?.role && !error) {
          setState((prev) => ({ ...prev, role: data.role as UserRole }));
        }
      })
      .catch(() => {
        // Keep default "customer" role
      });
  }

  async function signIn(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
  }

  async function signOut() {
    await supabase.auth.signOut();
    setState({ session: null, user: null, role: null, loading: false });
  }

  return { ...state, signIn, signOut };
}
