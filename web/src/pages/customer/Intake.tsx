/**
 * Intake — submit a privacy notice. A form, not a waiting room.
 *
 * Submitting POSTs to `/assessments/async`, which returns 202 + a job handle;
 * the job is then handed to the app-shell tracker (`IntakeJobsProvider` /
 * `JobTracker`) and runs in the background. The user is free to navigate away or
 * refresh — progress follows them, and the finished report is one click from the
 * tracker.
 *
 * This page previously carried a results pane that claimed "results will appear
 * here once processing is complete". That was never true: the page sent the user
 * to the report instead. The pane is gone; the claim with it.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { PageHeader } from "../../components/PageHeader";
import { MultiSelectDropdown, type MSDOption } from "../../components/MultiSelectDropdown";
import { useTasks } from "../../jobs/TasksProvider";
import "./intake.css";
import { Button } from "@/components/ui/button";

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

export function Intake() {
  const { track } = useTasks();
  /** Label of the notice just handed to the background tracker, for the inline
   *  confirmation. Cleared as soon as the user edits the form again. */
  const [handedOff, setHandedOff] = useState<string | null>(null);
  const [mode, setMode]         = useState<InputMode>("url");
  const [urlVal, setUrlVal]     = useState("");
  const [textVal, setTextVal]   = useState("");
  const [fileVal, setFileVal]   = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [step, setStep]         = useState<Step>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [canRetry, setCanRetry] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  // ARCH-001A: intake filters. Options come from the engine's real vocabulary
  // (GET /config/intake-options) so they can't drift from what scoring understands.
  type IndustryOpt = { value: string; label: string; industry_id?: string };
  type JurisdictionOpt = { value: string; label: string };
  // Industry is now a multi-select (checkbox dropdown); the FIRST real pick is the
  // primary benchmark cohort server-side. Empty array = not selected.
  const [industries, setIndustries] = useState<string[]>([]);
  const [industryOpts, setIndustryOpts] = useState<IndustryOpt[]>([]);
  const [jurisdictionOpts, setJurisdictionOpts] = useState<JurisdictionOpt[]>([]);
  const [unknownIndustry, setUnknownIndustry] = useState<string>("unknown");
  const [organizationName, setOrganizationName] = useState("");
  const [organizationSize, setOrganizationSize] = useState("");
  const [publicPrivate, setPublicPrivate] = useState("");
  const [geography, setGeography] = useState("");
  const [stateFootprint, setStateFootprint] = useState<string[]>([]);
  const [selectedLaws, setSelectedLaws] = useState<string[]>([]);
  const [dataCategories, setDataCategories] = useState<string[]>([]);
  const [businessPractices, setBusinessPractices] = useState<string[]>([]);
  const [sizeOpts, setSizeOpts] = useState<MSDOption[]>([]);
  const [publicPrivateOpts, setPublicPrivateOpts] = useState<MSDOption[]>([]);
  const [geographyOpts, setGeographyOpts] = useState<MSDOption[]>([]);
  const [footprintOpts, setFootprintOpts] = useState<MSDOption[]>([]);
  const [dataCategoryOpts, setDataCategoryOpts] = useState<MSDOption[]>([]);
  const [practiceOpts, setPracticeOpts] = useState<MSDOption[]>([]);

  useEffect(() => {
    let alive = true;
    api.get("/config/intake-options")
      .then((o: { industries: IndustryOpt[]; jurisdictions: JurisdictionOpt[]; unknown_industry?: string;
        organization_sizes?: MSDOption[]; public_private?: MSDOption[]; geographies?: MSDOption[];
        state_footprint?: MSDOption[]; data_categories?: MSDOption[]; business_practices?: MSDOption[] }) => {
        if (!alive) return;
        setIndustryOpts(o.industries ?? []);
        setJurisdictionOpts(o.jurisdictions ?? []);
        if (o.unknown_industry) setUnknownIndustry(o.unknown_industry);
        setSizeOpts(o.organization_sizes ?? []);
        setPublicPrivateOpts(o.public_private ?? []);
        setGeographyOpts(o.geographies ?? []);
        setFootprintOpts(o.state_footprint ?? []);
        setDataCategoryOpts(o.data_categories ?? []);
        setPracticeOpts(o.business_practices ?? []);
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
  const filtersBlank = industries.length === 0 && selectedLaws.length === 0 && stateFootprint.length === 0;

  // QA-011 polling machinery. The idempotency key is stable across retries of the
  // SAME submission, so a retry resumes the existing job (no duplicate assessment).
  const idempotencyKey = useRef<string>("");
  /** Guards a late submit response from touching state after unmount. Progress
   *  itself is no longer this page's concern — the provider owns it. */
  const cancelled = useRef(false);

  useEffect(() => () => { cancelled.current = true; }, []);

  // Polling now lives in IntakeJobsProvider so a running assessment survives
  // navigation and refresh. This page only submits and hands off.

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
    setStep("submitting");
    setErrorMsg("");
    setCanRetry(false);
    setHandedOff(null);

    // Stable idempotency key: generated once per submission, REUSED on retry so a
    // double-submit/retry can never create a duplicate assessment (QA-011).
    if (!idempotencyKey.current) {
      idempotencyKey.current =
        (globalThis.crypto?.randomUUID?.() ?? `idem-${Date.now()}-${Math.random()}`);
    }

    try {
      const formData = new FormData();
      if (mode === "url") formData.append("url", urlVal);
      else if (mode === "text") formData.append("text", textVal);
      else if (mode === "upload" && fileVal) formData.append("file", fileVal, fileVal.name);
      // ARCH-001A: thread the captured filters (blank fields are simply omitted).
      // Industry is comma-separated (multi-select); the server treats the first
      // entry as the primary benchmark cohort.
      if (industries.length) formData.append("industry", industries.join(","));
      if (organizationName) formData.append("organization_name", organizationName);
      if (organizationSize) formData.append("organization_size", organizationSize);
      if (publicPrivate) formData.append("public_private", publicPrivate);
      if (geography) formData.append("geography", geography);
      if (stateFootprint.length) formData.append("state_footprint", stateFootprint.join(","));
      if (selectedLaws.length) formData.append("selected_laws", selectedLaws.join(","));
      if (dataCategories.length) formData.append("data_categories", dataCategories.join(","));
      if (businessPractices.length) formData.append("business_practices", businessPractices.join(","));
      formData.append("idempotency_key", idempotencyKey.current);

      const sub = await api.postForm("/assessments/async", formData) as {
        assessment_id: string; status: string; stage?: string;
      };
      if (cancelled.current) return;
      const label = mode === "url" ? urlVal
        : mode === "upload" ? (fileVal?.name ?? "Uploaded document")
        : "Pasted notice";
      // Hand the job to the app-shell tracker. From here it is genuinely a
      // background task: the user may navigate away or refresh, and progress
      // keeps reporting itself from server state (F01 AC-15/16).
      track({ taskId: sub.assessment_id, kind: "intake", label, status: "queued", stage: sub.stage || "queued" });
      setStep("idle");
      setReviewing(false);
      idempotencyKey.current = "";
      setHandedOff(label);
    } catch (err: unknown) {
      setStep("error");
      setCanRetry(true);
      setErrorMsg(err instanceof Error ? err.message : "Could not submit the notice.");
    }
  }, [mode, urlVal, textVal, fileVal, industries, organizationName, organizationSize,
    publicPrivate, geography, stateFootprint, selectedLaws, dataCategories,
    businessPractices, track]);

  // A new submission (inputs changed) gets a fresh idempotency key. The review
  // panel remains open and updates live, so the user can verify changed values.
  useEffect(() => { idempotencyKey.current = ""; }, [mode, urlVal, textVal, fileVal,
    industries, organizationName, organizationSize, publicPrivate, geography, stateFootprint,
    selectedLaws, dataCategories, businessPractices]);

  return (
    <div>
      <PageHeader
        eyebrow="Intake"
        title="Submit a Privacy Notice"
        description="Add a notice by URL, pasted text, or an uploaded document (PDF, Word, or text). Visentix extracts clauses, classifies each into a privacy domain, and scores the notice against normalized peers."
      />

      <div className="intake-page">
      {/* ─── LEFT PANE: Form ─── */}
      <div className="intake-main">
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

          <details className="intake-details" open>
            <summary>Organization profile</summary>
            <div className="intake-detail-grid">
              <div className="intake-field"><label htmlFor="organization-name">Organization name</label>
                <input id="organization-name" value={organizationName} onChange={e => setOrganizationName(e.target.value)} disabled={isProcessing} /></div>
              <div className="intake-field"><label htmlFor="organization-size">Organization size</label>
                <select id="organization-size" value={organizationSize} onChange={e => setOrganizationSize(e.target.value)} disabled={isProcessing}>
                  <option value="">Not specified</option>{sizeOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select></div>
              <div className="intake-field"><label htmlFor="public-private">Ownership</label>
                <select id="public-private" value={publicPrivate} onChange={e => setPublicPrivate(e.target.value)} disabled={isProcessing}>
                  <option value="">Not specified</option>{publicPrivateOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select></div>
              <div className="intake-field"><label htmlFor="geography">Geography</label>
                <select id="geography" value={geography} onChange={e => setGeography(e.target.value)} disabled={isProcessing}>
                  <option value="">Not specified</option>{geographyOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select></div>
            </div>
          </details>

          <details className="intake-details" open>
            <summary>Footprint and assessment scope</summary>
          <div className="intake-field">
            <label id="intake-footprint-label">WHERE YOU HAVE CONSUMERS OR OPERATE</label>
            <MultiSelectDropdown
              testId="intake-footprint"
              ariaLabel="State footprint"
              placeholder="Select footprint states…"
              options={footprintOpts}
              selected={stateFootprint}
              onChange={setStateFootprint}
              disabled={isProcessing}
            />
            <span className="intake-field-help">This factual footprint informs regulatory scrutiny.</span>
          </div>

          <div className="intake-field">
            <label id="intake-selected-laws-label">LAWS TO INCLUDE IN THIS ASSESSMENT</label>
            <MultiSelectDropdown
              testId="intake-selected-laws"
              ariaLabel="Selected legal scope"
              placeholder="Select assessment laws…"
              options={jurisdictionChoices}
              selected={selectedLaws}
              onChange={setSelectedLaws}
              disabled={isProcessing}
            />
            <span className="intake-field-help">This controls the requested assessment scope; it does not change your factual footprint.</span>
          </div>
          </details>

          <details className="intake-details">
            <summary>Data and business practices</summary>
            <div className="intake-field">
              <label>DATA CATEGORIES PROCESSED</label>
              <MultiSelectDropdown testId="intake-data-categories" ariaLabel="Data categories processed"
                placeholder="Select data categories…" options={dataCategoryOpts} selected={dataCategories}
                onChange={setDataCategories} disabled={isProcessing} />
            </div>
            <div className="intake-field">
              <label>BUSINESS PRACTICES</label>
              <MultiSelectDropdown testId="intake-business-practices" ariaLabel="Business practices"
                placeholder="Select business practices…" options={practiceOpts} selected={businessPractices}
                onChange={setBusinessPractices} disabled={isProcessing} />
            </div>
          </details>

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
              <span>Organization profile</span>
              <strong>{[
                organizationName || "name not specified",
                sizeOpts.find(o => o.value === organizationSize)?.label ?? organizationSize,
                publicPrivateOpts.find(o => o.value === publicPrivate)?.label ?? publicPrivate,
                geographyOpts.find(o => o.value === geography)?.label ?? geography,
              ].filter(Boolean).join(" · ")}</strong>
            </li>
            <li>
              <span>Benchmark cohort</span>
              <strong>{realIndustries.length
                ? `${industryLabel(realIndustries[0])} peers${realIndustries.length > 1 ? ` (+${realIndustries.length - 1} more selected)` : ""}`
                : "broad cohort (industry not specified)"}</strong>
            </li>
            <li>
              <span>State footprint</span>
              <strong>{stateFootprint.length
                ? stateFootprint.map(c => jurisdictionOpts.find(o => o.value === c)?.label ?? c).join(", ")
                : "not confirmed"}</strong>
            </li>
            <li>
              <span>Selected legal scope</span>
              <strong>{selectedLaws.length
                ? selectedLaws.map(c => jurisdictionOpts.find(o => o.value === c)?.label ?? c).join(", ")
                : "not specified"}</strong>
            </li>
            <li>
              <span>Declared data and practices</span>
              <strong>{[...dataCategories, ...businessPractices].length
                ? [...dataCategories, ...businessPractices].join(", ")
                : "not confirmed; report will label notice-based inferences"}</strong>
            </li>
          </ul>
          <p className="intake-scope-foot">
            Confidence and cohort size are shown with the result; small cohorts are disclosed and may be broadened.
          </p>
        </div>

        <p className="intake-deliverable" data-testid="intake-deliverable">
          Your deliverable includes an on-screen report and a shareable PDF.
        </p>

        {reviewing && (
          <div className="intake-review" data-testid="intake-review">
            <strong>Review assessment scope</strong>
            <p>Confirm the notice source, organization profile, footprint, selected legal scope, data categories, business practices, and proposed peer cohort shown above.</p>
          </div>
        )}

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
          <Button onClick={() => reviewing ? void handleSubmit() : setReviewing(true)}
            disabled={isProcessing}
            aria-busy={isProcessing}
            id="intake-submit-btn"
          >
            {isProcessing ? "Adding to queue…" : reviewing ? "Confirm and analyse" : "Review scope"}
          </Button>
          {canRetry && step === "error" && (
            <Button variant="outline" size="sm" onClick={handleSubmit} data-testid="intake-retry" style={{ marginLeft: 8 }}>
              Retry
            </Button>
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

      {/* The results pane is gone. Processing now runs in the background and
          reports itself in the floating JobTracker, which follows the user
          across routes and survives a refresh — so intake is a form, not a
          waiting room. The old pane also told a lie: it said "results will
          appear here", while the page actually sent the user to the report. */}

      {handedOff && (
        <div className="intake-handoff" role="status" data-testid="intake-handoff">
          <div className="intake-handoff-title">Analysing “{handedOff}” in the background</div>
          <p>
            You can leave this page — progress follows you, and it survives a refresh.
            The tracker in the corner will link to the report when it is ready.
          </p>
          <div className="intake-handoff-actions">
            <Button variant="outline" size="sm" type="button" onClick={() => setHandedOff(null)}>
              Submit another notice
            </Button>
            <Button asChild size="sm"><Link to="/assessments">Go to Assessments</Link></Button>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
