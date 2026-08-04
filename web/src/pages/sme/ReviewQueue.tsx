/**
 * SME Workbench v2 — three-pane layout
 *
 * Left:   Source clause + de-id checker (PII detected → category label → Redact)
 * Center: Auto-finding + Analyst metric grid + Confirm / Edit / Dismiss
 * Right:  Advisor Note editor + Codex reference
 *
 * All data is loaded from the real backend:
 *   GET  /review/queue                          → pending review items
 *   GET  /findings/                             → findings (filtered by notice_id === assessment_id)
 *   GET  /assessments/{aid}/clauses             → source clause text (matched by finding domain)
 *   GET  /findings/codex                        → finding-type titles
 *   POST /review/finding/{aid}/{fid}            → per-finding confirm/edit/dismiss
 *   POST /review/{aid}/approve                  → finalize review, freeze snapshot
 *
 * Exposure / VCI / Percentile are NOT recorded per-finding by any API, so they
 * render honest absence ("—" / "not recorded") — never a fabricated number.
 *
 * Training label counts loaded from /admin/training-stats API.
 */
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { CodexTooltip }   from "../../components/CodexTooltip";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { PageHeader } from "../../components/PageHeader";
import "../../components/furniture.css";

interface ReviewItem {
  assessment_id: string;
  status: string;
  finding_reviews: Record<string, unknown>;
  approved_by: string;
  approved_at?: string;
}

// Shape returned by GET /findings/ (see app/routers/findings.py list_findings)
interface Finding {
  finding_id: string;
  finding_type_code: string;
  severity: string;
  score: number | null;
  domain: string;
  confidence_score: number | null;
  notice_id: string;
}

// Shape returned by GET /assessments/{id}/clauses (see app/routers/assessments.py list_clauses)
interface Clause {
  clause_id: string;
  raw_text: string;
  domain: string;
}

// Honest-absence marker for any metric the API does not record.
const NR = "—";

interface PiiToken { token: string; category: "name" | "email" | "url" | "custom"; start: number; end: number; }

function detectPii(text: string): PiiToken[] {
  const tokens: PiiToken[] = [];
  // Email
  const emailRe = /[\w.+-]+@[\w.-]+\.\w+/g;
  let m;
  while ((m = emailRe.exec(text)) !== null)
    tokens.push({ token: m[0], category: "email", start: m.index, end: m.index + m[0].length });
  // URL
  const urlRe = /https?:\/\/[\w./-]+/g;
  while ((m = urlRe.exec(text)) !== null)
    tokens.push({ token: m[0], category: "url", start: m.index, end: m.index + m[0].length });
  // Simple name heuristic (two capitalised words)
  const nameRe = /[A-Z][a-z]+ [A-Z][a-z]+/g;
  while ((m = nameRe.exec(text)) !== null) {
    if (!tokens.some(t => t.start === m!.index))
      tokens.push({ token: m[0], category: "name", start: m.index, end: m.index + m[0].length });
  }
  return tokens.sort((a, b) => a.start - b.start);
}

function ClauseDisplay({ text, redacted }: { text: string; redacted: boolean }) {
  const tokens = detectPii(text);
  if (tokens.length === 0 || redacted) {
    const displayText = redacted
      ? tokens.reduce((t, tok) => t.replace(tok.token, "[REDACTED]"), text)
      : text;
    return <span>{displayText}</span>;
  }

  const parts: React.ReactNode[] = [];
  let pos = 0;
  tokens.forEach((tok, i) => {
    if (tok.start > pos) parts.push(<span key={`text-${i}`}>{text.slice(pos, tok.start)}</span>);
    parts.push(
      <span key={`tok-${i}`} title={`${tok.category} detected`}>
        <span style={{
          borderBottom: "2px solid var(--red)", color: "var(--red)",
          fontWeight: 600, position: "relative", cursor: "help",
        }}>
          🔒 {tok.token}
        </span>
        <span style={{
          display: "inline-block", fontSize: "0.62rem", fontWeight: 700,
          textTransform: "uppercase", letterSpacing: "0.07em",
          background: "rgba(248,113,113,0.12)", color: "#b91c1c",
          border: "1px solid rgba(248,113,113,0.3)",
          padding: "0 5px", borderRadius: 3, marginLeft: 3,
          verticalAlign: "middle",
        }}>[{tok.category}]</span>
      </span>
    );
    pos = tok.end;
  });
  if (pos < text.length) parts.push(<span key="tail">{text.slice(pos)}</span>);
  return <>{parts}</>;
}

