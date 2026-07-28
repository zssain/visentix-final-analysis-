/**
 * F18 — Clause Rewrite (illustrative, guardrailed) · REAL UI (replaces the F14
 * mock M-26).
 *
 * Left: clause picker for an assessment (findings-flagged domains first).
 * Right: guardrailed + fabrication-verified rewrite with a token diff (gold
 * added / warm-gray struck), a NON-DISMISSIBLE watermark, and an honest
 * fallback (side-by-side vs an approved exemplar) whenever a rewrite can't be
 * safely generated. A rewrite is never shown unless BOTH guardrail AND
 * verification passed.
 */
import { useCallback, useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { api, ApiError } from "../../lib/api";
import "../../components/furniture.css";
import "./rewrite.css";

const WATERMARK = "Illustrative language based on peer patterns — not legal drafting. Review with counsel.";

interface Clause { clause_id: string; raw_text: string; domain: string; }
interface DiffOp { op: "eq" | "add" | "del"; text: string; }
interface RewriteResult {
  rewrite_id: string; status: "llm" | "fallback";
  suggested_text: string | null; diff: DiffOp[]; watermark_text: string;
  guardrail_passed: boolean; verification_passed: boolean; fallback_used: boolean;
}

export function NoticeRewrite() {
  const [assessmentId, setAssessmentId] = useState("");
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [flagged, setFlagged] = useState<string[]>([]);
  const [selected, setSelected] = useState<Clause | null>(null);
  const [result, setResult] = useState<RewriteResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, showFlash] = useFlash();

  const loadClauses = useCallback(async (id: string) => {
    if (!id.trim()) return;
    try {
      const data = await api.get(`/assessments/${id.trim()}/clauses`);
      setClauses(data.clauses || []); setFlagged(data.flagged_domains || []);
      setSelected(null); setResult(null);
      if (!data.clauses?.length) showFlash("No substantive clauses found for that assessment.");
    } catch (e) { showFlash(e instanceof ApiError ? (e.status === 403 ? "Not your assessment." : "Could not load clauses.") : "Load failed."); }
  }, [showFlash]);

  const rewrite = async (c: Clause) => {
    setSelected(c); setResult(null); setBusy(true);
    try {
      const r: RewriteResult = await api.post(`/assessments/${assessmentId.trim()}/clauses/${c.clause_id}/rewrite`, {});
      setResult(r);
    } catch (e) { showFlash(e instanceof ApiError ? `Rewrite failed: ${e.message}` : "Rewrite failed."); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Rewrite" title="Illustrative Clause Rewrite"
        description="A drafting aid — clearer structure, peer-informed phrasing — that never adds a practice, recipient, or purpose your clause didn't already make. Every suggestion passes a banned-term and a fabrication check; if it can't, you get a safe side-by-side comparison instead." />
      <FlashNotice message={flash} />

      <div className="rw-load">
        <input className="rw-input" placeholder="Assessment ID" value={assessmentId}
               onChange={e => setAssessmentId(e.target.value)} onKeyDown={e => e.key === "Enter" && loadClauses(assessmentId)} />
        <button className="btn btn-primary" onClick={() => loadClauses(assessmentId)}>Load clauses</button>
      </div>

      {clauses.length > 0 && (
        <div className="rw-grid">
          {/* Clause picker */}
          <section className="rw-card rw-picker">
            <div className="rw-h">Clauses {flagged.length > 0 && <span className="rw-flagged-note">· flagged domains first</span>}</div>
            {clauses.map(c => (
              <button key={c.clause_id} className={`rw-clause ${selected?.clause_id === c.clause_id ? "on" : ""} ${flagged.includes(c.domain) ? "flagged" : ""}`}
                      onClick={() => rewrite(c)}>
                <span className="rw-clause-domain">{c.domain}{flagged.includes(c.domain) ? " ●" : ""}</span>
                <span className="rw-clause-text">{c.raw_text.slice(0, 140)}{c.raw_text.length > 140 ? "…" : ""}</span>
              </button>
            ))}
          </section>

          {/* Rewrite / diff */}
          <section className="rw-card rw-output">
            {!selected ? <div className="rw-empty">Pick a clause to see an illustrative rewrite.</div> : (
              <>
                <div className="rw-watermark">{WATERMARK}</div>
                {busy ? <div className="rw-empty">Generating…</div> : result ? (
                  <>
                    {result.status === "llm" ? (
                      <div className="rw-diff">
                        {result.diff.map((op, i) => (
                          <span key={i} className={`rw-op rw-${op.op}`}>{op.text} </span>
                        ))}
                      </div>
                    ) : (
                      <div className="rw-fallback">
                        <div className="rw-fallback-note">A safe rewrite couldn't be generated for this clause (it failed the fabrication or banned-term check, or the model was unavailable). Here is your clause beside an approved peer exemplar instead.</div>
                        <div className="rw-diff">
                          {result.diff.length ? result.diff.map((op, i) => (
                            <span key={i} className={`rw-op rw-${op.op}`}>{op.text} </span>
                          )) : <span className="rw-empty">No approved exemplar for this domain yet.</span>}
                        </div>
                      </div>
                    )}
                    {result.suggested_text && (
                      <div className="rw-actions">
                        <button className="btn" onClick={() => { navigator.clipboard?.writeText(result.suggested_text || ""); showFlash("Copied."); }}>Copy</button>
                        <button className="btn" onClick={() => selected && rewrite(selected)}>Regenerate</button>
                      </div>
                    )}
                    <div className="rw-legend"><span className="rw-op rw-add">added</span> <span className="rw-op rw-del">removed</span> · <IntelligenceMark /></div>
                  </>
                ) : null}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
