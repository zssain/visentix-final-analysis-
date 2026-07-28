/**
 * F05 addendum — Recommendation evidence stack (expandable "why").
 *
 * Reads the FROZEN stack from GET /assessments/{id}/findings/{fid}/evidence
 * (assembled at expert approval, never re-computed at render). Shows obligation
 * context (verbatim exposure-context register), one approved exemplar or an
 * honest absence, ≤2 resolved-enforcement precedents. The risk-reduction delta
 * row appears ONLY when non-null (i.e. never today — no formula exists). The
 * three honest-absence claims are shown distinctly, never conflated.
 */
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import "./evidence.css";

interface ObRef { obligation_id: string; similarity: number; law?: string; requirement_type?: string; jurisdiction?: string; verified?: boolean; }
interface EnfRef { enforcement_id: string; regulator?: string; year?: string; similarity?: number; }
interface Evidence {
  obligation_refs: ObRef[]; obligation_register: string; obligation_absence: string | null;
  exemplar_clause_id: string | null; exemplar_absence: string | null;
  enforcement_refs: EnfRef[]; risk_reduction_delta: number | null; confidence?: number;
}

export function EvidenceStack({ assessmentId, findingId }: { assessmentId: string; findingId: string }) {
  const [ev, setEv] = useState<Evidence | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "pending" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    api.get(`/assessments/${assessmentId}/findings/${findingId}/evidence`)
      .then(d => { if (!cancelled) { setEv(d); setState("ready"); } })
      .catch(e => { if (!cancelled) setState(e instanceof ApiError && e.status === 404 ? "pending" : "error"); });
    return () => { cancelled = true; };
  }, [assessmentId, findingId]);

  if (state === "loading") return <div className="ev-stack ev-muted">Loading evidence…</div>;
  if (state === "pending") return <div className="ev-stack ev-muted">Evidence is assembled and frozen when a Visentix expert approves this assessment.</div>;
  if (state === "error" || !ev) return null;

  return (
    <div className="ev-stack">
      <div className="ev-title">Why this finding</div>

      {/* Obligation context */}
      <div className="ev-block">
        <div className="ev-h">Obligation context</div>
        {ev.obligation_refs.length > 0 ? (
          <ul className="ev-list">
            {ev.obligation_refs.map((o, i) => (
              <li key={i}>
                {o.law || "Obligation"} · {o.requirement_type || "requirement"}{o.jurisdiction ? ` (${o.jurisdiction})` : ""}
                <span className="ev-sim"> · {(o.similarity * 100).toFixed(0)}% match{o.verified === false ? " · unverified" : ""}</span>
              </li>
            ))}
          </ul>
        ) : <div className="ev-absence">{ev.obligation_absence}</div>}
        <div className="ev-register">{ev.obligation_register}</div>
      </div>

      {/* Exemplar */}
      <div className="ev-block">
        <div className="ev-h">Approved peer exemplar</div>
        {ev.exemplar_clause_id ? <div className="ev-muted">An approved exemplar for this domain is available in the language studio.</div>
          : <div className="ev-absence">{ev.exemplar_absence}</div>}
      </div>

      {/* Enforcement precedent */}
      {ev.enforcement_refs.length > 0 && (
        <div className="ev-block">
          <div className="ev-h">Enforcement precedent (resolved records only)</div>
          <ul className="ev-list">
            {ev.enforcement_refs.map((e, i) => (
              <li key={i}>{e.regulator || "Regulator"} · {e.year || "—"}{e.similarity != null ? ` · ${(e.similarity * 100).toFixed(0)}% related` : ""}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Risk-reduction delta — rendered ONLY when non-null (never, today) */}
      {ev.risk_reduction_delta != null && (
        <div className="ev-block"><div className="ev-h">Estimated risk reduction</div><div>{ev.risk_reduction_delta}</div></div>
      )}
    </div>
  );
}
