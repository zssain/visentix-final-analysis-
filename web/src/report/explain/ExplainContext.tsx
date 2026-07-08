/**
 * ExplainContext — provides:
 *   - Plain/Technical register toggle (React context, NOT localStorage)
 *   - Prefetch cache for /explain/all per assessment
 */
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../../lib/api";

type Register = "plain" | "technical";

interface ExplainEnvelope {
  element_type: string;
  element_key: string;
  title: string;
  plain: string;
  technical: Record<string, unknown>;
  llm_involvement: Record<string, unknown>;
  database_provenance: Record<string, unknown>[];
  legal_basis: Record<string, unknown>[];
  peer_comparison: Record<string, unknown>;
  lineage: Record<string, unknown>;
  confidence_note: string;
  human_review_status: string | null;
  versioning: Record<string, unknown>;
  last_updated: string | null;
}

interface ExplainContextValue {
  register: Register;
  setRegister: (r: Register) => void;
  getEnvelope: (assessmentId: string, type: string, key: string) => ExplainEnvelope | null;
  prefetch: (assessmentId: string) => void;
  loading: boolean;
}

const ExplainCtx = createContext<ExplainContextValue | null>(null);

export function ExplainProvider({ children }: { children: ReactNode }) {
  const [register, setRegister] = useState<Register>("plain");
  const [cache, setCache] = useState<Record<string, Record<string, ExplainEnvelope>>>({});
  const [loading, setLoading] = useState(false);

  const prefetch = useCallback((assessmentId: string) => {
    if (cache[assessmentId]) return; // already cached
    setLoading(true);
    api.get(`/reports/${assessmentId}/explain/all`)
      .then((data: Record<string, ExplainEnvelope>) => {
        setCache(prev => ({ ...prev, [assessmentId]: data }));
      })
      .catch(() => {}) // silently ignore — ⓘ buttons degrade to "unavailable"
      .finally(() => setLoading(false));
  }, [cache]);

  const getEnvelope = useCallback((assessmentId: string, type: string, key: string) => {
    const assessmentCache = cache[assessmentId];
    if (!assessmentCache) return null;
    return assessmentCache[`${type}:${key}`] ?? null;
  }, [cache]);

  const value = useMemo<ExplainContextValue>(
    () => ({ register, setRegister, getEnvelope, prefetch, loading }),
    [register, setRegister, getEnvelope, prefetch, loading],
  );

  return <ExplainCtx.Provider value={value}>{children}</ExplainCtx.Provider>;
}

export function useExplain(): ExplainContextValue {
  const ctx = useContext(ExplainCtx);
  if (!ctx) throw new Error("useExplain must be inside ExplainProvider");
  return ctx;
}

export type { ExplainEnvelope, Register };
