/**
 * Intake & Decomposition Explorer
 *
 * Split-pane: left = intake form + progress stepper
 *             right = extracted clause chips + domain filter
 *
 * [MOCK M-01] Clause list is populated from MOCK_CLAUSES until the
 *             backend /api/assessments decomposition response is wired.
 * [MOCK M-02] "Verified source" badge always shown on URL fetch success.
 *             Real flag: ssrf_protected field in API response.
 */
import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { PageHeader } from "../../components/PageHeader";
import "./intake.css";
import "../../components/furniture.css";

const DOMAINS = [
  "data_sharing", "tracking_cookies", "consumer_rights",
  "cross_border", "sensitive_data", "retention",
  "children_teens", "ai_automated_decisions", "other",
] as const;

type Domain = typeof DOMAINS[number];

function domainLabel(d: Domain): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// [MOCK M-01] Static clauses until backend decomposition is wired
const MOCK_CLAUSES: {
  id: string; domain: Domain;
  preview: string; full: string;
}[] = [
  {
    id: "C-001", domain: "data_sharing",
    preview: "We share your personal data with third-party partners for marketing and analytics purposes…",
    full: "We share your personal data with third-party partners for marketing and analytics purposes. Recipients include advertising networks, analytics providers, and business affiliates. We may also share data with government authorities where required by law.",
  },
  {
    id: "C-002", domain: "tracking_cookies",
    preview: "Our website uses cookies and similar tracking technologies to personalise content and analyse traffic…",
    full: "Our website uses cookies and similar tracking technologies to personalise content and analyse traffic. You may opt out of certain cookies via our cookie preference centre. Disabling cookies may affect functionality.",
  },
  {
    id: "C-003", domain: "retention",
    preview: "We retain your data for as long as necessary to fulfil the purposes outlined in this notice…",
    full: "We retain your data for as long as necessary to fulfil the purposes outlined in this notice or as required by applicable law. Specific retention periods vary by data type and are available on request.",
  },
  {
    id: "C-004", domain: "consumer_rights",
    preview: "You have the right to access, correct, and delete your personal data. Requests can be submitted…",
    full: "You have the right to access, correct, and delete your personal data. You may also object to or restrict certain processing. Requests can be submitted via our privacy portal or by emailing privacy@example.com.",
  },
  {
    id: "C-005", domain: "cross_border",
    preview: "Your data may be transferred to and processed in countries outside your country of residence…",
    full: "Your data may be transferred to and processed in countries outside your country of residence. We rely on Standard Contractual Clauses and adequacy decisions to ensure appropriate protections apply.",
  },
  {
    id: "C-006", domain: "sensitive_data",
    preview: "We may process sensitive categories of data including health information where you have provided consent…",
    full: "We may process sensitive categories of data including health information where you have provided explicit consent, or where processing is necessary for healthcare delivery, fraud prevention, or legal obligations.",
  },
  {
    id: "C-007", domain: "ai_automated_decisions",
    preview: "We use automated decision-making processes, including profiling, to personalise services and detect fraud…",
    full: "We use automated decision-making processes, including profiling, to personalise services and detect fraud. Decisions with significant effects on you may be subject to human review upon request.",
  },
  {
    id: "C-008", domain: "children_teens",
    preview: "Our services are not intended for children under 13. We do not knowingly collect data from minors…",
    full: "Our services are not intended for children under 13. We do not knowingly collect personal data from children. If we become aware of such collection we will delete the data promptly.",
  },
];

type Step = "idle" | "ingesting" | "decomposing" | "classifying" | "ready" | "error";
type InputMode = "url" | "pdf" | "text";

function StepDot({ label, state }: { label: string; state: "idle" | "active" | "done" }) {
  return (
    <div className={`stepper-step ${state}`}>
      <div className="stepper-dot" />
      <span className="stepper-label">{label}</span>
    </div>
  );
}

