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
import "./workbench.css";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

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

function severityBadgeClass(severity: string): string {
  switch ((severity || "").toLowerCase()) {
    case "severe":
    case "high": return "badge-high";
    case "moderate": return "badge-moderate";
    case "low": return "badge-low";
    default: return "badge-draft";
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
          <div className="wb-header-stats">
            <Badge variant="provisional">{queueLoading ? NR : queue.length} pending</Badge>
            <div className="wb-counters">
              <span title="Confirmed">✓ {trainingStats.confirmed}</span>
              <span title="Edited">✎ {trainingStats.edited}</span>
              <span title="Dismissed">✕ {trainingStats.dismissed}</span>
            </div>
          </div>
        }
      />

      <div className="wb-tabs" role="tablist" aria-label="Workbench mode">
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
        <div className="wb-grid">
          {/* ── Queue ── */}
          <Card className="wb-queue">
            <div className="flex items-center justify-between gap-3 border-b px-6 py-4"><div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Awaiting review</div></div>
            <div className="wb-queue-body">
              {queueLoading ? (
                <p className="wb-muted">Loading queue…</p>
              ) : queue.length === 0 ? (
                <p className="wb-muted" data-testid="queue-empty">All caught up — nothing is waiting for review.</p>
              ) : queue.map(item => {
                const total = item.total_findings ?? 0;
                const decided = item.decided_findings ?? 0;
                return (
                  <button key={item.assessment_id} onClick={() => selectItem(item)}
                    data-testid={`queue-item-${item.assessment_id}`}
                    title={`Assessment ${item.assessment_id}`}
                    className={`wb-queue-item ${selected?.assessment_id === item.assessment_id ? "sel" : ""}`}>
                    <span className="wb-qi-main">
                      {/* The organization is the item's name. The id stays available
                          on hover and in the header — reachable, not leading. */}
                      <span className="wb-qi-name">
                        {item.organization_name || <em className="wb-muted">Organization not recorded</em>}
                      </span>
                      {item.source_label && (
                        <span className="wb-qi-src">{shortSource(item.source_label)}</span>
                      )}
                      <span className="wb-qi-meta">
                        {total > 0
                          ? `${decided}/${total} findings decided`
                          : "No findings recorded"}
                        {item.captured_at && <> · {shortDate(item.captured_at)}</>}
                      </span>
                    </span>
                    <span className={`badge ${item.status === "in_review" ? "badge-gold" : "badge-draft"}`}>
                      {item.status.replace(/_/g, " ")}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* ── Review surface ── */}
          <Card className="wb-review">
            {!selected ? (
              <div className="wb-empty">Choose an assessment to begin reviewing its findings.</div>
            ) : detailLoading ? (
              <div className="wb-empty">Loading findings…</div>
            ) : detailError ? (
              <Alert variant="destructive" data-testid="detail-error"><AlertDescription>{detailError}</AlertDescription></Alert>
            ) : !detail || detail.total_count === 0 ? (
              <div className="wb-empty" data-testid="no-findings">
                No findings are recorded for this assessment. Nothing can be approved until the
                pipeline has produced findings — this is not the same as "everything passed".
              </div>
            ) : current ? (
              <>
                <div className="wb-subject">
                  <strong>{selected.organization_name || "Organization not recorded"}</strong>
                  {selected.source_label && <span> · {shortSource(selected.source_label)}</span>}
                  {selected.industry && <span> · {selected.industry.replace(/_/g, " ")}</span>}
                  <code title="Assessment id">{selected.assessment_id}</code>
                </div>
                <div className="wb-finding-head">
                  <CodexTooltip code={current.finding_type_code} />
                  <span className={`badge ${severityBadgeClass(current.severity)}`} data-testid="finding-severity">
                    {current.severity || NR}
                  </span>
                  {current.decision && (
                    <Badge variant="verified" data-testid="finding-decision">
                      {current.decision}ed
                    </Badge>
                  )}
                  <span className="wb-count">Finding {findingIdx + 1} of {detail.total_count}</span>
                </div>

                {/* Cited evidence — the real finding_clause links, or absence. */}
                <div className="wb-block">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Cited clause{current.evidence.length > 1 ? "s" : ""}</div>
                  {current.evidence.length === 0 ? (
                    <p className="wb-muted" data-testid="no-evidence">
                      No clause is linked to this finding. Judge it on the finding definition alone,
                      or dismiss it — no substitute text is shown.
                    </p>
                  ) : current.evidence.map(ev => (
                    <blockquote key={ev.clause_id} className="wb-clause" data-testid="cited-clause">
                      <p>{ev.text || <span className="wb-muted">Clause text not recorded.</span>}</p>
                      <cite className="code-chip">{ev.clause_id}</cite>
                    </blockquote>
                  ))}
                </div>

                <div className="wb-metrics">
                  <div><span>Score</span><strong>{fmt(current.score)}</strong></div>
                  <div><span>Confidence</span><strong>{fmt(current.confidence_score, 2)}</strong></div>
                  <div><span>Benchmark deviation</span><strong>{fmt(current.benchmark_deviation_score)}</strong></div>
                  <div><span>Domain</span><strong>{current.domain?.replace(/_/g, " ") || NR}</strong></div>
                </div>

                <div className="wb-block">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Advisor note (optional)</div>
                  <input className="wb-input" placeholder="Lede — one sentence"
                    value={advisorLede} onChange={e => setAdvisorLede(e.target.value)} />
                  <textarea className="wb-input" rows={3} placeholder="Body"
                    value={advisorBody} onChange={e => setAdvisorBody(e.target.value)} />
                </div>

                <div className="wb-actions">
                  <Button size="sm" disabled={saving} onClick={() => decide("confirm")}>Confirm</Button>
                  <Button variant="outline" size="sm" disabled={saving} onClick={() => decide("edit")}>Save edit</Button>
                  <Button variant="destructive" size="sm" disabled={saving} onClick={() => decide("dismiss")}>Dismiss</Button>
                  <span className="wb-nav">
                    <Button variant="outline" size="sm" disabled={findingIdx === 0} onClick={() => setFindingIdx(i => Math.max(0, i - 1))}>← Prev</Button>
                    <Button variant="outline" size="sm" disabled={findingIdx>= detail.total_count - 1}
                      onClick={() => setFindingIdx(i => Math.min(detail.total_count - 1, i + 1))}>Next →</Button>
                  </span>
                </div>

                <div className="wb-approve">
                  <div className="wb-progress">
                    <div className="wb-progress-bar">
                      <div style={{ width: `${(detail.reviewed_count / Math.max(detail.total_count, 1)) * 100}%` }} />
                    </div>
                    <span>{detail.reviewed_count} of {detail.total_count} decided</span>
                  </div>
                  <Button data-testid="approve-btn" disabled={approving || !detail.all_reviewed} onClick={approve}>
                    {approving ? "Approving…" : "Approve assessment"}
                  </Button>
                  {!detail.all_reviewed && (
                    <span className="wb-muted" data-testid="approve-blocked">
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
        <div className="wb-grid">
          <Card className="wb-queue">
            <div className="flex items-center justify-between gap-3 border-b px-6 py-4"><div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Candidates</div></div>
            <div className="wb-queue-body">
              {exLoading ? <p className="wb-muted">Loading candidates…</p>
                : exemplars.length === 0 ? <p className="wb-muted" data-testid="exemplars-empty">No exemplar candidates are awaiting de-identification.</p>
                : exemplars.map(ex => (
                  <button key={ex.id} onClick={() => pickExemplar(ex)}
                    className={`wb-queue-item ${exSelected?.id === ex.id ? "sel" : ""}`}
                    data-testid={`exemplar-${ex.id}`}>
                    <span className="wb-qid">{ex.domain?.replace(/_/g, " ") || NR}</span>
                    <Badge variant="provisional">{ex.id.slice(0, 6)}…</Badge>
                  </button>
                ))}
            </div>
          </Card>

          <Card className="wb-review">
            {!exSelected ? (
              <div className="wb-empty">
                Choose a candidate to de-identify. The server re-validates every submission and
                refuses text that still carries identifying tokens — the check below is only a
                reading aid.
              </div>
            ) : (
              <>
                <div className="wb-block">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Cleaned clause text</div>
                  <textarea className="wb-input" rows={8} value={cleanText}
                    onChange={e => setCleanText(e.target.value)} data-testid="exemplar-text" />
                  {hints.length > 0 && (
                    <p className="wb-hint" data-testid="pii-hint">
                      Possible identifiers spotted while typing: {hints.join(", ")}. The server makes
                      the binding decision on save.
                    </p>
                  )}
                </div>
                <div className="wb-block">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Maturity note</div>
                  <input className="wb-input" value={maturityNote}
                    onChange={e => setMaturityNote(e.target.value)} />
                </div>
                <div className="wb-actions">
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
