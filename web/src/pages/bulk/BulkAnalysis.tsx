/**
 * F19 — Bulk Screening (regulator / law-firm / insurer journeys) · REAL UI.
 *
 * Replaces the F12 bulk mock (M-23/M-24). Product surface on the verified
 * reassessment kernel: Upload (CSV/JSON + client-side validation preview) →
 * Job list (status chips, progress, 5s auto-poll while running) → Results grid
 * (sortable columns, domain filter chips, sector heat strip, draft-grade badge
 * throughout, Export CSV). A score-cell click opens the draft report (gold
 * watermark shows naturally). Failed rows show their error inline;
 * insufficient_profile is explained in plain English (SME copy).
 *
 * Guardrail posture: EXPOSURE / maturity measurement, never a verdict. Every
 * number is draft-grade and VCI-suppressed when confidence is low.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { PageHeader } from "../../components/PageHeader";
import { FlashNotice } from "../../components/FlashNotice";
import { VciBadge } from "../../report/VciBadge";
import { useFlash } from "../../lib/useFlash";
import { scoreBandColor, vciBand } from "../../lib/scoreBands";
import { api, ApiError } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { statusLabel } from "../../lib/labels";

// 8 taxonomy domains (backend heatmap TAXONOMY_DOMAINS order) + short labels.
const DOMAINS = [
  "ai_automated_decisions", "children_teens", "consumer_rights", "cross_border",
  "data_sharing", "retention", "sensitive_data", "tracking_cookies",
] as const;
const DOMAIN_LABEL: Record<string, string> = {
  ai_automated_decisions: "AI decisions", children_teens: "Children",
  consumer_rights: "Consumer rights", cross_border: "Cross-border",
  data_sharing: "Data sharing", retention: "Retention",
  sensitive_data: "Sensitive data", tracking_cookies: "Tracking",
};

const INSUFFICIENT_PROFILE_TEXT =
  "Not scored — we could not build a reliable company profile or peer " +
  "comparison from public information. No score is shown rather than an unfair one.";

type RowStatus = "pending" | "running" | "succeeded" | "failed" | "insufficient_profile";
interface JobRow { position: number; org_name: string; notice_url: string; status: RowStatus; assessment_id: string | null; error: string | null; }
interface Job { id: string; label: string; status: string; row_count: number; completed_count: number; failed_count: number; created_at: string; finished_at: string | null; rows?: JobRow[]; }
interface DomainScore { domain: string; score: number | null; }
interface Result { org_name: string; assessment_id: string; review_status: string; overall: number | null; suppressed_reason: string | null; domain_scores: DomainScore[]; cohort: { n: number; relaxation_label: string }; top_findings: { code: string; domain: string; severity: string }[]; vci: number | null; }
interface HeatCell { domain: string; mean: number | null; n: number; }

/* Job status is a KIND, mapped once — it used to be a class interpolated off
   the raw status ("bulk-status-chip st-partial"), so an unmapped status
   rendered an unstyled chip carrying the database's own word. */
const JOB_STATUS_VARIANT: Record<string, "default" | "verified" | "provisional" | "standing-bad" | "secondary"> = {
  queued: "default", running: "default",
  completed: "verified", partial: "provisional", failed: "standing-bad",
};

const DraftBadge = () => (
  <Badge variant="provisional" title="Screening intelligence — automated analysis, not expert-reviewed.">Draft-grade</Badge>
);

const StatusChip = ({ status }: { status: string }) => (
  <Badge variant={JOB_STATUS_VARIANT[status] ?? "secondary"}>{statusLabel(status)}</Badge>
);