function severityBadgeClass(severity: string): string {
  const s = (severity || "").toLowerCase();
  if (s === "high") return "badge-high";
  if (s === "medium") return "badge-gold";
  if (s === "low") return "badge-draft";
  return "badge-draft";
}

function fmtScore(v: number | null | undefined): string {
  return v === null || v === undefined || Number.isNaN(v) ? NR : String(v);
}

function fmtConfidence(v: number | null | undefined): string {
  return v === null || v === undefined || Number.isNaN(v) ? NR : `${v}%`;
}

export function ReviewQueue() {
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ReviewItem | null>(null);

  // Findings for the selected assessment
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingIdx, setFindingIdx] = useState(0);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [redacted, setRedacted] = useState(false);
  const [advisorLede, setAdvisorLede] = useState("");
  const [advisorBody, setAdvisorBody] = useState("");
  const [action, setAction] = useState<"confirm" | "edit" | "dismiss" | null>(null);
  const [savingFinding, setSavingFinding] = useState(false);
  const [approving, setApproving] = useState(false);
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [trainingStats, setTrainingStats] = useState({ confirmed: 0, edited: 0, dismissed: 0 });

  const currentFinding: Finding | null = findings[findingIdx] ?? null;

  // Best-effort clause text for the current finding: first substantive clause in
  // the finding's domain. If none, honest absence — never invented clause text.
  const clauseForFinding = currentFinding
    ? clauses.find(c => c.domain === currentFinding.domain) ?? null
    : null;
  const clauseText = clauseForFinding?.raw_text ?? "";
  const piiTokens  = clauseText ? detectPii(clauseText) : [];
  const hasPii     = piiTokens.length > 0 && !redacted;

  const loadQueue = useCallback(() => {
    setLoading(true);
    return api.get("/review/queue")
      .then((data) => setQueue(Array.isArray(data) ? (data as ReviewItem[]) : []))
      .catch((err) => { if (err instanceof ApiError && err.status === 401) return; setQueue([]); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadQueue();
    // Load real training stats
    api.get("/admin/training-stats")
      .then((data) => { if (data && typeof data === "object") setTrainingStats(data as typeof trainingStats); })
      .catch(() => {});
  }, [loadQueue]);

  // Reset the per-finding editing state (local only).
  const resetDecision = useCallback(() => {
    setAction(null);
    setAdvisorLede("");
    setAdvisorBody("");
    setRedacted(false);
  }, []);

  // Load a selected assessment's real findings + clauses.
  const selectItem = useCallback((item: ReviewItem) => {
    setSelected(item);
    setFindingIdx(0);
    setFindings([]);
    setClauses([]);
    setDetailError(null);
    setBanner(null);
    resetDecision();
    setDetailLoading(true);
    Promise.all([
      api.get("/findings/").catch(() => [] as unknown),
      api.get(`/assessments/${item.assessment_id}/clauses`).catch(() => ({ clauses: [] })),
    ])
      .then(([allFindings, clauseResp]) => {
        const list = Array.isArray(allFindings) ? (allFindings as Finding[]) : [];
        setFindings(list.filter(f => f.notice_id === item.assessment_id));
        const cl = (clauseResp as { clauses?: Clause[] } | null)?.clauses ?? [];
        setClauses(Array.isArray(cl) ? cl : []);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) return;
        setDetailError("Could not load findings for this assessment. Try again.");
      })
      .finally(() => setDetailLoading(false));
  }, [resetDecision]);

  // Persist a per-finding decision, then advance to the next finding.
  const submitFinding = useCallback(async () => {
    if (!selected || !currentFinding || !action || savingFinding) return;
    setSavingFinding(true);
    setBanner(null);
    const edited_fields =
      action === "edit"
        ? { advisor_lede: advisorLede, advisor_body: advisorBody }
        : (advisorLede || advisorBody)
          ? { advisor_lede: advisorLede, advisor_body: advisorBody }
          : undefined;
    try {
      await api.post(
        `/review/finding/${selected.assessment_id}/${currentFinding.finding_id}`,
        { action, ...(edited_fields ? { edited_fields } : {}) },
      );
      setBanner({ kind: "ok", text: `${action.toUpperCase()} saved for ${currentFinding.finding_id}` });
      resetDecision();
      // Advance to the next undecided finding (or stay on the last one).
      setFindingIdx(i => Math.min(i + 1, Math.max(findings.length - 1, 0)));
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Save failed";
      setBanner({ kind: "err", text: `Could not save finding decision: ${msg}` });
    } finally {
      setSavingFinding(false);
    }
  }, [selected, currentFinding, action, savingFinding, advisorLede, advisorBody, findings.length, resetDecision]);

  // Finalize the review: approve the assessment, refresh the queue, advance.
  const submitReview = useCallback(async () => {
    if (!selected || approving) return;
    setApproving(true);
    setBanner(null);
    try {
      await api.post(`/review/${selected.assessment_id}/approve`);
      setBanner({ kind: "ok", text: `Assessment ${selected.assessment_id} approved` });
      const approvedId = selected.assessment_id;
      // Refresh the queue and move to the next item.
      const data = await api.get("/review/queue").catch(() => [] as unknown);
      const next = (Array.isArray(data) ? (data as ReviewItem[]) : []).filter(
        i => i.assessment_id !== approvedId,
      );
      setQueue(next);
      if (next.length > 0) {
        selectItem(next[0]);
      } else {
        setSelected(null);
        setFindings([]);
        setClauses([]);
        resetDecision();
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Approve failed";
      setBanner({ kind: "err", text: `Could not approve assessment: ${msg}` });
    } finally {
      setApproving(false);
    }
  }, [selected, approving, selectItem, resetDecision]);

  return (
    <div>
      <PageHeader
        eyebrow="Workbench"
        title="SME Workbench"
        description="Review each machine finding before it reaches the client: confirm it, edit its language, or dismiss it — and author the Advisor Note. Every decision is saved as a training label."
        actions={
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <span className="badge badge-gold">
              {loading ? NR : queue.length} pending in queue
            </span>
            <div style={{ display: "flex", gap: 12, fontSize: "0.78rem", color: "var(--text-muted)", flexWrap: "wrap" }}>
              <span style={{ color: "var(--teal)", fontWeight: 700 }}>✓ {trainingStats.confirmed}</span>
              <span style={{ color: "var(--exec-blue)", fontWeight: 700 }}>✎ {trainingStats.edited}</span>
              <span style={{ color: "var(--red)", fontWeight: 700 }}>✕ {trainingStats.dismissed}</span>
            </div>
          </div>
        }
      />

      {banner && (
        <div
          role="status"
          className={`notice-box ${banner.kind === "err" ? "red" : "teal"}`}
          style={{ marginBottom: 12 }}
          data-testid="workbench-banner"
        >
          {banner.text}
        </div>
      )}

      {/* Three-pane workbench */}
      <div className="workbench-grid" style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
        gap: 16, alignItems: "start",
      }}>

        {/* ── LEFT: Source clause ── */}
        <div className="card" style={{ overflow: "visible" }}>
          <div className="card-head">
            <div className="section-label">Source Clause</div>
            <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              {currentFinding ? (
                <>
                  <span className="code-chip" style={{ fontSize: "0.7rem" }} data-testid="clause-code">
                    {clauseForFinding?.clause_id ?? NR}
                  </span>
                  <span className="domain-eyebrow">{currentFinding.domain.replace(/_/g, " ")}</span>
                </>
              ) : (
                <span className="domain-eyebrow">no finding selected</span>
              )}
            </div>
          </div>

          <div style={{ padding: "14px 16px", fontSize: "0.88rem", lineHeight: 1.7, color: "var(--text)", minHeight: 120 }}>
            {!selected ? (
              <span style={{ color: "var(--text-muted)" }}>
                Select an item from the review queue to view its source clause text and run the PII de-identification checker.
              </span>
            ) : detailLoading ? (
              <span style={{ color: "var(--text-muted)" }}>Loading source clause…</span>
            ) : clauseText ? (
              <ClauseDisplay text={clauseText} redacted={redacted} />
            ) : (
              <span style={{ color: "var(--text-muted)" }} data-testid="clause-absent">
                Source clause text not recorded for this finding's domain.
              </span>
            )}
          </div>

          {hasPii && (
            <div style={{
              margin: "0 16px 14px",
              padding: "10px 14px",
              background: "rgba(248,113,113,0.06)",
              border: "1px solid rgba(248,113,113,0.25)",
              borderRadius: "var(--radius)",
            }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#b91c1c", marginBottom: 4 }}>
                🔒 PII detected — {piiTokens.length} token{piiTokens.length > 1 ? "s" : ""} flagged
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                {piiTokens.map((tok, i) => (
                  <span key={i} style={{
                    fontSize: "0.7rem", fontWeight: 700,
                    background: "rgba(248,113,113,0.12)", color: "#b91c1c",
                    border: "1px solid rgba(248,113,113,0.3)",
                    padding: "2px 8px", borderRadius: 4,
                  }}>[{tok.category}]</span>
                ))}
              </div>
              <button
                className="btn btn-danger btn-sm"
                onClick={() => setRedacted(true)}
                id="redact-all-btn"
              >
                Replace all with [REDACTED]
              </button>
            </div>
          )}

          {redacted && (
            <div className="notice-box teal" style={{ margin: "0 16px 14px" }}>
              ✓ All PII replaced with [REDACTED]
            </div>
          )}

          {clauseForFinding && (
            <div style={{ padding: "10px 16px", borderTop: "1px solid var(--border)" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Source: <span style={{ fontFamily: "var(--font-data)", fontWeight: 600 }}>
                  {currentFinding?.domain.replace(/_/g, " ")} &gt; {clauseForFinding.clause_id}
                </span>
              </span>
            </div>
          )}
        </div>

        {/* ── CENTER: Auto-finding ── */}
        <div className="card" style={{ overflow: "visible" }}>
          <div className="card-head">
            <div className="section-label">Auto Finding</div>
          </div>
          <div style={{ padding: "14px 16px" }}>
            {/* Queue list */}
            <div style={{ marginBottom: 14 }}>
              <div className="section-label" style={{ marginBottom: 6 }}>Review Queue</div>
              {loading ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Loading queue…</div>
              ) : queue.length === 0 ? (
                <div
                  style={{ padding: "16px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "0.82rem" }}
                  data-testid="queue-empty"
                >
                  All caught up — no assessments pending review
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {queue.map(item => (
                    <button
                      key={item.assessment_id}
                      onClick={() => selectItem(item)}
                      data-testid={`queue-item-${item.assessment_id}`}
                      style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "8px 10px", borderRadius: "var(--radius)",
                        border: `1px solid ${selected?.assessment_id === item.assessment_id ? "var(--navy)" : "var(--border)"}`,
                        background: selected?.assessment_id === item.assessment_id ? "rgba(9,35,79,0.04)" : "white",
                        cursor: "pointer", textAlign: "left",
                      }}
                    >
                      <span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--navy)" }}>
                        {item.assessment_id}
                      </span>
                      <span className={`badge ${item.status === "in_review" ? "badge-gold" : "badge-draft"}`} style={{ fontSize: "0.65rem" }}>
                        {item.status.replace(/_/g, " ")}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected finding detail */}
            {!selected ? (
              <div style={{ color: "var(--text-muted)", fontSize: "0.82rem", padding: "12px 0" }}>
                Select a queue item to review its findings.
              </div>
            ) : detailLoading ? (
              <div style={{ color: "var(--text-muted)", fontSize: "0.82rem", padding: "12px 0" }}>Loading findings…</div>
            ) : detailError ? (
              <div className="notice-box red" data-testid="detail-error">{detailError}</div>
            ) : findings.length === 0 ? (
              <div
                style={{ color: "var(--text-muted)", fontSize: "0.82rem", padding: "12px 0" }}
                data-testid="no-findings"
              >
                No machine findings recorded for this assessment.
              </div>
            ) : currentFinding ? (
              <>
                {/* Finding header */}
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                  <CodexTooltip code={currentFinding.finding_type_code} />
                  <span className={`badge ${severityBadgeClass(currentFinding.severity)}`} data-testid="finding-severity">
                    {currentFinding.severity || NR}
                  </span>
                  <span style={{ marginLeft: "auto", fontSize: "0.72rem", color: "var(--text-muted)" }}>
                    Finding {findingIdx + 1} of {findings.length}
                  </span>
                </div>
                <div
                  style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--navy)", marginBottom: 12, fontFamily: "var(--font-data)" }}
                  data-testid="finding-id"
                >
                  {currentFinding.finding_id}
                </div>

                {/* Mini metric grid — honest absence where the API does not record a metric */}
                <div style={{
                  display: "grid", gridTemplateColumns: "1fr 1fr",
                  gap: 1, background: "var(--border)",
                  border: "1px solid var(--border)", borderRadius: "var(--radius)", marginBottom: 16,
                }}>
                  {[
                    { label: "Score", value: fmtScore(currentFinding.score) },
                    { label: "Confidence", value: fmtConfidence(currentFinding.confidence_score) },
                    { label: "Exposure", value: NR },      // not recorded per-finding by the API
                    { label: "Percentile", value: NR },    // not recorded per-finding by the API
                  ].map(mtc => (
                    <div key={mtc.label} style={{ background: "white", padding: "10px 12px" }}>
                      <div className="micro-label" style={{ marginBottom: 2 }}>{mtc.label}</div>
                      <div style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums", fontSize: "1.1rem", fontWeight: 700, color: "var(--navy)" }}>{mtc.value}</div>
                    </div>
                  ))}
                </div>

                {/* Confirm / Edit / Dismiss */}
                <div className="section-label" style={{ marginBottom: 8 }}>Finding Actions</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    className={`btn btn-sm ${action === "confirm" ? "btn-teal" : "btn-outline"}`}
                    onClick={() => setAction("confirm")}
                    disabled={hasPii || savingFinding}
                    title={hasPii ? "Resolve PII before confirming" : undefined}
                    id="finding-confirm-btn"
                  >
                    ✓ Confirm
                  </button>
                  <button
                    className={`btn btn-sm ${action === "edit" ? "btn-primary" : "btn-outline"}`}
                    onClick={() => setAction("edit")}
                    disabled={savingFinding}
                    id="finding-edit-btn"
                  >
                    ✎ Edit
                  </button>
                  <button
                    className={`btn btn-sm ${action === "dismiss" ? "btn-danger" : "btn-outline"}`}
                    onClick={() => setAction("dismiss")}
                    disabled={savingFinding}
                    id="finding-dismiss-btn"
                  >
                    ✕ Dismiss
                  </button>
                </div>
                {hasPii && (
                  <p style={{ fontSize: "0.72rem", color: "var(--red)", marginTop: 6, fontWeight: 600 }}>
                    🔒 Resolve PII in source clause before confirming
                  </p>
                )}
                {action && (
                  <div className={`notice-box ${action === "dismiss" ? "red" : "teal"}`} style={{ marginTop: 10 }}>
                    Action: <strong>{action.toUpperCase()}</strong> — label saved when you record the decision
                  </div>
                )}
                <div style={{ marginTop: 10 }}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={submitFinding}
                    disabled={!action || savingFinding || hasPii}
                    id="finding-record-btn"
                  >
                    {savingFinding ? "Saving…" : "Record Decision"}
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>

        {/* ── RIGHT: Advisor Note editor ── */}
        <div className="card" style={{ overflow: "visible" }}>
          <div className="card-head">
            <div className="section-label">Advisor Note Editor</div>
          </div>
          <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label className="micro-label" style={{ display: "block", marginBottom: 5 }}>
                Italic lede (Fraunces)
              </label>
              <textarea
                rows={3}
                value={advisorLede}
                onChange={e => setAdvisorLede(e.target.value)}
                placeholder="Write the opening italic sentence in exposure/maturity language…"
                style={{
                  width: "100%", border: "1.5px solid var(--border)", borderRadius: "var(--radius)",
                  padding: "10px 12px", fontSize: "0.88rem", fontFamily: "Fraunces, serif",
                  fontStyle: "italic", resize: "vertical", background: "var(--soft-white)",
                }}
                id="advisor-lede-input"
              />
            </div>
            <div>
              <label className="micro-label" style={{ display: "block", marginBottom: 5 }}>
                Body
              </label>
              <textarea
                rows={5}
                value={advisorBody}
                onChange={e => setAdvisorBody(e.target.value)}
                placeholder="Expand in exposure / maturity / benchmark language. No legal verdicts."
                style={{
                  width: "100%", border: "1.5px solid var(--border)", borderRadius: "var(--radius)",
                  padding: "10px 12px", fontSize: "0.88rem", resize: "vertical", background: "var(--soft-white)",
                }}
                id="advisor-body-input"
              />
            </div>

            {/* Attribution */}
            <div style={{ background: "var(--soft-white)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 12px" }}>
              <div className="micro-label">Attribution</div>
              <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--navy)" }}>The Visentix Privacy Desk</div>
              <div style={{ marginTop: 8, borderTop: "1px dashed var(--border)", paddingTop: 8 }}>
                <div className="micro-label" style={{ marginBottom: 3 }}>Expert Reviewer Slot</div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontStyle: "italic" }}>Reserved for SME name + credential</div>
              </div>
            </div>

            {/* Codex reference — driven by the selected finding's type code */}
            {currentFinding && (
              <div>
                <div className="section-label" style={{ marginBottom: 8 }}>Codex Reference</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <CodexTooltip code={currentFinding.finding_type_code} />
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: 8, paddingTop: 4 }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={submitReview}
                disabled={!selected || approving}
                id="workbench-submit-btn"
              >
                {approving ? "Approving…" : "Submit Review"}
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={resetDecision}
                id="workbench-clear-btn"
              >
                Clear
              </button>
            </div>

            <IntelligenceMark />
          </div>
        </div>
      </div>

      {/* Mobile: stack */}
      <style>{`
        @media (max-width: 900px) {
          .workbench-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
