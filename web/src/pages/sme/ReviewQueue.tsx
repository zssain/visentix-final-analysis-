/**
 * SME Workbench — the review gate.
 *
 * This is the control that makes a report client-shippable (business-logic §5),
 * so its first duty is that nothing it shows is a lie. The rewrite fixed four
 * defects that made it look like a review tool while the gate stood open:
 *
 *  1. Findings were loaded from `GET /findings/` — every organization's findings,
 *     ordered by score, capped at 200, then filtered client-side. An assessment
 *     outside that global top-200 showed ZERO findings while Approve stayed live.
 *     Now: `GET /review/{id}/findings`, scoped to the one assessment.
 *  2. The "source clause" was whichever clause happened to share the finding's
 *     domain — so an SME judged a finding against text that was not its evidence,
 *     under a heading that said "Source". Now: the real `finding_clause`
 *     citations, or explicit absence.
 *  3. "Replace all with [REDACTED]" set local state, called no endpoint, and then
 *     displayed "✓ All PII replaced". Nothing was ever saved. De-identification
 *     now lives in its own tab and drives the real, server-validated exemplar
 *     endpoints; the finding pane shows evidence read-only.
 *  4. Approve committed the freeze without asking whether findings were reviewed
 *     (F06 AC-3 unenforced). The server now refuses with 409; this surfaces it
 *     and disables the button with a reason.
 *
 * Layout follows the actual job: pick an assessment → work through its findings →
 * approve. The queue is its own column instead of being buried inside the middle
 * pane, which is what made the old screen unreadable.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { CodexTooltip } from "../../components/CodexTooltip";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { domainLabel, humanize, severityLabel, statusLabel } from "../../lib/labels";
import { cn } from "@/lib/utils";

const NR = "—"; // honest absence — never a fabricated value (DATA-003)

interface ReviewItem {
  assessment_id: string;
  status: string;
  finding_reviews: Record<string, unknown>;
  // Identity, from GET /review/queue. A UUID is not a name: an SME needs to know
  // WHOSE notice this is and what was assessed before they open it (DDR-011).
  // Any of these may be absent on a legacy row — absent renders as absent.
  organization_name?: string | null;
  organization_domain?: string | null;
  industry?: string | null;
  source_label?: string | null;
  captured_at?: string | null;
  total_findings?: number;
  decided_findings?: number;
}

interface Evidence {
  clause_id: string;
  text: string;
  domain?: string | null;
}

interface Finding {
  finding_id: string;
  finding_type_code: string;
  severity: string;
  score?: number | null;
  domain: string;
  confidence_score?: number | null;
  benchmark_deviation_score?: number | null;
  evidence: Evidence[];
  decision: "confirm" | "edit" | "dismiss" | null;
}

interface FindingsResponse {
  findings: Finding[];
  reviewed_count: number;
  total_count: number;
  all_reviewed: boolean;
}

interface ExemplarCandidate {
  id: string;
  domain: string;
  clause_text: string;
  maturity_note?: string | null;
  sme_cleaned: boolean;
}

type Mode = "findings" | "exemplars";

function fmt(v: number | null | undefined, digits = 1): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : NR;
}

/** Severity IS a standing, so it uses the one traffic-light scale (OD-13).
 *  An unrecognised severity gets no standing at all — `provisional` says "we do
 *  not know what this is", where the old `badge-draft` fallback quietly painted
 *  it the same as a reviewed draft. */
function severityVariant(severity: string): "standing-bad" | "standing-mid" | "standing-good" | "provisional" {
  switch ((severity || "").toLowerCase()) {
    case "severe":
    case "high": return "standing-bad";
    case "moderate":
    case "elevated":
    case "medium": return "standing-mid";
    case "low": return "standing-good";
    default: return "provisional";
  }
}

/** A submitted source shown at reading length: a full privacy-policy URL is
 *  mostly boilerplate, and the host plus the tail is what identifies it. */
function shortSource(src: string): string {
  try {
    const u = new URL(src);
    const tail = u.pathname.replace(/\/$/, "").split("/").filter(Boolean).pop();
    return tail ? `${u.hostname}/…/${tail}` : u.hostname;
  } catch {
    return src.length > 42 ? `${src.slice(0, 40)}…` : src;
  }
}