// ── Parse + validate the upload before submit ────────────────
interface ParsedRow { org_name: string; notice_url: string; valid: boolean; }
function urlWellFormed(u: string): boolean {
  try { const p = new URL(u.trim()); return p.protocol === "http:" || p.protocol === "https:"; }
  catch { return false; }
}
function parseCsv(text: string): ParsedRow[] {
  const lines = text.split(/\r?\n/).filter(l => l.trim());
  if (!lines.length) return [];
  const header = lines[0].split(",").map(h => h.trim().toLowerCase());
  const oi = header.indexOf("org_name"), ui = header.indexOf("notice_url");
  const start = oi >= 0 && ui >= 0 ? 1 : 0;
  return lines.slice(start).map(l => {
    const cells = l.split(",");
    const org_name = (start ? cells[oi] : cells[0] || "").trim();
    const notice_url = (start ? cells[ui] : cells[1] || cells[0] || "").trim();
    return { org_name, notice_url, valid: urlWellFormed(notice_url) };
  });
}
function parseJson(text: string): ParsedRow[] {
  try {
    const obj = JSON.parse(text);
    const rows = Array.isArray(obj) ? obj : obj.rows;
    if (!Array.isArray(rows)) return [];
    return rows.map((r: { org_name?: string; notice_url?: string }) => ({
      org_name: (r.org_name || "").trim(), notice_url: (r.notice_url || "").trim(),
      valid: urlWellFormed(r.notice_url || ""),
    }));
  } catch { return []; }
}

export function BulkAnalysis() {
  const [view, setView] = useState<"upload" | "list" | "results">("list");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [flash, showFlash] = useFlash();

  const loadJobs = useCallback(async () => {
    try { setJobs(await api.get("/bulk/jobs")); }
    catch (e) { if (e instanceof ApiError && e.status === 403) showFlash("Bulk screening requires an analyst or admin role."); }
  }, [showFlash]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => { void loadJobs(); }, 0);
    return () => window.clearTimeout(initialLoad);
  }, [loadJobs]);

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  return (
    <div>
      <PageHeader
        eyebrow="Bulk"
        title="Bulk Screening"
        description="Screen many organisations' notices at once. Results are a draft-grade, risk-ranked exposure grid — every number carries confidence, cohort size, and a not-expert-reviewed badge. Exposure and maturity measurement, never a verdict."
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <Button type="button" size="sm" variant={view === "list" ? "default" : "outline"} aria-pressed={view === "list"} onClick={() => { setView("list"); loadJobs(); }}>Jobs</Button>
            <Button type="button" size="sm" variant={view === "upload" ? "default" : "outline"} aria-pressed={view === "upload"} onClick={() => setView("upload")}>New screening</Button>
          </div>
        }
      />
      <FlashNotice message={flash} />

      {view === "upload" && (
        <UploadStep onSubmitted={(id) => { showFlash("Screening queued — rows will fill in as they finish."); setSelectedJobId(id); setView("results"); loadJobs(); }} showFlash={showFlash} />
      )}
      {view === "list" && (
        <JobList jobs={jobs} onOpen={(id) => { setSelectedJobId(id); setView("results"); }} onRefresh={loadJobs} />
      )}
      {view === "results" && selectedJobId && (
        <ResultsGrid jobId={selectedJobId} onBack={() => { setView("list"); loadJobs(); }} showFlash={showFlash} />
      )}
    </div>
  );
}

