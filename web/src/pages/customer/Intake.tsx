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
import { CheckCircle2, FileText, Info, ListChecks, Upload } from "lucide-react";
import { api } from "../../lib/api";
import { PageHeader } from "../../components/PageHeader";
import { MultiSelectDropdown, type MSDOption } from "../../components/MultiSelectDropdown";
import { useTasks } from "../../jobs/TasksProvider";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

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

// Radix Select items cannot carry an empty value, but "not specified" must stay
// a first-class choice; this sentinel maps back to "" in state.
const UNSPECIFIED = "__unspecified__";

function StepBadge({ n }: { n: number }) {
  return (
    <span aria-hidden className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
      {n}
    </span>
  );
}

/** A single optional org-profile dropdown ("Not specified" is a real choice). */
function ProfileSelect({ id, label, value, onChange, options, disabled }: {
  id: string; label: string; value: string;
  onChange: (v: string) => void; options: MSDOption[]; disabled: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select
        value={value || UNSPECIFIED}
        onValueChange={v => onChange(v === UNSPECIFIED ? "" : v)}
        disabled={disabled}
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue placeholder="Not specified" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={UNSPECIFIED} className="text-muted-foreground">Not specified</SelectItem>
          {options.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

/** One row of the analysis-scope summary: muted when the value is a fallback. */
function ScopeRow({ label, value, fallback }: { label: string; value?: string; fallback: string }) {
  return (
    <div className="flex flex-col gap-0.5 py-2.5 first:pt-0 last:pb-0 sm:grid sm:grid-cols-[11rem_1fr] sm:items-baseline sm:gap-4">
      <span className="text-sm text-muted-foreground">{label}</span>
      {value
        ? <span className="text-sm font-medium">{value}</span>
        : <span className="text-sm text-muted-foreground italic">{fallback}</span>}
    </div>
  );
}

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

  // Analysis-scope summary values (undefined = fall back to the muted default).
  const profileParts = [
    organizationName,
    sizeOpts.find(o => o.value === organizationSize)?.label ?? organizationSize,
    publicPrivateOpts.find(o => o.value === publicPrivate)?.label ?? publicPrivate,
    geographyOpts.find(o => o.value === geography)?.label ?? geography,
  ].filter(Boolean);

  return (
    <div>
      <PageHeader
        eyebrow="Intake"
        title="Submit a Privacy Notice"
        description="Add a notice by URL, pasted text, or an uploaded document (PDF, Word, or text). Visentix extracts clauses, classifies each into a privacy domain, and scores the notice against normalized peers."
      />

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">

        {/* ─── Step 1: the notice itself ─── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5">
              <StepBadge n={1} />
              Provide the notice
            </CardTitle>
            <CardDescription className="pl-[2.125rem]">
              Link to it, paste its text, or upload the document.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={mode} onValueChange={v => { setMode(v as InputMode); setErrorMsg(""); }}>
              <TabsList className="grid w-full grid-cols-3" aria-label="Input method">
                <TabsTrigger value="url" disabled={isProcessing}>URL</TabsTrigger>
                <TabsTrigger value="text" disabled={isProcessing}>Paste text</TabsTrigger>
                <TabsTrigger value="upload" disabled={isProcessing}>Upload</TabsTrigger>
              </TabsList>

              <TabsContent value="url" className="mt-3 flex flex-col gap-1.5">
                <Label htmlFor="intake-url">Privacy Notice URL</Label>
                <Input
                  id="intake-url"
                  type="url"
                  placeholder="https://example.com/privacy"
                  value={urlVal}
                  onChange={e => setUrlVal(e.target.value)}
                  disabled={isProcessing}
                />
                <p className="text-xs text-muted-foreground">We fetch the page and read the notice exactly as published.</p>
              </TabsContent>

              <TabsContent value="text" className="mt-3 flex flex-col gap-1.5">
                <Label htmlFor="intake-text">Notice text</Label>
                <Textarea
                  id="intake-text"
                  rows={10}
                  className="min-h-48"
                  placeholder="Paste the full text of the privacy notice…"
                  value={textVal}
                  onChange={e => setTextVal(e.target.value)}
                  disabled={isProcessing}
                />
              </TabsContent>

              <TabsContent value="upload" className="mt-3">
                <label
                  htmlFor="intake-file"
                  className={cn(
                    "group flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-input p-8 text-center transition-colors",
                    dragOver ? "border-ring bg-accent/60" : "hover:border-ring/60 hover:bg-accent/40",
                    fileVal && "border-solid bg-muted/40",
                    isProcessing && "pointer-events-none opacity-50",
                  )}
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
                    className="hidden"
                  />
                  {fileVal ? (
                    <>
                      <span className="flex size-10 items-center justify-center rounded-full bg-muted">
                        <FileText className="size-5 text-muted-foreground" />
                      </span>
                      <span className="text-sm font-medium">{fileVal.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {(fileVal.size / 1024).toFixed(0)} KB · click to replace
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="flex size-10 items-center justify-center rounded-full bg-muted transition-colors group-hover:bg-accent">
                        <Upload className="size-5 text-muted-foreground" />
                      </span>
                      <span className="text-sm">
                        <span className="font-medium">Drag a file here</span>
                        <span className="text-muted-foreground"> or click to browse</span>
                      </span>
                      <span className="text-xs text-muted-foreground">PDF, Word (.docx), or plain text — up to 10 MB</span>
                    </>
                  )}
                </label>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* ─── Step 2: ARCH-001A intake filters (industry + scope) ─── */}
        <Card data-testid="intake-filters">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5">
              <StepBadge n={2} />
              Describe your organization
            </CardTitle>
            <CardDescription className="pl-[2.125rem]">
              Optional, but it sharpens your peer benchmark and the legal scope of the assessment.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label id="intake-industry-label">Industry</Label>
                <MultiSelectDropdown
                  testId="intake-industry"
                  ariaLabel="Industry"
                  placeholder="Select industries…"
                  options={industryChoices}
                  selected={industries}
                  onChange={setIndustries}
                  disabled={isProcessing}
                />
                <p className="text-xs text-muted-foreground">Determines your peer benchmark cohort — the first selection is primary.</p>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="organization-name">Organization name</Label>
                <Input
                  id="organization-name"
                  placeholder="Acme Inc."
                  value={organizationName}
                  onChange={e => setOrganizationName(e.target.value)}
                  disabled={isProcessing}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <ProfileSelect id="organization-size" label="Organization size"
                value={organizationSize} onChange={setOrganizationSize}
                options={sizeOpts} disabled={isProcessing} />
              <ProfileSelect id="public-private" label="Ownership"
                value={publicPrivate} onChange={setPublicPrivate}
                options={publicPrivateOpts} disabled={isProcessing} />
              <ProfileSelect id="geography" label="Geography"
                value={geography} onChange={setGeography}
                options={geographyOpts} disabled={isProcessing} />
            </div>

            <Separator />

            <div className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold">Footprint and assessment scope</h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label id="intake-footprint-label">Where you have consumers or operate</Label>
                  <MultiSelectDropdown
                    testId="intake-footprint"
                    ariaLabel="State footprint"
                    placeholder="Select footprint states…"
                    options={footprintOpts}
                    selected={stateFootprint}
                    onChange={setStateFootprint}
                    disabled={isProcessing}
                  />
                  <p className="text-xs text-muted-foreground">This factual footprint informs regulatory scrutiny.</p>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label id="intake-selected-laws-label">Laws to include in this assessment</Label>
                  <MultiSelectDropdown
                    testId="intake-selected-laws"
                    ariaLabel="Selected legal scope"
                    placeholder="Select assessment laws…"
                    options={jurisdictionChoices}
                    selected={selectedLaws}
                    onChange={setSelectedLaws}
                    disabled={isProcessing}
                  />
                  <p className="text-xs text-muted-foreground">Sets the requested assessment scope; it does not change your factual footprint.</p>
                </div>
              </div>
            </div>

            <Separator />

            <div className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold">Data and business practices</h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label>Data categories processed</Label>
                  <MultiSelectDropdown testId="intake-data-categories" ariaLabel="Data categories processed"
                    placeholder="Select data categories…" options={dataCategoryOpts} selected={dataCategories}
                    onChange={setDataCategories} disabled={isProcessing} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Business practices</Label>
                  <MultiSelectDropdown testId="intake-business-practices" ariaLabel="Business practices"
                    placeholder="Select business practices…" options={practiceOpts} selected={businessPractices}
                    onChange={setBusinessPractices} disabled={isProcessing} />
                </div>
              </div>
            </div>

            {filtersBlank && (
              <p className="flex items-start gap-2 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground" data-testid="intake-filters-note">
                <Info aria-hidden className="mt-px size-3.5 shrink-0" />
                Without this, your notice is scored against a broad cohort and general US exposure.
              </p>
            )}
          </CardContent>
        </Card>

        {/* ─── Step 3: ARCH-001B review analysis scope — a live, plain-English
            summary of what will drive the assessment, separating what you
            DECLARED from what is DETECTED from the notice. Only reflects inputs
            the engine actually consumes. ─── */}
        <Card data-testid="intake-scope">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5">
              <StepBadge n={3} />
              Analysis scope
            </CardTitle>
            <CardDescription className="pl-[2.125rem]">
              A live summary of what will drive this assessment — updates as you fill in the form.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-border/60">
              <ScopeRow label="Organization profile"
                value={profileParts.length ? profileParts.join(" · ") : undefined}
                fallback="Not specified" />
              <ScopeRow label="Benchmark cohort"
                value={realIndustries.length
                  ? `${industryLabel(realIndustries[0])} peers${realIndustries.length > 1 ? ` (+${realIndustries.length - 1} more selected)` : ""}`
                  : undefined}
                fallback="Broad cohort — industry not specified" />
              <ScopeRow label="State footprint"
                value={stateFootprint.length
                  ? stateFootprint.map(c => footprintOpts.find(o => o.value === c)?.label ?? c).join(", ")
                  : undefined}
                fallback="Not confirmed" />
              <ScopeRow label="Selected legal scope"
                value={selectedLaws.length
                  ? selectedLaws.map(c => jurisdictionOpts.find(o => o.value === c)?.label ?? c).join(", ")
                  : undefined}
                fallback="Not specified" />
              <ScopeRow label="Declared data and practices"
                value={[...dataCategories, ...businessPractices].length
                  ? [...dataCategories, ...businessPractices].join(", ")
                  : undefined}
                fallback="Not confirmed — the report will label notice-based inferences" />
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Confidence and cohort size are shown with the result; small cohorts are disclosed and may be broadened.
            </p>
          </CardContent>
        </Card>

        {reviewing && (
          <div className="flex gap-3 rounded-lg border bg-muted/40 p-4" data-testid="intake-review">
            <ListChecks aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <div className="text-sm">
              <p className="font-medium">Review assessment scope</p>
              <p className="mt-1 text-muted-foreground">
                Confirm the notice source, organization profile, footprint, selected legal scope,
                data categories, business practices, and proposed peer cohort shown above.
              </p>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => reviewing ? void handleSubmit() : setReviewing(true)}
            disabled={isProcessing}
            aria-busy={isProcessing}
            id="intake-submit-btn"
          >
            {isProcessing ? "Adding to queue…" : reviewing ? "Confirm and analyse" : "Review scope"}
          </Button>
          {canRetry && step === "error" && (
            <Button variant="outline" size="sm" onClick={handleSubmit} data-testid="intake-retry">
              Retry
            </Button>
          )}
          {(step === "error" || errorMsg) && (
            <span className="text-sm text-destructive">
              {errorMsg || "Could not process this notice."}
              {mode === "upload" && step === "error" && (
                <span className="text-muted-foreground">
                  {" "}You can also paste the text or submit the notice URL instead.
                </span>
              )}
            </span>
          )}
        </div>

        <p className="text-sm text-muted-foreground" data-testid="intake-deliverable">
          Your deliverable includes an on-screen report and a shareable PDF.
        </p>

        {/* QA-012: honest processing / retention / confidentiality disclosure. Wording
            matches the owner-approved privacy notice (decision-log 2026-07-28); no
            invented legal promises. */}
        <p className="max-w-prose text-xs leading-relaxed text-muted-foreground" data-testid="intake-disclosure">
          <strong className="text-foreground">How your notice is handled.</strong> It is processed on Visentix's own
          infrastructure to generate your assessment — <strong>not</strong> sent to any
          third-party AI provider and <strong>not</strong> used to train third-party models.
          De-identified, aggregated patterns may improve Visentix's own accuracy. Content is
          retained and protected per our{" "}
          <a href="/privacy" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-foreground">Privacy Policy</a>.
        </p>

        {/* The results pane is gone. Processing now runs in the background and
            reports itself in the floating JobTracker, which follows the user
            across routes and survives a refresh — so intake is a form, not a
            waiting room. The old pane also told a lie: it said "results will
            appear here", while the page actually sent the user to the report. */}

        {handedOff && (
          <div className="flex gap-3 rounded-lg border bg-card p-5 shadow-sm" role="status" data-testid="intake-handoff">
            <CheckCircle2 aria-hidden className="mt-0.5 size-5 shrink-0 text-standing-good" />
            <div>
              <div className="text-base font-semibold">Analysing “{handedOff}” in the background</div>
              <p className="mt-1 text-sm text-muted-foreground">
                You can leave this page — progress follows you, and it survives a refresh.
                The tracker in the corner will link to the report when it is ready.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" type="button" onClick={() => setHandedOff(null)}>
                  Submit another notice
                </Button>
                <Button asChild size="sm"><Link to="/assessments">Go to Assessments</Link></Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
