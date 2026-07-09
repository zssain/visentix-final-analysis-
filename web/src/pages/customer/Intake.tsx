/**
 * Intake — submit a privacy notice, show real pipeline results.
 *
 * POST /assessments/ returns:
 *   status: "scored" | "decomposed"
 *   scores?: { overall_intelligence, benchmark_percentile, finding_count,
 *              vci_label, vci_score, cohort_size, relaxations, ... }
 *   scoring_error?, content_warning?,
 *   classification: { llm, keyword_fallback }
 *   sections, clauses, content_hash
 */
import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { maturityBand } from "../../lib/scoreBands";
import { PageHeader } from "../../components/PageHeader";
import "./intake.css";
import "../../components/furniture.css";

type Step = "idle" | "submitting" | "done" | "error";
type InputMode = "url" | "pdf" | "text";

interface AssessmentResult {
  assessment_id: string;
  organization_id: string;
  status: "scored" | "decomposed";
  sections: number;
  clauses: number;
  content_hash: string;
  classification: { llm: number; keyword_fallback: number };
  scores?: {
    overall_intelligence: number;
    benchmark_percentile: number;
    finding_count: number;
    vci_label: string;
    vci_score?: number;
    suppress?: boolean;
    snapshot_id?: string;
    cohort_size?: number;
    benchmark_population_version?: number;
    relaxations?: string[];
  };
  scoring_error?: string;
  content_warning?: string;
}