function shortDate(raw: string): string {
  const d = new Date(raw);
  return Number.isNaN(d.getTime())
    ? raw
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** Reading aid only — the authoritative de-id check runs server-side on submit. */
function piiHints(text: string): string[] {
  const hits: string[] = [];
  if (/[\w.+-]+@[\w-]+\.[\w.]+/.test(text)) hits.push("email");
  if (/https?:\/\/\S+|www\.\S+/.test(text)) hits.push("url");
  if (/\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/.test(text)) hits.push("phone");
  return hits;
}

export function ReviewQueue() {
  const [mode, setMode] = useState<Mode>("findings");
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [trainingStats, setTrainingStats] = useState({ confirmed: 0, edited: 0, dismissed: 0 });

  // ── Findings review ──────────────────────────────────────────────────────
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [detail, setDetail] = useState<FindingsResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [findingIdx, setFindingIdx] = useState(0);
  const [advisorLede, setAdvisorLede] = useState("");
  const [advisorBody, setAdvisorBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);

  // ── Exemplar de-identification ───────────────────────────────────────────
  const [exemplars, setExemplars] = useState<ExemplarCandidate[]>([]);
  const [exLoading, setExLoading] = useState(false);
  const [exSelected, setExSelected] = useState<ExemplarCandidate | null>(null);
  const [cleanText, setCleanText] = useState("");
  const [maturityNote, setMaturityNote] = useState("");
  const [exBusy, setExBusy] = useState(false);

  const current: Finding | null = detail?.findings[findingIdx] ?? null;

  const loadQueue = useCallback(() => {
    setQueueLoading(true);
    return api.get("/review/queue")
      .then(d => setQueue(Array.isArray(d) ? (d as ReviewItem[]) : []))
      .catch(err => { if (!(err instanceof ApiError && err.status === 401)) setQueue([]); })
      .finally(() => setQueueLoading(false));
  }, []);

  useEffect(() => {
    void loadQueue();
    void api.get("/admin/training-stats")
      .then(s => {
        const t = s as { confirmed?: number; edited?: number; dismissed?: number } | null;
        if (t) setTrainingStats({ confirmed: t.confirmed ?? 0, edited: t.edited ?? 0, dismissed: t.dismissed ?? 0 });
      })
      .catch(() => { /* counters stay at their last real value; never invented */ });
  }, [loadQueue]);

  const loadFindings = useCallback((assessmentId: string, keepIdx = false) => {
    setDetailLoading(true);
    setDetailError(null);
    return api.get(`/review/${assessmentId}/findings`)
      .then(d => {
        const data = d as FindingsResponse;
        setDetail(data);
        if (!keepIdx) {
          // Land on the first finding that still needs a decision.
          const next = data.findings.findIndex(f => !f.decision);
          setFindingIdx(next >= 0 ? next : 0);
        }
      })
      .catch(err => {
        if (err instanceof ApiError && err.status === 401) return;
        setDetail(null);
        setDetailError("Could not load this assessment's findings. Nothing was approved.");
      })
      .finally(() => setDetailLoading(false));
  }, []);

  const selectItem = useCallback((item: ReviewItem) => {
    setSelected(item);
    setBanner(null);
    setAdvisorLede("");
    setAdvisorBody("");
    void loadFindings(item.assessment_id);
  }, [loadFindings]);

  const decide = useCallback(async (action: "confirm" | "edit" | "dismiss") => {
    if (!selected || !current || saving) return;
    setSaving(true);
    setBanner(null);
    const edited_fields = (action === "edit" || advisorLede || advisorBody)
      ? { advisor_lede: advisorLede, advisor_body: advisorBody }
      : undefined;
    try {
      await api.post(
        `/review/finding/${selected.assessment_id}/${current.finding_id}`,
        { action, ...(edited_fields ? { edited_fields } : {}) },
      );
      setAdvisorLede("");
      setAdvisorBody("");
      // Re-read from the server so progress and decisions are never inferred.
      await loadFindings(selected.assessment_id, true);
      setFindingIdx(i => Math.min(i + 1, Math.max((detail?.findings.length ?? 1) - 1, 0)));
      setTrainingStats(s => ({
        confirmed: s.confirmed + (action === "confirm" ? 1 : 0),
        edited: s.edited + (action === "edit" ? 1 : 0),
        dismissed: s.dismissed + (action === "dismiss" ? 1 : 0),
      }));
    } catch (err) {
      setBanner({ kind: "err", text: `Could not save that decision: ${err instanceof ApiError ? err.message : "save failed"}` });
    } finally {
      setSaving(false);
    }
  }, [selected, current, saving, advisorLede, advisorBody, loadFindings, detail]);

  const approve = useCallback(async () => {
    if (!selected || approving) return;
    setApproving(true);
    setBanner(null);
    try {
      await api.post(`/review/${selected.assessment_id}/approve`);
      setBanner({ kind: "ok", text: `Approved — the snapshot for ${selected.assessment_id.slice(0, 8)}… is frozen.` });
      const remaining = queue.filter(i => i.assessment_id !== selected.assessment_id);
      setQueue(remaining);
      setSelected(null);
      setDetail(null);
      void loadQueue();
    } catch (err) {
      // The server is authoritative on the gate; surface its reason verbatim.
      const msg = err instanceof ApiError ? err.message : "approval failed";
      setBanner({ kind: "err", text: `Not approved — ${msg}` });
      if (selected) void loadFindings(selected.assessment_id, true);
    } finally {
      setApproving(false);
    }
  }, [selected, approving, queue, loadQueue, loadFindings]);

  // ── Exemplars ────────────────────────────────────────────────────────────
  const loadExemplars = useCallback(() => {
    setExLoading(true);
    return api.get("/review/exemplars")
      .then(d => setExemplars(Array.isArray(d) ? (d as ExemplarCandidate[]) : []))
      .catch(() => setExemplars([]))
      .finally(() => setExLoading(false));
  }, []);

  useEffect(() => { if (mode === "exemplars") void loadExemplars(); }, [mode, loadExemplars]);

  const pickExemplar = useCallback((ex: ExemplarCandidate) => {
    setExSelected(ex);
    setCleanText(ex.clause_text ?? "");
    setMaturityNote(ex.maturity_note ?? "");
    setBanner(null);
  }, []);

  const saveClean = useCallback(async () => {
    if (!exSelected || exBusy) return;
    setExBusy(true);
    setBanner(null);
    try {
      await api.post(`/review/exemplar/${exSelected.id}/clean`, {
        cleaned_text: cleanText, maturity_note: maturityNote,
      });
      setBanner({ kind: "ok", text: "Cleaned text saved — the server verified it carries no identifying tokens." });
      await loadExemplars();
    } catch (err) {
      // A rejection here is the de-id guarantee doing its job; show it plainly.
      setBanner({ kind: "err", text: err instanceof ApiError ? err.message : "Could not save cleaned text." });
    } finally {
      setExBusy(false);
    }
  }, [exSelected, exBusy, cleanText, maturityNote, loadExemplars]);

  const approveExemplar = useCallback(async () => {
    if (!exSelected || exBusy) return;
    setExBusy(true);
    setBanner(null);
    try {
      await api.post(`/review/exemplar/${exSelected.id}/approve`);
      setBanner({ kind: "ok", text: "Exemplar approved and available to the benchmark-language comparison." });
      setExSelected(null);
      await loadExemplars();
    } catch (err) {
      setBanner({ kind: "err", text: err instanceof ApiError ? err.message : "Could not approve this exemplar." });
    } finally {
      setExBusy(false);
    }
  }, [exSelected, exBusy, loadExemplars]);

  const hints = useMemo(() => piiHints(cleanText), [cleanText]);

  return (
    <div>
      <PageHeader
        eyebrow="Workbench"
        title="SME Workbench"
        description="Decide every machine finding before it reaches a client — confirm, edit or dismiss — then approve the assessment. Every decision is saved as a training label."
        actions={
          <div className="flex flex-col items-end gap-1.5">
            <Badge variant="provisional">{queueLoading ? NR : queue.length} pending</Badge>
            <div className="flex gap-3 text-[0.78rem] font-bold [&>span:nth-child(1)]:text-[var(--standing-good)] [&>span:nth-child(2)]:text-[var(--verified)] [&>span:nth-child(3)]:text-[var(--standing-bad)]">
              <span title="Confirmed">✓ {trainingStats.confirmed}</span>
              <span title="Edited">✎ {trainingStats.edited}</span>
              <span title="Dismissed">✕ {trainingStats.dismissed}</span>
            </div>
          </div>
        }
      />

      <div className="mb-4 flex gap-1 border-b [&_button]:-mb-px [&_button]:cursor-pointer [&_button]:border-b-2 [&_button]:border-transparent [&_button]:bg-transparent [&_button]:px-3.5 [&_button]:py-2.5 [&_button]:text-[0.85rem] [&_button]:font-semibold [&_button]:text-muted-foreground [&_button.active]:border-b-foreground [&_button.active]:text-foreground" role="tablist" aria-label="Workbench mode">
        <button role="tab" aria-selected={mode === "findings"} className={mode === "findings" ? "active" : ""}
          onClick={() => setMode("findings")}>Findings review</button>
        <button role="tab" aria-selected={mode === "exemplars"} className={mode === "exemplars" ? "active" : ""}
          onClick={() => setMode("exemplars")}>Exemplar de-identification</button>
      </div>

      {banner && (
        <Alert role="status" data-testid="workbench-banner"
          className="mb-3.5" variant={banner.kind === "err" ? "destructive" : "default"}>
          <AlertDescription>{banner.text}</AlertDescription>
        </Alert>
      )}

      {mode === "findings" ? (
        <div className="grid items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          {/* ── Queue ── */}
          <Card className="gap-0 overflow-hidden py-0">
            <div className="flex items-center justify-between gap-3 border-b px-6 py-4"><div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Awaiting review</div></div>
            <div className="flex max-h-[70vh] flex-col gap-1.5 overflow-y-auto p-2.5">
              {queueLoading ? (
                <p className="m-0 text-[0.82rem] text-muted-foreground">Loading queue…</p>
              ) : queue.length === 0 ? (
                <p className="m-0 text-[0.82rem] text-muted-foreground" data-testid="queue-empty">All caught up — nothing is waiting for review.</p>
              ) : queue.map(item => {
                const total = item.total_findings ?? 0;
                const decided = item.decided_findings ?? 0;
                return (
                  <button key={item.assessment_id} onClick={() => selectItem(item)}
                    data-testid={`queue-item-${item.assessment_id}`}
                    title={`Assessment ${item.assessment_id}`}
                    className={cn("flex w-full items-start justify-between gap-2 rounded-md border bg-card px-2.5 py-2.5 text-left", "hover:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50", selected?.assessment_id === item.assessment_id && "border-ring bg-[color-mix(in_oklab,var(--primary)_4%,transparent)]")}>
                    <span className="flex min-w-0 flex-col gap-0.5">
                      {/* The organization is the item's name. The id stays available
                          on hover and in the header — reachable, not leading. */}
                      <span className="text-[0.84rem] font-bold">
                        {item.organization_name || <em className="m-0 text-[0.82rem] text-muted-foreground">Organization not recorded</em>}
                      </span>
                      {item.source_label && (
                        <span className="max-w-[190px] overflow-hidden text-ellipsis whitespace-nowrap text-[0.72rem] text-muted-foreground">{shortSource(item.source_label)}</span>
                      )}
                      <span className="text-[0.7rem] text-muted-foreground">
                        {total > 0
                          ? `${decided}/${total} findings decided`
                          : "No findings recorded"}
                        {item.captured_at && <> · {shortDate(item.captured_at)}</>}
                      </span>
                    </span>
                    <Badge variant="provisional">
                      {statusLabel(item.status)}
                    </Badge>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* ── Review surface ── */}
          <Card className="px-4.5 py-4">
            {!selected ? (
              <div className="max-w-[60ch] px-1 py-6 text-[0.86rem] leading-relaxed text-muted-foreground">Choose an assessment to begin reviewing its findings.</div>
            ) : detailLoading ? (
              <div className="max-w-[60ch] px-1 py-6 text-[0.86rem] leading-relaxed text-muted-foreground">Loading findings…</div>
            ) : detailError ? (
              <Alert variant="destructive" data-testid="detail-error"><AlertDescription>{detailError}</AlertDescription></Alert>
            ) : !detail || detail.total_count === 0 ? (
              <div className="max-w-[60ch] px-1 py-6 text-[0.86rem] leading-relaxed text-muted-foreground" data-testid="no-findings">
                No findings are recorded for this assessment. Nothing can be approved until the
                pipeline has produced findings — this is not the same as "everything passed".
              </div>
            ) : current ? (
              <>
                <div className="mb-3.5 flex flex-wrap items-baseline gap-1.5 border-b pb-3 text-[0.84rem] text-muted-foreground [&_strong]:text-[0.95rem] [&_strong]:text-foreground [&_code]:ml-auto [&_code]:rounded-sm [&_code]:bg-muted/60 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-data [&_code]:text-[0.68rem] [&_code]:text-muted-foreground">
                  <strong>{selected.organization_name || "Organization not recorded"}</strong>
                  {selected.source_label && <span> · {shortSource(selected.source_label)}</span>}
                  {selected.industry && <span> · {humanize(selected.industry)}</span>}
                  <code title="Assessment id">{selected.assessment_id}</code>
                </div>
                <div className="mb-3.5 flex flex-wrap items-center gap-2">
                  <CodexTooltip code={current.finding_type_code} />
                  <Badge variant={severityVariant(current.severity)} data-testid="finding-severity">
                    {current.severity ? severityLabel(current.severity) : NR}
                  </Badge>
                  {current.decision && (
                    <Badge variant="verified" data-testid="finding-decision">
                      {current.decision}ed
                    </Badge>
                  )}
                  <span className="ml-auto text-[0.74rem] text-muted-foreground">Finding {findingIdx + 1} of {detail.total_count}</span>
                </div>

                {/* Cited evidence — the real finding_clause links, or absence. */}
                <div className="mb-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Cited clause{current.evidence.length > 1 ? "s" : ""}</div>
                  {current.evidence.length === 0 ? (
                    <p className="m-0 text-[0.82rem] text-muted-foreground" data-testid="no-evidence">
                      No clause is linked to this finding. Judge it on the finding definition alone,
                      or dismiss it — no substitute text is shown.
                    </p>
                  ) : current.evidence.map(ev => (
                    <blockquote key={ev.clause_id} className="mb-2 rounded-r-md border-l-[3px] border-l-primary bg-muted/40 px-3.5 py-3 [&_p]:m-0 [&_p]:mb-1.5 [&_p]:text-[0.88rem] [&_p]:leading-relaxed [&_cite]:not-italic" data-testid="cited-clause">
                      <p>{ev.text || <span className="m-0 text-[0.82rem] text-muted-foreground">Clause text not recorded.</span>}</p>
                      <cite className="code-chip">{ev.clause_id}</cite>
                    </blockquote>
                  ))}
                </div>

                <div className="mb-4 grid gap-2.5 [grid-template-columns:repeat(auto-fit,minmax(130px,1fr))] [&>div]:flex [&>div]:flex-col [&>div]:gap-0.5 [&>div]:rounded-md [&>div]:border [&>div]:px-3 [&>div]:py-2.5 [&_span]:text-[0.65rem] [&_span]:font-bold [&_span]:uppercase [&_span]:tracking-wider [&_span]:text-muted-foreground [&_strong]:font-data [&_strong]:text-base [&_strong]:tabular-nums">
                  <div><span>Score</span><strong>{fmt(current.score)}</strong></div>
                  <div><span>Confidence</span><strong>{fmt(current.confidence_score, 2)}</strong></div>
                  <div><span>Benchmark deviation</span><strong>{fmt(current.benchmark_deviation_score)}</strong></div>
                  <div><span>Domain</span><strong>{current.domain ? domainLabel(current.domain) : NR}</strong></div>
                </div>

                <div className="mb-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Advisor note (optional)</div>
                  <input className="mb-2 w-full resize-y rounded-md border bg-transparent px-2.5 py-2 text-[0.85rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" placeholder="Lede — one sentence"
                    value={advisorLede} onChange={e => setAdvisorLede(e.target.value)} />
                  <textarea className="mb-2 w-full resize-y rounded-md border bg-transparent px-2.5 py-2 text-[0.85rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" rows={3} placeholder="Body"
                    value={advisorBody} onChange={e => setAdvisorBody(e.target.value)} />
                </div>

                <div className="mb-4.5 flex flex-wrap items-center gap-2">
                  <Button size="sm" disabled={saving} onClick={() => decide("confirm")}>Confirm</Button>
                  <Button variant="outline" size="sm" disabled={saving} onClick={() => decide("edit")}>Save edit</Button>
                  <Button variant="destructive" size="sm" disabled={saving} onClick={() => decide("dismiss")}>Dismiss</Button>
                  <span className="ml-auto flex gap-1.5">
                    <Button variant="outline" size="sm" disabled={findingIdx === 0} onClick={() => setFindingIdx(i => Math.max(0, i - 1))}>← Prev</Button>
                    <Button variant="outline" size="sm" disabled={findingIdx>= detail.total_count - 1}
                      onClick={() => setFindingIdx(i => Math.min(detail.total_count - 1, i + 1))}>Next →</Button>
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-3.5 border-t pt-3.5">
                  <div className="flex items-center gap-2.5 text-[0.78rem] text-muted-foreground">
                    <div className="h-1.5 w-[130px] overflow-hidden rounded-sm bg-border [&>div]:h-full [&>div]:rounded-sm [&>div]:bg-[var(--standing-good)] [&>div]:transition-[width] [&>div]:duration-300 motion-reduce:[&>div]:transition-none">
                      <div style={{ width: `${(detail.reviewed_count / Math.max(detail.total_count, 1)) * 100}%` }} />
                    </div>
                    <span>{detail.reviewed_count} of {detail.total_count} decided</span>
                  </div>
                  <Button data-testid="approve-btn" disabled={approving || !detail.all_reviewed} onClick={approve}>
                    {approving ? "Approving…" : "Approve assessment"}
                  </Button>
                  {!detail.all_reviewed && (
                    <span className="m-0 text-[0.82rem] text-muted-foreground" data-testid="approve-blocked">
                      Every finding needs a decision first — the server refuses approval otherwise.
                    </span>
                  )}
                </div>
              </>
            ) : null}
          </Card>
        </div>
      ) : (
        /* ── Exemplar de-identification — real, server-validated ── */
        <div className="grid items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <Card className="gap-0 overflow-hidden py-0">
            <div className="flex items-center justify-between gap-3 border-b px-6 py-4"><div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Candidates</div></div>
            <div className="flex max-h-[70vh] flex-col gap-1.5 overflow-y-auto p-2.5">
              {exLoading ? <p className="m-0 text-[0.82rem] text-muted-foreground">Loading candidates…</p>
                : exemplars.length === 0 ? <p className="m-0 text-[0.82rem] text-muted-foreground" data-testid="exemplars-empty">No exemplar candidates are awaiting de-identification.</p>
                : exemplars.map(ex => (
                  <button key={ex.id} onClick={() => pickExemplar(ex)}
                    className={cn("flex w-full items-start justify-between gap-2 rounded-md border bg-card px-2.5 py-2.5 text-left", "hover:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50", exSelected?.id === ex.id && "border-ring bg-[color-mix(in_oklab,var(--primary)_4%,transparent)]")}
                    data-testid={`exemplar-${ex.id}`}>
                    <span className="font-data text-[0.76rem] font-semibold">{ex.domain ? domainLabel(ex.domain) : NR}</span>
                    <Badge variant="provisional">{ex.id.slice(0, 6)}…</Badge>
                  </button>
                ))}
            </div>
          </Card>

          <Card className="px-4.5 py-4">
            {!exSelected ? (
              <div className="max-w-[60ch] px-1 py-6 text-[0.86rem] leading-relaxed text-muted-foreground">
                Choose a candidate to de-identify. The server re-validates every submission and
                refuses text that still carries identifying tokens — the check below is only a
                reading aid.
              </div>
            ) : (
              <>
                <div className="mb-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Cleaned clause text</div>
                  <textarea className="mb-2 w-full resize-y rounded-md border bg-transparent px-2.5 py-2 text-[0.85rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" rows={8} value={cleanText}
                    onChange={e => setCleanText(e.target.value)} data-testid="exemplar-text" />
                  {hints.length > 0 && (
                    <p className="mt-0.5 text-[0.76rem] text-[var(--standing-mid)]" data-testid="pii-hint">
                      Possible identifiers spotted while typing: {hints.join(", ")}. The server makes
                      the binding decision on save.
                    </p>
                  )}
                </div>
                <div className="mb-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Maturity note</div>
                  <input className="mb-2 w-full resize-y rounded-md border bg-transparent px-2.5 py-2 text-[0.85rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={maturityNote}
                    onChange={e => setMaturityNote(e.target.value)} />
                </div>
                <div className="mb-4.5 flex flex-wrap items-center gap-2">
                  <Button variant="outline" size="sm" disabled={exBusy} onClick={saveClean} data-testid="exemplar-clean">Check &amp; save cleaned text</Button>
                  <Button size="sm" disabled={exBusy} onClick={approveExemplar} data-testid="exemplar-approve">Approve exemplar</Button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