export function Intake() {
  const navigate = useNavigate();
  const [mode, setMode]           = useState<InputMode>("url");
  const [urlVal, setUrlVal]       = useState("");
  const [textVal, setTextVal]     = useState("");
  const [step, setStep]           = useState<Step>("idle");
  const [verifiedSrc, setVerified]= useState(false);
  const [activeDomain, setActiveDomain] = useState<Domain | "all">("all");
  const [activeClause, setActiveClause] = useState<string | null>(null);
  const [assessmentId, setAssessmentId] = useState<string | null>(null);

  const stepState = (target: Step): "idle" | "active" | "done" => {
    const order: Step[] = ["idle", "ingesting", "decomposing", "classifying", "ready"];
    const cur = order.indexOf(step);
    const tgt = order.indexOf(target);
    if (cur < tgt) return "idle";
    if (cur === tgt) return "active";
    return "done";
  };

  const filteredClauses = MOCK_CLAUSES.filter(
    c => activeDomain === "all" || c.domain === activeDomain
  );

  const handleSubmit = useCallback(async () => {
    if (mode === "url" && !urlVal.trim()) return;
    if (mode === "text" && !textVal.trim()) return;

    setStep("ingesting");
    setVerified(false);

    // [MOCK M-02] Simulate SSRF-safe URL fetch
    await new Promise(r => setTimeout(r, 600));
    if (mode === "url") setVerified(true); // real: read ssrf_protected flag from API

    setStep("decomposing");
    await new Promise(r => setTimeout(r, 700));

    setStep("classifying");
    await new Promise(r => setTimeout(r, 900));

    try {
      // Real API call — fires and captures the assessment_id if available
      const payload =
        mode === "url" ? { url: urlVal } :
        mode === "text" ? { text: textVal } : null;

      if (payload) {
        const res = await api.post("/assessments/", payload).catch(() => null);
        if (res?.notice_id) setAssessmentId(res.notice_id);
      }
    } catch { /* ignore — mock clauses still display */ }

    setStep("ready");
  }, [mode, urlVal, textVal]);

  const handleViewAssessment = useCallback(() => {
    if (assessmentId) {
      navigate(`/reports/${assessmentId}`);
    } else {
      navigate("/assessments");
    }
  }, [assessmentId, navigate]);

  const isProcessing = ["ingesting", "decomposing", "classifying"].includes(step);
  const isReady = step === "ready";

  return (
    <div>
      <PageHeader
        eyebrow="Intake"
        title="Submit a Privacy Notice"
        description="Add a notice by URL, PDF, or pasted text. Visentix splits it into individual clauses, sorts each into a privacy domain, and prepares it for scoring — you can watch each step below."
      />

      <div className="intake-layout">
      {/* ─── LEFT PANE ─── */}
      <div className="intake-left">
        <div className="intake-left-header">
          <h2>Privacy Notice</h2>

          {/* Input mode tabs */}
          <div className="intake-tabs" role="tablist" aria-label="Input method">
            {(["url", "pdf", "text"] as InputMode[]).map(m => (
              <button
                key={m}
                className={`intake-tab ${mode === m ? "active" : ""}`}
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
              >
                {m === "url" ? "URL" : m === "pdf" ? "PDF Upload" : "Paste Text"}
              </button>
            ))}
          </div>
        </div>

        {/* Form body */}
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
                aria-describedby={verifiedSrc ? "verified-source-label" : undefined}
              />
              {verifiedSrc && (
                <div className="verified-source-mark" id="verified-source-label">
                  <span>✓</span> Verified source
                </div>
              )}
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
          {mode === "pdf" && (
            <div className="intake-field">
              <label htmlFor="intake-pdf">Upload PDF</label>
              <input
                id="intake-pdf"
                type="file"
                accept=".pdf,application/pdf"
                disabled={isProcessing}
              />
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 6 }}>
                Max 10 MB · PDF, HTML, or plain text
              </p>
            </div>
          )}
        </div>

        {/* Progress stepper */}
        <div className="intake-stepper">
          <div className="intake-stepper-title">Processing pipeline</div>
          <div className="stepper-row">
            <StepDot label="Ingest"    state={stepState("ingesting")} />
            <div className="stepper-line" />
            <StepDot label="Decompose" state={stepState("decomposing")} />
            <div className="stepper-line" />
            <StepDot label="Classify"  state={stepState("classifying")} />
          </div>
        </div>

        {/* Actions */}
        <div className="intake-actions">
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={isProcessing || isReady}
            aria-busy={isProcessing}
            id="intake-submit-btn"
          >
            {isProcessing ? "Processing…" : "Analyse Notice"}
          </button>
          {step === "error" && (
            <span style={{ fontSize: "0.82rem", color: "var(--red)" }}>
              Could not process this notice. Please try again.
            </span>
          )}
        </div>
      </div>

      {/* ─── RIGHT PANE ─── */}
      <div className="intake-right">
        <div className="intake-right-header">
          <h2>Extracted Clauses</h2>
          <div className="clause-count-bar">
            <strong>{filteredClauses.length}</strong> clauses
            {activeDomain !== "all" && <> in <strong>{domainLabel(activeDomain as Domain)}</strong></>}
            {isReady && (
              <>
                &nbsp;·&nbsp;
                {/* Honest count — distinct domains actually present in extracted clauses */}
                <strong>{new Set(MOCK_CLAUSES.map(c => c.domain)).size}</strong> domains detected
              </>
            )}
            {/* [MOCK M-01] badge */}
            {isReady && <span className="mock-badge">MOCK M-01</span>}
          </div>
        </div>

        {/* Domain filter */}
        <div className="domain-filter-pills" role="group" aria-label="Filter by domain">
          <button
            className={`domain-pill ${activeDomain === "all" ? "active" : ""}`}
            onClick={() => setActiveDomain("all")}
          >
            All
          </button>
          {DOMAINS.map(d => (
            <button
              key={d}
              className={`domain-pill ${activeDomain === d ? "active" : ""}`}
              onClick={() => setActiveDomain(activeDomain === d ? "all" : d)}
            >
              {domainLabel(d)}
            </button>
          ))}
        </div>

        {/* Clause list */}
        {!isProcessing && !isReady && (
          <div className="intake-empty">
            <div className="intake-empty-icon">◉</div>
            <p className="intake-empty-msg">
              Submit a privacy notice above.<br />
              Clauses will appear here as they are extracted and classified.
            </p>
          </div>
        )}

        {isProcessing && (
          <div className="clause-list">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="processing-shimmer" style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        )}

        {isReady && (
          <div className="clause-list">
            {filteredClauses.map(c => (
              <button
                key={c.id}
                className={`clause-chip ${activeClause === c.id ? "active" : ""}`}
                onClick={() => setActiveClause(activeClause === c.id ? null : c.id)}
                aria-expanded={activeClause === c.id}
                aria-label={`Clause ${c.id} — ${domainLabel(c.domain)}`}
              >
                <div className="cc-header">
                  <span className="cc-code">{c.id}</span>
                  <span className="cc-domain">{domainLabel(c.domain)}</span>
                </div>
                <span className="cc-preview">
                  {activeClause === c.id ? c.full : c.preview}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Ready CTA */}
        {isReady && (
          <div className="intake-ready-cta">
            <p className="ready-label">
              <strong>Classification complete.</strong> Your notice has been analysed.
            </p>
            <button
              className="btn btn-primary"
              onClick={handleViewAssessment}
              id="intake-view-assessment-btn"
            >
              View Assessment →
            </button>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