// ── Upload step ──────────────────────────────────────────────
function UploadStep({ onSubmitted, showFlash }: { onSubmitted: (id: string) => void; showFlash: (m: string) => void }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const reparse = useCallback((raw: string) => {
    const t = raw.trim();
    if (!t) { setRows([]); return; }
    setRows(t.startsWith("{") || t.startsWith("[") ? parseJson(t) : parseCsv(t));
  }, []);

  const onFile = async (f: File) => {
    setFile(f); const t = await f.text(); setText(t); reparse(t);
  };

  const validCount = rows.filter(r => r.valid).length;
  const invalidCount = rows.length - validCount;
  const overCap = rows.length > 200;

  const submit = async () => {
    setSubmitting(true);
    try {
      let resp;
      if (file) {
        const fd = new FormData(); fd.append("file", file); if (label) fd.append("label", label);
        resp = await api.postForm("/bulk/jobs", fd);
      } else {
        resp = await api.post("/bulk/jobs", { label, rows: rows.map(r => ({ org_name: r.org_name, notice_url: r.notice_url })) });
      }
      onSubmitted(resp.bulk_job_id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) showFlash("A screening job is already running for your organisation — wait for it to finish before starting another.");
      else if (e instanceof ApiError && e.status === 400) showFlash(`Rejected: ${e.message}`);
      else showFlash("Submit failed — please try again.");
    } finally { setSubmitting(false); }
  };

  return (
    <div className="grid gap-6">
      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <div className="mb-2.5 text-[0.7rem] font-bold uppercase tracking-wider text-muted-foreground">Upload company list</div>
        <input className="mb-3 h-9 w-full rounded-md border bg-transparent px-3 py-1 text-[0.86rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" placeholder="Label (optional) — e.g. Q3 retail sector scan"
               value={label} onChange={e => setLabel(e.target.value)} />
        <div
          className="rounded-md border-[1.5px] border-dashed border-muted-foreground p-5.5 text-center text-[0.86rem] text-muted-foreground"
          onDragOver={e => e.preventDefault()}
          onDrop={async e => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) await onFile(f); }}
        >
          Drag a CSV (headers <code>org_name,notice_url</code>) here, or paste CSV / JSON below.
          <textarea
            className="mt-2.5 min-h-[88px] w-full resize-y rounded-md border bg-transparent px-3 py-2.5 font-data text-[0.84rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
            placeholder={"org_name,notice_url\nAcme Retail,https://acme.example/privacy\n…\n\n— or JSON —\n{ \"rows\": [{ \"org_name\": \"Acme\", \"notice_url\": \"https://acme.example/privacy\" }] }"}
            value={text}
            onChange={e => { setFile(null); setText(e.target.value); reparse(e.target.value); }}
          />
          <input type="file" accept=".csv,text/csv" onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
        </div>
      </Card>

      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <div className="mb-2.5 text-[0.7rem] font-bold uppercase tracking-wider text-muted-foreground">Validation preview</div>
        {rows.length === 0 ? (
          <div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">Paste or drop a list to preview it before submitting.</div>
        ) : (
          <>
            <div className="mb-2.5 flex gap-3 text-[0.8rem] [&_.ok]:font-bold [&_.ok]:text-[var(--verified)] [&_.bad]:font-bold [&_.bad]:text-[var(--standing-bad)]">
              <span>{rows.length} rows</span>
              <span className="ok">{validCount} valid</span>
              {invalidCount > 0 && <span className="bad">{invalidCount} malformed URL{invalidCount > 1 ? "s" : ""}</span>}
              {overCap && <span className="bad">over the 200-row cap</span>}
            </div>
            <div className="max-h-[320px] overflow-y-auto rounded-md border">
              {rows.slice(0, 50).map((r, i) => (
                <div key={i} className={cn(
                  "grid grid-cols-[1.1fr_2fr_auto] items-center gap-2.5 border-b px-3 py-1.5 text-[0.8rem] last:border-b-0",
                  !r.valid && "bg-[color-mix(in_oklab,var(--standing-bad)_6%,transparent)]",
                )}>
                  <span className="font-semibold">{r.org_name || <em>(no name)</em>}</span>
                  <span className="overflow-hidden text-ellipsis whitespace-nowrap font-data text-muted-foreground">{r.notice_url || <em>(no url)</em>}</span>
                  {!r.valid && <span className="text-[0.68rem] font-bold text-[var(--standing-bad)]">malformed — will fail alone</span>}
                </div>
              ))}
              {rows.length > 50 && <div className="px-3 py-2 text-[0.78rem] italic text-muted-foreground">…and {rows.length - 50} more</div>}
            </div>
            <Button style={{ marginTop: 12 }} disabled={submitting || overCap || rows.length === 0} onClick={submit}>
              {submitting ? "Submitting…" : `Run screening · ${rows.length} organisations`}
            </Button>
            {overCap && <div className="mt-2 text-[0.78rem] text-[var(--standing-bad)]">Trim to 200 rows or fewer — the cap is enforced server-side.</div>}
          </>
        )}
      </Card>
    </div>
  );
}

