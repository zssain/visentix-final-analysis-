/**
 * SME Workbench v2 — three-pane layout
 *
 * Left:   Source clause + de-id checker (PII detected → category label → Redact)
 * Center: Auto-finding + Analyst metric grid + Confirm / Edit / Dismiss
 * Right:  Advisor Note editor + Codex reference
 *
 * [MOCK M-04] Training label counts hardcoded — real: /api/admin/health training_stats
 */
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { CodexTooltip }   from "../../components/CodexTooltip";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import "../../components/furniture.css";

interface ReviewItem {
  assessment_id: string;
  status: string;
  finding_reviews: Record<string, unknown>;
  approved_by: string;
}

// Simulated PII tokens in example clause (de-id checker)
const EXAMPLE_CLAUSE = "This data sharing agreement was reviewed by Jane Smith (jane.smith@acmecorp.com) and covers transfers to https://analytics-partner.com for marketing analytics purposes.";

// [MOCK M-04] — real: /api/admin/health training_stats block
const MOCK_LABELS = { confirmed: 142, edited: 31, dismissed: 12 };

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

export function ReviewQueue() {
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [redacted, setRedacted] = useState(false);
  const [advisorLede, setAdvisorLede] = useState("");
  const [advisorBody, setAdvisorBody] = useState("");
  const [action, setAction] = useState<"confirm" | "edit" | "dismiss" | null>(null);

  const clauseText = EXAMPLE_CLAUSE;
  const piiTokens  = detectPii(clauseText);
  const hasPii     = piiTokens.length > 0 && !redacted;

  useEffect(() => {
    api.get("/review/queue")
      .then((data) => setQueue(Array.isArray(data) ? data : []))
      .catch((err) => { if (err instanceof ApiError && err.status === 401) return; })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", marginBottom: 6 }}>
          <h1 style={{ fontSize: "1.4rem", fontWeight: 800, color: "var(--navy)", letterSpacing: "-0.02em" }}>
            SME Workbench
          </h1>
          <span className="badge badge-gold">
            {loading ? "—" : queue.length} findings pending
          </span>
        </div>

        {/* [MOCK M-04] Training label counter */}
        <div style={{ display: "flex", gap: 16, fontSize: "0.8rem", color: "var(--text-muted)", flexWrap: "wrap" }}>
          <span>Training labels
            <span style={{
              marginLeft: 6, fontSize: "0.65rem", background: "rgba(200,164,106,0.15)",
              color: "#7a5c20", border: "1px dashed var(--gold)",
              padding: "1px 7px", borderRadius: 10, fontWeight: 700,
            }}>MOCK M-04</span>:
          </span>
          <span style={{ color: "var(--teal)", fontWeight: 700 }}>✓ {MOCK_LABELS.confirmed} confirmed</span>
          <span style={{ color: "var(--exec-blue)", fontWeight: 700 }}>✎ {MOCK_LABELS.edited} edited</span>
          <span style={{ color: "var(--red)", fontWeight: 700 }}>✕ {MOCK_LABELS.dismissed} dismissed</span>
        </div>
      </div>

      {/* Three-pane workbench */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
        gap: 16, alignItems: "start",
      }}>

        {/* ── LEFT: Source clause ── */}
        <div className="card" style={{ overflow: "visible" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--soft-white)", borderTopLeftRadius: "var(--radius-lg)", borderTopRightRadius: "var(--radius-lg)" }}>
            <div className="section-label">Source Clause</div>
            <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
              <span className="code-chip" style={{ fontSize: "0.7rem" }}>C-118</span>
              <span className="domain-eyebrow">data sharing</span>
            </div>
          </div>

          <div style={{ padding: "14px 16px", fontSize: "0.88rem", lineHeight: 1.7, color: "var(--text)", minHeight: 120 }}>
            <ClauseDisplay text={clauseText} redacted={redacted} />
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
            <div style={{
              margin: "0 16px 14px", padding: "8px 12px",
              background: "rgba(85,199,179,0.08)", border: "1px solid rgba(85,199,179,0.3)",
              borderRadius: "var(--radius)", fontSize: "0.78rem", color: "#0d6b5c", fontWeight: 600,
            }}>
              ✓ All PII replaced with [REDACTED]
            </div>
          )}

          <div style={{ padding: "10px 16px", borderTop: "1px solid var(--border)" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Source: <span style={{ fontFamily: "var(--font-data)", fontWeight: 600 }}>privacy_notice &gt; section_3 &gt; C-118</span>
            </span>
          </div>
        </div>

        {/* ── CENTER: Auto-finding ── */}
        <div className="card" style={{ overflow: "visible" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--soft-white)", borderTopLeftRadius: "var(--radius-lg)", borderTopRightRadius: "var(--radius-lg)" }}>
            <div className="section-label">Auto Finding</div>
          </div>
          <div style={{ padding: "14px 16px" }}>
            {/* Finding header */}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
              <CodexTooltip code="SH-002" />
              <span className="badge badge-high">High</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--navy)", marginBottom: 12 }}>
              Broad Sharing Language
            </div>

            {/* Mini metric grid */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr",
              gap: 1, background: "var(--border)",
              border: "1px solid var(--border)", borderRadius: "var(--radius)", marginBottom: 16,
            }}>
              {[
                { label: "Exposure", value: "72.4" },
                { label: "VCI",      value: "81%" },
                { label: "Percentile", value: "74th" },
                { label: "Formula", value: "F-002" },
              ].map(m => (
                <div key={m.label} style={{ background: "white", padding: "10px 12px" }}>
                  <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 2 }}>{m.label}</div>
                  <div style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums", fontSize: "1.1rem", fontWeight: 700, color: "var(--navy)" }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Queue list */}
            <div style={{ marginBottom: 12 }}>
              <div className="section-label" style={{ marginBottom: 6 }}>Review Queue</div>
              {loading ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Loading queue…</div>
              ) : queue.length === 0 ? (
                <div style={{
                  padding: "16px 0", textAlign: "center",
                  color: "var(--text-muted)", fontSize: "0.82rem",
                }}>
                  All caught up — no findings pending
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {queue.slice(0, 4).map(item => (
                    <button
                      key={item.assessment_id}
                      onClick={() => setSelected(item)}
                      style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "8px 10px", borderRadius: "var(--radius)",
                        border: `1px solid ${selected?.assessment_id === item.assessment_id ? "var(--navy)" : "var(--border)"}`,
                        background: selected?.assessment_id === item.assessment_id ? "rgba(9,35,79,0.04)" : "white",
                        cursor: "pointer", textAlign: "left",
                      }}
                    >
                      <span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--navy)" }}>
                        {item.assessment_id.slice(0, 14)}…
                      </span>
                      <span className={`badge ${item.status === "in_review" ? "badge-gold" : "badge-draft"}`} style={{ fontSize: "0.65rem" }}>
                        {item.status.replace("_", " ")}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Confirm / Edit / Dismiss */}
            <div className="section-label" style={{ marginBottom: 8 }}>Finding Actions</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                className={`btn btn-sm ${action === "confirm" ? "btn-teal" : "btn-outline"}`}
                onClick={() => setAction("confirm")}
                disabled={hasPii}
                title={hasPii ? "Resolve PII before confirming" : undefined}
                id="finding-confirm-btn"
              >
                ✓ Confirm
              </button>
              <button
                className={`btn btn-sm ${action === "edit" ? "btn-primary" : "btn-outline"}`}
                onClick={() => setAction("edit")}
                id="finding-edit-btn"
              >
                ✎ Edit
              </button>
              <button
                className={`btn btn-sm ${action === "dismiss" ? "btn-danger" : "btn-outline"}`}
                onClick={() => setAction("dismiss")}
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
              <div style={{
                marginTop: 10, padding: "8px 12px",
                background: action === "dismiss" ? "rgba(248,113,113,0.06)" : "rgba(85,199,179,0.08)",
                border: `1px solid ${action === "dismiss" ? "rgba(248,113,113,0.25)" : "rgba(85,199,179,0.3)"}`,
                borderRadius: "var(--radius)", fontSize: "0.78rem", fontWeight: 600,
                color: action === "dismiss" ? "#b91c1c" : "#0d6b5c",
              }}>
                Action: <strong>{action.toUpperCase()}</strong> — label will be saved on submit
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: Advisor Note editor ── */}
        <div className="card" style={{ overflow: "visible" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--soft-white)", borderTopLeftRadius: "var(--radius-lg)", borderTopRightRadius: "var(--radius-lg)" }}>
            <div className="section-label">Advisor Note Editor</div>
          </div>
          <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 5 }}>
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
              <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 5 }}>
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
              <div style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>Attribution</div>
              <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--navy)" }}>The Visentix Privacy Desk</div>
              <div style={{ marginTop: 8, borderTop: "1px dashed var(--border)", paddingTop: 8 }}>
                <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--text-muted)", marginBottom: 3 }}>Expert Reviewer Slot</div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontStyle: "italic" }}>Reserved for SME name + credential</div>
              </div>
            </div>

            {/* Codex reference */}
            <div>
              <div className="section-label" style={{ marginBottom: 8 }}>Codex Reference</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["SH-002", "TRK-007", "RT-003"].map(code => (
                  <CodexTooltip key={code} code={code} />
                ))}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, paddingTop: 4 }}>
              <button
                className="btn btn-primary btn-sm"
                disabled={hasPii || !action}
                id="workbench-submit-btn"
              >
                Submit Review
              </button>
              <button className="btn btn-ghost btn-sm">Clear</button>
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
