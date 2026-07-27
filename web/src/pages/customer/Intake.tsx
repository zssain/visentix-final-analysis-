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
type InputMode = "url" | "text" | "upload";

// Accepted upload types — validated authoritatively server-side by magic bytes;
// this is only a friendlier client-side pre-check.
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB — matches backend MAX_UPLOAD_BYTES
const ACCEPT_EXT = ".pdf,.docx,.txt";
const ACCEPT_MIME = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
]);

interface AssessmentResult {
  assessment_id: string;
  organization_id: string;
  status: "scored" | "decomposed";
  sections: number;
  clauses: number;
  content_hash: string;
  ssrf_protected?: boolean;
  source_url?: string | null;
  intake_method?: "url" | "text" | "upload";
  upload_filename?: string;
  clauses_substantive?: number;
  clauses_noise?: number;
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
  const [fileVal, setFileVal]   = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [step, setStep]         = useState<Step>("idle");
  const [result, setResult]     = useState<AssessmentResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const isProcessing = step === "submitting";

  // Friendly client-side pre-check. The server re-validates by magic bytes and
  // is the source of truth; this just fails fast with a plain-English message.
  const pickFile = useCallback((f: File | null) => {
    setErrorMsg("");
    if (!f) { setFileVal(null); return; }
    const extOk = /\.(pdf|docx|txt)$/i.test(f.name);
    if (!ACCEPT_MIME.has(f.type) && !extOk) {
      setErrorMsg("That file type isn't supported. Upload a PDF, Word (.docx), or plain-text (.txt) file.");
      setFileVal(null);
      return;
    }
    if (f.size > MAX_UPLOAD_BYTES) {
      setErrorMsg(`That file is ${(f.size / (1024 * 1024)).toFixed(1)} MB — the maximum is 10 MB.`);
      setFileVal(null);
      return;
    }
    setFileVal(f);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (mode === "url" && !urlVal.trim()) return;
    if (mode === "text" && !textVal.trim()) return;
    if (mode === "upload" && !fileVal) return;

    setStep("submitting");
    setResult(null);
    setErrorMsg("");

    try {
      const formData = new FormData();
      if (mode === "url") formData.append("url", urlVal);
      else if (mode === "text") formData.append("text", textVal);
      else if (mode === "upload" && fileVal) formData.append("file", fileVal, fileVal.name);

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
  }, [mode, urlVal, textVal, fileVal, navigate]);

  return (
    <div>
      <PageHeader
        eyebrow="Intake"
        title="Submit a Privacy Notice"
        description="Add a notice by URL, pasted text, or an uploaded document (PDF, Word, or text). Visentix extracts clauses, classifies each into a privacy domain, and scores the notice against normalized peers."
      />

      <div className="intake-layout">
      {/* ─── LEFT PANE: Form ─── */}
      <div className="intake-left">
        <div className="intake-left-header">
          <h2>Privacy Notice</h2>
          <div className="intake-tabs" role="tablist" aria-label="Input method">
            {(["url", "text", "upload"] as InputMode[]).map(m => (
              <button
                key={m}
                className={`intake-tab ${mode === m ? "active" : ""}`}
                role="tab"
                aria-selected={mode === m}
                onClick={() => { setMode(m); setErrorMsg(""); }}
              >
                {m === "url" ? "URL" : m === "text" ? "Paste Text" : "Upload"}
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
          {mode === "upload" && (
            <div className="intake-field">
              <label htmlFor="intake-file">Notice Document</label>
              <label
                htmlFor="intake-file"
                className={`intake-dropzone ${dragOver ? "dragover" : ""} ${fileVal ? "has-file" : ""}`}
                onDragOver={e => { e.preventDefault(); if (!isProcessing) setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => {
                  e.preventDefault();
                  setDragOver(false);
                  if (isProcessing) return;
                  pickFile(e.dataTransfer.files?.[0] ?? null);
                }}
              >
                <input
                  id="intake-file"
                  type="file"
                  accept={ACCEPT_EXT}
                  disabled={isProcessing}
                  onChange={e => pickFile(e.target.files?.[0] ?? null)}
                  style={{ display: "none" }}
                />
                {fileVal ? (
                  <div className="intake-dropzone-file">
                    <strong>{fileVal.name}</strong>
                    <span>{(fileVal.size / 1024).toFixed(0)} KB · click to replace</span>
                  </div>
                ) : (
                  <div className="intake-dropzone-prompt">
                    <div className="intake-dropzone-icon">↥</div>
                    <p><strong>Drag a file here</strong> or click to browse</p>
                    <p className="intake-dropzone-hint">PDF, Word (.docx), or plain text — up to 10 MB</p>
                  </div>
                )}
              </label>
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
          {(step === "error" || errorMsg) && (
            <span style={{ fontSize: "0.82rem", color: "var(--red)" }}>
              {errorMsg || "Could not process this notice."}
              {mode === "upload" && step === "error" && (
                <span style={{ color: "var(--text-muted)" }}>
                  {" "}You can also paste the text or submit the notice URL instead.
                </span>
              )}
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
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}>
                  Decomposition
                </div>
                {/* M-02: verified-source badge — shown only when the notice was
                    retrieved and validated from its live web address. Customer-
                    register wording; no security jargon (Rule 9). */}
                {result.ssrf_protected && (
                  <span
                    data-testid="verified-source-badge"
                    title="This notice was retrieved and validated directly from its published web address."
                    style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      fontSize: "0.66rem", fontWeight: 700, color: "var(--teal)",
                      background: "rgba(20,138,120,0.08)", border: "1px solid rgba(20,138,120,0.25)",
                      padding: "1px 8px", borderRadius: 4, cursor: "help",
                    }}
                  >
                    ✓ Verified source
                  </span>
                )}
                {/* Uploaded document — customer-register wording. This is NOT a
                    verified source (that badge means a URL passed validation);
                    showing verified-source for an upload would be dishonest. */}
                {result.intake_method === "upload" && (
                  <span
                    data-testid="uploaded-document-badge"
                    title={result.upload_filename
                      ? `Extracted from the uploaded document “${result.upload_filename}”.`
                      : "Extracted from an uploaded document."}
                    style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      fontSize: "0.66rem", fontWeight: 700, color: "var(--text-secondary)",
                      background: "var(--soft-white)", border: "1px solid var(--border)",
                      padding: "1px 8px", borderRadius: 4, cursor: "help",
                    }}
                  >
                    ↥ Uploaded document
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.95rem", color: "var(--text)" }}>
                <strong>{result.sections}</strong> sections · <strong>{result.clauses_substantive ?? result.clauses}</strong> clauses · <strong>{result.classification.llm}</strong> LLM-classified
                {result.classification.keyword_fallback > 0 && (
                  <span style={{ color: "var(--text-muted)" }}> · {result.classification.keyword_fallback} keyword fallback</span>
                )}
                {result.clauses_noise != null && result.clauses_noise > 0 && (
                  <span style={{ color: "var(--text-muted)" }}> · {result.clauses_noise} filtered as noise</span>
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