export function Intake() {
  const navigate = useNavigate();
  const [mode, setMode]         = useState<InputMode>("url");
  const [urlVal, setUrlVal]     = useState("");
  const [textVal, setTextVal]   = useState("");
  const [step, setStep]         = useState<Step>("idle");
  const [result, setResult]     = useState<AssessmentResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const isProcessing = step === "submitting";

  const handleSubmit = useCallback(async () => {
    if (mode === "url" && !urlVal.trim()) return;
    if (mode === "text" && !textVal.trim()) return;

    setStep("submitting");
    setResult(null);
    setErrorMsg("");

    try {
      const formData = new FormData();
      if (mode === "url") formData.append("url", urlVal);
      else if (mode === "text") formData.append("text", textVal);

      const res = await api.postForm("/assessments/", formData) as AssessmentResult;
      setResult(res);
      setStep("done");

      // Auto-redirect logic
      if (res.scoring_error) {
        // Don't auto-redirect — user needs to see the error
      } else if (res.content_warning) {
        // Delay redirect to show warning
        setTimeout(() => navigate(`/reports/${res.assessment_id}`), 4000);
      } else {
        // Normal redirect after brief display
        setTimeout(() => navigate(`/reports/${res.assessment_id}`), 1500);
      }
    } catch (err: unknown) {
      setStep("error");
      setErrorMsg(err instanceof Error ? err.message : "Assessment failed");
    }
  }, [mode, urlVal, textVal, navigate]);

  return (
    <div>
      <PageHeader
        eyebrow="Intake"
        title="Submit a Privacy Notice"
        description="Add a notice by URL or pasted text. Visentix extracts clauses, classifies each into a privacy domain, and scores the notice against normalized peers."
      />

      <div className="intake-layout">
      {/* ─── LEFT PANE: Form ─── */}
      <div className="intake-left">
        <div className="intake-left-header">
          <h2>Privacy Notice</h2>
          <div className="intake-tabs" role="tablist" aria-label="Input method">
            {(["url", "text"] as InputMode[]).map(m => (
              <button
                key={m}
                className={`intake-tab ${mode === m ? "active" : ""}`}
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
              >
                {m === "url" ? "URL" : "Paste Text"}
              </button>
            ))}
          </div>
        </div>

        <div className="intake-form-body">
          {mode === "url" && (
            <div className="intake-field">
              <label htmlFor="intake-url">Privacy Notice URL</label>
              <input
                id="intake-url"
                type="url"
                placeholder="https://example.com/privacy"
                value={urlVal}
                onChange={e => setUrlVal(e.target.value)}
                disabled={isProcessing}
              />
            </div>
          )}
          {mode === "text" && (
            <div className="intake-field">
              <label htmlFor="intake-text">Notice Text</label>
              <textarea
                id="intake-text"
                rows={12}
                placeholder="Paste the full text of the privacy notice…"
                value={textVal}
                onChange={e => setTextVal(e.target.value)}
                disabled={isProcessing}
              />
            </div>
          )}
        </div>

        <div className="intake-actions">
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={isProcessing || step === "done"}
            aria-busy={isProcessing}
            id="intake-submit-btn"
          >
            {isProcessing ? "Processing…" : "Analyse Notice"}
          </button>
          {step === "error" && (
            <span style={{ fontSize: "0.82rem", color: "var(--red)" }}>
              {errorMsg || "Could not process this notice."}
            </span>
          )}
        </div>
      </div>

      {/* ─── RIGHT PANE: Results ─── */}
      <div className="intake-right">
        {step === "idle" && (
          <div className="intake-empty">
            <div className="intake-empty-icon">◉</div>
            <p className="intake-empty-msg">
              Submit a privacy notice above.<br />
              Results will appear here once processing is complete.
            </p>
          </div>
        )}

        {isProcessing && (
          <div className="intake-empty">
            <div style={{
              width: 36, height: 36, border: "3px solid var(--border)",
              borderTopColor: "var(--exec-blue)", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", margin: "0 auto 12px",
            }} />
            <p className="intake-empty-msg">Extracting, decomposing, classifying, and scoring…</p>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {step === "done" && result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Content warning (amber box) */}
            {result.content_warning && (
              <div style={{
                background: "rgba(200,164,106,0.08)", border: "1px solid var(--gold)",
                borderRadius: "var(--radius)", padding: "12px 16px",
                color: "#7a5c20", fontSize: "0.88rem", fontWeight: 600,
              }}>
                {result.content_warning}
              </div>
            )}

            {/* Decomposition summary */}
            <div className="card" style={{ padding: "16px 20px" }}>
              <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>
                Decomposition
              </div>
              <div style={{ fontSize: "0.95rem", color: "var(--text)" }}>
                <strong>{result.sections}</strong> sections · <strong>{result.clauses}</strong> clauses · <strong>{result.classification.llm}</strong> LLM-classified
                {result.classification.keyword_fallback > 0 && (
                  <span style={{ color: "var(--text-muted)" }}> · {result.classification.keyword_fallback} keyword fallback</span>
                )}
              </div>
            </div>

            {/* Scores (when present) */}
            {result.scores && (
              <div className="card" style={{ padding: "16px 20px" }}>
                <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>
                  Intelligence Scores
                </div>
                <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "baseline" }}>
                  <div>
                    <span style={{ fontFamily: "var(--font-data)", fontSize: "1.8rem", fontWeight: 700, color: "var(--navy)" }}>
                      {result.scores.overall_intelligence?.toFixed(1)}
                    </span>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>/100</span>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--exec-blue)", marginTop: 2 }}>
                      {maturityBand(result.scores.overall_intelligence ?? 0)}
                    </div>
                  </div>
                  <div style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                    <strong>{result.scores.finding_count}</strong> findings ·
                    Confidence: <strong>{result.scores.vci_label}</strong>
                    {result.scores.benchmark_percentile != null && (
                      <> · {result.scores.benchmark_percentile?.toFixed(1)}th percentile</>
                    )}
                  </div>
                </div>

                {/* Relaxation disclosure */}
                {(
                  (result.scores.cohort_size != null && result.scores.cohort_size < 20) ||
                  (result.scores.relaxations && result.scores.relaxations.length > 0)
                ) && (
                  <div style={{
                    marginTop: 10, padding: "8px 12px",
                    background: "rgba(200,164,106,0.08)", border: "1px dashed var(--gold)",
                    borderRadius: "var(--radius)", fontSize: "0.78rem", color: "#7a5c20",
                  }}>
                    Benchmark cohort was broadened for sufficiency; confidence adjusted.
                    {result.scores.cohort_size != null && (
                      <> Cohort size: {result.scores.cohort_size}.</>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Scoring error */}
            {result.status === "decomposed" && result.scoring_error && (
              <div className="card" style={{ padding: "16px 20px", borderColor: "var(--red)" }}>
                <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--red)", marginBottom: 8 }}>
                  Scoring Issue
                </div>
                <p style={{ fontSize: "0.88rem", color: "var(--text-secondary)" }}>
                  Assessment stored, but scoring failed: <code style={{ fontSize: "0.82rem" }}>{result.scoring_error}</code>
                </p>
                <a
                  href={`/reports/${result.assessment_id}`}
                  className="btn btn-outline btn-sm"
                  style={{ marginTop: 10 }}
                >
                  View report anyway →
                </a>
              </div>
            )}

            {/* Normal CTA — only when no scoring error (redirect is pending) */}
            {!result.scoring_error && (
              <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.82rem" }}>
                {result.content_warning
                  ? "Redirecting to report in a few seconds…"
                  : "Redirecting to report…"}
              </div>
            )}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