// ── Job list ─────────────────────────────────────────────────
function JobList({ jobs, onOpen, onRefresh }: { jobs: Job[]; onOpen: (id: string) => void; onRefresh: () => void }) {
  const anyRunning = jobs.some(j => j.status === "running" || j.status === "queued");
  useEffect(() => {
    if (!anyRunning) return;
    const t = setInterval(onRefresh, 5000); // auto-poll while running
    return () => clearInterval(t);
  }, [anyRunning, onRefresh]);

  if (!jobs.length) return <Card className="rounded-lg border bg-card px-5.5 py-5"><div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">No screening jobs yet. Start one with “New screening”.</div></Card>;
  return (
    <Card className="rounded-lg border bg-card px-5.5 py-5">
      <Card className="mb-3.5 flex items-center justify-between font-sans text-[1.05rem] font-semibold"><span>Screening jobs</span></Card>
      <table className="w-full border-collapse text-[0.84rem] [&_th]:border-b [&_th]:px-2.5 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-[0.72rem] [&_th]:uppercase [&_th]:tracking-wider [&_th]:text-muted-foreground [&_td]:border-b [&_td]:px-2.5 [&_td]:py-2.5 [&_td]:text-left">
        <thead><tr><th>Label</th><th>Status</th><th>Progress</th><th>Created</th><th></th></tr></thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.id}>
              <td>{j.label || <em>(untitled)</em>}</td>
              <td><StatusChip status={j.status} /></td>
              <td>
                <div className="mb-1 h-1.5 overflow-hidden rounded-sm bg-border [&>span]:block [&>span]:h-full [&>span]:rounded-sm [&>span]:bg-[var(--verified)] [&>span]:transition-[width] [&>span]:duration-200 motion-reduce:[&>span]:transition-none"><span style={{ width: `${j.row_count ? (100 * (j.completed_count + j.failed_count)) / j.row_count : 0}%` }} /></div>
                <span className="text-[0.74rem] tabular-nums text-muted-foreground">{j.completed_count + j.failed_count}/{j.row_count}{j.failed_count ? ` · ${j.failed_count} not scored` : ""}</span>
              </td>
              <td>{new Date(j.created_at).toLocaleString()}</td>
              <td><Button onClick={() => onOpen(j.id)}>Open</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

// ── Results grid ─────────────────────────────────────────────
type SortKey = "org" | "overall" | "cohort" | "vci" | string;
function ResultsGrid({ jobId, onBack, showFlash }: { jobId: string; onBack: () => void; showFlash: (m: string) => void }) {
  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [heat, setHeat] = useState<HeatCell[]>([]);
  const [domainFilter, setDomainFilter] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "overall", dir: -1 });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const j: Job = await api.get(`/bulk/jobs/${jobId}`);
      setJob(j);
      const r = await api.get(`/bulk/jobs/${jobId}/results`);
      setResults(r.results || []); setHeat(r.sector_heat_strip || []);
      return j.status;
    } catch { return "failed"; }
  }, [jobId]);

  useEffect(() => {
    let cancelled = false;
    const initialLoad = window.setTimeout(() => {
      void load().then(status => {
        if (cancelled) return;
        if (status === "running" || status === "queued") {
          pollRef.current = setInterval(async () => { const s = await load(); if (s !== "running" && s !== "queued" && pollRef.current) clearInterval(pollRef.current); }, 5000);
        }
      });
    }, 0);
    return () => { cancelled = true; window.clearTimeout(initialLoad); if (pollRef.current) clearInterval(pollRef.current); };
  }, [load]);

  const exportCsv = async () => {
    try {
      const csv = await api.getText(`/bulk/jobs/${jobId}/export.csv`);
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `bulk_screening_${jobId.slice(0, 8)}.csv`; a.click();
      URL.revokeObjectURL(url);
    } catch { showFlash("Export failed."); }
  };

  const domVal = (r: Result, d: string) => r.domain_scores.find(c => c.domain === d)?.score ?? null;
  const sorted = useMemo(() => {
    const arr = [...results];
    arr.sort((a, b) => {
      let av: number | string | null, bv: number | string | null;
      if (sort.key === "org") { av = a.org_name.toLowerCase(); bv = b.org_name.toLowerCase(); }
      else if (sort.key === "overall") { av = a.overall; bv = b.overall; }
      else if (sort.key === "cohort") { av = a.cohort.n; bv = b.cohort.n; }
      else if (sort.key === "vci") { av = a.vci; bv = b.vci; }
      else { av = domVal(a, sort.key); bv = domVal(b, sort.key); }
      if (av === null) return 1; if (bv === null) return -1; // suppressed/absent sink
      return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir;
    });
    return arr;
  }, [results, sort]);

  const filtered = domainFilter.size === 0 ? sorted
    : sorted.filter(r => [...domainFilter].some(d => (domVal(r, d) ?? 0) > 0));

  const setSortKey = (key: SortKey) => setSort(s => s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: -1 });
  const cell = (v: number | null) => v === null
    ? <span className="text-[0.74rem] italic text-muted-foreground" title="Suppressed — confidence below the presentation threshold.">suppressed</span>
    : <span style={{ color: scoreBandColor(v), fontWeight: 600 }}>{v.toFixed(1)}</span>;

  const rows = job?.rows || [];
  const nonScored = rows.filter(r => r.status === "failed" || r.status === "insufficient_profile");

  return (
    <div>
      <div className="mb-4.5 flex flex-wrap items-center gap-3">
        <Button onClick={onBack}>← Jobs</Button>
        <span className="flex items-center gap-2 font-sans text-[1.1rem] font-semibold">{job?.label || "Screening"} <StatusChip status={job?.status || "…"} /></span>
        <DraftBadge />
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <span className="text-[0.74rem] tabular-nums text-muted-foreground">{job ? `${job.completed_count + job.failed_count}/${job.row_count} processed` : ""}</span>
          <Button onClick={exportCsv} disabled={!results.length}>Export CSV</Button>
        </div>
      </div>

      {/* Sector heat strip — aggregate domain means over succeeded rows */}
      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <div className="mb-2.5 text-[0.7rem] font-bold uppercase tracking-wider text-muted-foreground">Sector heat strip · aggregate domain means (succeeded rows)</div>
        <div className="grid grid-cols-4 gap-1.5 md:grid-cols-8">
          {DOMAINS.map(d => {
            const h = heat.find(c => c.domain === d);
            const m = h?.mean ?? null;
            return (
              <div key={d} className="text-center" title={`${DOMAIN_LABEL[d]} · n=${h?.n ?? 0}`}>
                <div className="rounded-md px-1 py-3.5 font-data text-[0.9rem] font-bold tabular-nums text-[var(--primary-foreground)]" style={{ background: m === null ? "var(--border)" : scoreBandColor(m) }}>{m === null ? "—" : m.toFixed(0)}</div>
                <div className="mt-1 text-[0.68rem] text-muted-foreground">{DOMAIN_LABEL[d]}</div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Domain filter chips */}
      <div className="flex flex-wrap gap-2">
        {DOMAINS.map(d => (
          <Button key={d} type="button" size="sm" className="rounded-full"
            variant={domainFilter.has(d) ? "default" : "outline"} aria-pressed={domainFilter.has(d)}
                  onClick={() => setDomainFilter(prev => { const n = new Set(prev); if (n.has(d)) n.delete(d); else n.add(d); return n; })}>
            {DOMAIN_LABEL[d]}
          </Button>
        ))}
        {domainFilter.size > 0 && <Button type="button" size="sm" variant="ghost" className="rounded-full italic" onClick={() => setDomainFilter(new Set())}>Clear</Button>}
      </div>

      <Card className="overflow-x-auto rounded-lg border bg-card px-5.5 py-5">
        {results.length === 0 ? (
          <div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">{job && (job.status === "running" || job.status === "queued") ? "Scoring in progress — succeeded rows will appear here as they finish." : "No succeeded rows yet."}</div>
        ) : (
          <table className="w-full border-collapse text-[0.84rem] [&_th]:whitespace-nowrap [&_th]:border-b [&_th]:p-2 [&_th]:text-left [&_td]:whitespace-nowrap [&_td]:border-b [&_td]:p-2 [&_td]:text-left [&_.dom]:text-center [&_.dom]:text-[0.78rem] [&_.sortable]:cursor-pointer [&_.sortable]:select-none [&_.sortable]:text-[0.7rem] [&_.sortable]:uppercase [&_.sortable]:tracking-wider [&_.sortable]:text-muted-foreground [&_.clickable_a]:no-underline">
            <thead>
              <tr>
                <th className="sortable" onClick={() => setSortKey("org")}>Organisation</th>
                <th className="sortable" onClick={() => setSortKey("overall")}>Overall</th>
                {DOMAINS.map(d => <th key={d} className="sortable dom" onClick={() => setSortKey(d)} title={DOMAIN_LABEL[d]}>{DOMAIN_LABEL[d]}</th>)}
                <th className="sortable" onClick={() => setSortKey("cohort")}>Cohort n</th>
                <th className="sortable" onClick={() => setSortKey("vci")}>Confidence</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.assessment_id}>
                  <td>
                    <Link className="font-bold no-underline hover:underline" to={`/reports/${r.assessment_id}`} title="Open the draft report (gold watermark)">{r.org_name}</Link>
                    <span className="ml-2 inline-flex items-center gap-1.5"><DraftBadge /><span className={cn(
                      "text-[0.66rem] uppercase tracking-wider",
                      r.review_status === "approved" ? "text-[var(--verified)]" : "text-muted-foreground",
                    )}>{statusLabel(r.review_status)}</span></span>
                  </td>
                  <td className="clickable"><Link to={`/reports/${r.assessment_id}`}>{cell(r.overall)}</Link></td>
                  {DOMAINS.map(d => <td key={d} className="dom">{cell(domVal(r, d))}</td>)}
                  <td>{r.cohort.n}{r.cohort.n > 0 && r.cohort.relaxation_label !== "exact cohort" ? <span className="font-bold text-muted-foreground" title={r.cohort.relaxation_label}>*</span> : ""}</td>
                  <td>{r.vci === null ? <span className="text-[0.74rem] italic text-muted-foreground">—</span> : <VciBadge label={vciBand(r.vci)} guidance={`Result confidence: ${r.vci}`} />}</td>
                  <td>{r.top_findings.slice(0, 3).map((f, i) => <span key={i} className="whitespace-nowrap rounded-sm border bg-muted/40 px-2 py-0.5 text-[0.68rem] text-muted-foreground" title={`${f.domain} · ${f.severity}`}>{f.code}</span>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Non-scored rows — honest per-row explanation */}
      {nonScored.length > 0 && (
        <Card className="rounded-lg border bg-card px-5.5 py-5">
          <div className="mb-2.5 text-[0.7rem] font-bold uppercase tracking-wider text-muted-foreground">Rows not scored ({nonScored.length})</div>
          {nonScored.map((r, i) => (
            <div key={i} className={cn(
              "grid items-start gap-3 border-b px-0.5 py-2.5 last:border-b-0 md:grid-cols-[1fr_3fr]",
              r.status === "failed" && "[&_.msg]:text-[var(--standing-bad)]",
            )}>
              <span className="text-[0.86rem] font-bold">{r.org_name}</span>
              <span className="msg text-[0.82rem] leading-snug text-muted-foreground">
                {r.status === "insufficient_profile" ? INSUFFICIENT_PROFILE_TEXT : (r.error || "Failed during processing.")}
              </span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
