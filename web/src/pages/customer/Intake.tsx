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
import { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { maturityBand } from "../../lib/scoreBands";
import { PageHeader } from "../../components/PageHeader";
import { MultiSelectDropdown, type MSDOption } from "../../components/MultiSelectDropdown";
import "./intake.css";
import "../../components/furniture.css";

type Step = "idle" | "submitting" | "done" | "error";
type InputMode = "url" | "text" | "upload";

// QA-011: server-authoritative pipeline stages → customer-register labels.
const STAGE_LABELS: Record<string, string> = {
  queued: "Queued…",
  fetching: "Fetching the notice…",
  extracting: "Extracting text…",
  segmenting: "Decomposing into clauses…",
  classifying: "Classifying clauses…",
  profiling: "Profiling the organization…",
  benchmarking: "Building the peer benchmark…",
  scoring: "Scoring against peers…",
  generating_findings: "Generating findings…",
  awaiting_review: "Awaiting expert review…",
  generating_report: "Generating the report…",
  complete: "Complete",
  failed: "Failed",
};

// Bounded polling: start fast, back off, cap total wall-clock so the UI never
// spins forever (the QA-011 symptom). Progress is recovered from SERVER state,
// so a refresh mid-run resumes from the current stage.
const POLL_MIN_MS = 1200;
const POLL_MAX_MS = 4000;
const POLL_MAX_WALL_MS = 5 * 60 * 1000; // 5 min

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
  const [stage, setStage]       = useState<string>("queued");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [canRetry, setCanRetry] = useState(false);

  // ARCH-001A: intake filters. Options come from the engine's real vocabulary
  // (GET /config/intake-options) so they can't drift from what scoring understands.
  type IndustryOpt = { value: string; label: string; industry_id?: string };
  type JurisdictionOpt = { value: string; label: string };
  // Industry is now a multi-select (checkbox dropdown); the FIRST real pick is the
  // primary benchmark cohort server-side. Empty array = not selected.
  const [industries, setIndustries] = useState<string[]>([]);
  const [jurisdictions, setJurisdictions] = useState<string[]>([]);
  const [industryOpts, setIndustryOpts] = useState<IndustryOpt[]>([]);
  const [jurisdictionOpts, setJurisdictionOpts] = useState<JurisdictionOpt[]>([]);
  const [unknownIndustry, setUnknownIndustry] = useState<string>("unknown");

  useEffect(() => {
    let alive = true;
    api.get("/config/intake-options")
      .then((o: { industries: IndustryOpt[]; jurisdictions: JurisdictionOpt[]; unknown_industry?: string }) => {
        if (!alive) return;
        setIndustryOpts(o.industries ?? []);
        setJurisdictionOpts(o.jurisdictions ?? []);
        if (o.unknown_industry) setUnknownIndustry(o.unknown_industry);
      })
      .catch(() => { /* options unavailable — filters stay empty (honest degradation) */ });
    return () => { alive = false; };
  }, []);

  // Options for the two checkbox dropdowns. Industry appends the honest
  // "not sure / not listed" sentinel so opting out is a first-class choice.
  const industryChoices: MSDOption[] = [
    ...industryOpts.map(o => ({ value: o.value, label: o.label })),
    { value: unknownIndustry, label: "Not sure / not listed" },
  ];
  const jurisdictionChoices: MSDOption[] = jurisdictionOpts.map(o => ({ value: o.value, label: o.label }));

  // The primary (cohort) industry = first real (non-unknown) selection.
  const realIndustries = industries.filter(v => v !== unknownIndustry);
  const industryLabel = (v: string) => industryChoices.find(o => o.value === v)?.label ?? v;

  const isProcessing = step === "submitting";
  const filtersBlank = industries.length === 0 && jurisdictions.length === 0;

  // QA-011 polling machinery. The idempotency key is stable across retries of the
  // SAME submission, so a retry resumes the existing job (no duplicate assessment).
  const idempotencyKey = useRef<string>("");
  const startedAt = useRef<number>(0);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elapsedTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelled = useRef(false);

  const stopTimers = useCallback(() => {
    if (pollTimer.current) { clearTimeout(pollTimer.current); pollTimer.current = null; }
    if (elapsedTimer.current) { clearInterval(elapsedTimer.current); elapsedTimer.current = null; }
  }, []);

  // Clean up timers if the user navigates away mid-processing.
  useEffect(() => () => { cancelled.current = true; stopTimers(); }, [stopTimers]);

  const finishWithResult = useCallback((res: AssessmentResult) => {
    stopTimers();
    setResult(res);
    setStep("done");
    if (res.scoring_error) return;               // let the user read the error
    const delay = res.content_warning ? 4000 : 1500;
    setTimeout(() => navigate(`/reports/${res.assessment_id}`), delay);
  }, [navigate, stopTimers]);

  const pollStatus = useCallback(async (jobId: string, intervalMs: number) => {
    if (cancelled.current) return;
    // Overall wall-clock guard → recoverable timeout (never an infinite spinner).
    if (Date.now() - startedAt.current > POLL_MAX_WALL_MS) {
      stopTimers();
      setStep("error");
      setCanRetry(true);
      setErrorMsg("This is taking longer than expected. You can keep waiting by retrying — your place in line is kept.");
      return;
    }
    try {
      const s = await api.get(`/assessments/${jobId}/status`) as {
        status: string; stage: string; assessment_id: string | null;
        error?: string | null; result?: AssessmentResult | null;
      };
      if (cancelled.current) return;
      setStage(s.stage || s.status);
      if (s.status === "complete" && s.result) {
        finishWithResult(s.result);
        return;
      }
      if (s.status === "failed") {
        stopTimers();
        setStep("error");
        setCanRetry(true);
        setErrorMsg(s.error || "Processing failed. Please try again.");
        return;
      }
      const next = Math.min(intervalMs + 400, POLL_MAX_MS);
      pollTimer.current = setTimeout(() => pollStatus(jobId, next), next);
    } catch (err: unknown) {
      // A transient poll error shouldn't kill the run — retry a few times within
      // the wall-clock budget; a hard auth error is handled by the api layer.
      const next = Math.min(intervalMs + 800, POLL_MAX_MS);
      pollTimer.current = setTimeout(() => pollStatus(jobId, next), next);
      void err;
    }
  }, [finishWithResult, stopTimers]);

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

    cancelled.current = false;
    stopTimers();
    setStep("submitting");
    setResult(null);
    setErrorMsg("");
    setCanRetry(false);
    setStage("queued");
    setElapsedSec(0);
    startedAt.current = Date.now();

    // Stable idempotency key: generated once per submission, REUSED on retry so a
    // double-submit/retry can never create a duplicate assessment (QA-011).
    if (!idempotencyKey.current) {
      idempotencyKey.current =
        (globalThis.crypto?.randomUUID?.() ?? `idem-${Date.now()}-${Math.random()}`);
    }

    // Elapsed timer (server-state progress; refresh-safe).
    elapsedTimer.current = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt.current) / 1000));
    }, 1000);

    try {
      const formData = new FormData();
      if (mode === "url") formData.append("url", urlVal);
      else if (mode === "text") formData.append("text", textVal);
      else if (mode === "upload" && fileVal) formData.append("file", fileVal, fileVal.name);
      // ARCH-001A: thread the captured filters (blank fields are simply omitted).
      // Industry is comma-separated (multi-select); the server treats the first
      // entry as the primary benchmark cohort.
      if (industries.length) formData.append("industry", industries.join(","));
      if (jurisdictions.length) formData.append("jurisdictions", jurisdictions.join(","));
      formData.append("idempotency_key", idempotencyKey.current);

      const sub = await api.postForm("/assessments/async", formData) as {
        assessment_id: string; status: string; stage?: string;
      };
      if (cancelled.current) return;
      setStage(sub.stage || sub.status || "queued");
      pollStatus(sub.assessment_id, POLL_MIN_MS);
    } catch (err: unknown) {
      stopTimers();
      setStep("error");
      setCanRetry(true);
      setErrorMsg(err instanceof Error ? err.message : "Could not submit the notice.");
    }
  }, [mode, urlVal, textVal, fileVal, industries, jurisdictions, pollStatus, stopTimers]);

  // A new submission (inputs changed) should get a fresh idempotency key; a retry
  // of the same inputs keeps it. Clear the key whenever the inputs change.
  useEffect(() => { idempotencyKey.current = ""; }, [mode, urlVal, textVal, fileVal, industries, jurisdictions]);

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

        {/* ── ARCH-001A: intake filters (industry + state privacy laws) ── */}
        <div className="intake-filters" data-testid="intake-filters">
          <div className="intake-field">
            <label id="intake-industry-label">INDUSTRY</label>
            <MultiSelectDropdown
              testId="intake-industry"
              ariaLabel="Industry"
              placeholder="Select industries…"
              options={industryChoices}
              selected={industries}
              onChange={setIndustries}
              disabled={isProcessing}
            />
            <span className="intake-field-help">Determines your peer benchmark cohort (first selection is primary).</span>
          </div>

          <div className="intake-field">
            <label id="intake-jurisdictions-label">STATE PRIVACY LAWS</label>
            <MultiSelectDropdown
              testId="intake-jurisdictions"
              ariaLabel="State privacy laws"
              placeholder="Select state privacy laws…"
              options={jurisdictionChoices}
              selected={jurisdictions}
              onChange={setJurisdictions}
              disabled={isProcessing}
            />
            <span className="intake-field-help">Sets which regulators and state-law exposure apply.</span>
          </div>

          {filtersBlank && (
            <p className="intake-filters-note" data-testid="intake-filters-note">
              Without this, your notice is scored against a broad cohort and general US exposure.
            </p>
          )}
        </div>

        {/* ARCH-001B step 6: Review analysis scope — a live, plain-English summary of
            what will drive the assessment, separating what you DECLARED from what is
            DETECTED from the notice. Only reflects inputs the engine actually consumes. */}
        <div className="intake-scope" data-testid="intake-scope">
          <div className="intake-scope-title">Analysis scope</div>
          <ul className="intake-scope-list">
            <li>
              <span>Benchmark cohort</span>
              <strong>{realIndustries.length
                ? `${industryLabel(realIndustries[0])} peers${realIndustries.length > 1 ? ` (+${realIndustries.length - 1} more selected)` : ""}`
                : "broad cohort (industry not specified)"}</strong>
            </li>
            <li>
              <span>Regulatory / state-law exposure</span>
              <strong>{jurisdictions.length
                ? jurisdictions.map(c => jurisdictionOpts.find(o => o.value === c)?.label ?? c).join(", ")
                : "general US exposure (no states selected)"}</strong>
            </li>
            <li>
              <span>Declared by you</span>
              <strong>{[industries.length && "industry", jurisdictions.length && "state laws"].filter(Boolean).join(", ") || "nothing yet"}</strong>
            </li>
            <li>
              <span>Detected from the notice</span>
              <strong>data categories &amp; practices (tracking, sharing, AI, retention…) — inferred during analysis</strong>
            </li>
          </ul>
          <p className="intake-scope-foot">
            Confidence and cohort size are shown with the result; small cohorts are disclosed and may be broadened.
          </p>
        </div>

        {/* QA-012: honest processing / retention / confidentiality disclosure. Wording
            matches the owner-approved privacy notice (decision-log 2026-07-28); no
            invented legal promises. */}
        <p className="intake-disclosure" data-testid="intake-disclosure">
          <strong>How your notice is handled.</strong> It is processed on Visentix's own
          infrastructure to generate your assessment — <strong>not</strong> sent to any
          third-party AI provider and <strong>not</strong> used to train third-party models.
          De-identified, aggregated patterns may improve Visentix's own accuracy. Content is
          retained and protected per our{" "}
          <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.
        </p>

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
          {canRetry && step === "error" && (
            <button
              className="btn btn-outline btn-sm"
              onClick={handleSubmit}
              data-testid="intake-retry"
              style={{ marginLeft: 8 }}
            >
              Retry
            </button>
          )}
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
          <div className="intake-empty" data-testid="intake-progress">
            <div style={{
              width: 36, height: 36, border: "3px solid var(--border)",
              borderTopColor: "var(--exec-blue)", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", margin: "0 auto 12px",
            }} />
            <p className="intake-empty-msg" data-testid="intake-stage">
              {STAGE_LABELS[stage] ?? "Processing…"}
            </p>
            <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 4 }}>
              {elapsedSec}s elapsed · you can safely refresh — progress is saved
            </p>
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
