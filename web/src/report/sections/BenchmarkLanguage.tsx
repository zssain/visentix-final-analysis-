import { useState } from "react";
import { CodexTooltip } from "../../components/CodexTooltip";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

interface ExemplarEntry {
  domain: string;
  your_text?: string;
  exemplar_text: string;
  maturity_note?: string;
  finding_code?: string;
  cohort_size?: number;
  cohort_date?: string;
}

type DiffSeg = { text: string; type: "same" | "added" | "removed" };

/** Word-level diff (LCS) from `a` (your notice) to `b` (exemplar):
 *  words only in `b` are additions (gold), only in `a` are removals
 *  (warm-gray strikethrough). Deterministic — pure display, no scoring. */
function wordDiff(a: string, b: string): DiffSeg[] {
  const aw = a.split(/(\s+)/).filter(Boolean);
  const bw = b.split(/(\s+)/).filter(Boolean);
  const n = aw.length, m = bw.length;
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      lcs[i][j] = aw[i] === bw[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const out: DiffSeg[] = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (aw[i] === bw[j]) { out.push({ text: aw[i], type: "same" }); i++; j++; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) { out.push({ text: aw[i], type: "removed" }); i++; }
    else { out.push({ text: bw[j], type: "added" }); j++; }
  }
  while (i < n) { out.push({ text: aw[i], type: "removed" }); i++; }
  while (j < m) { out.push({ text: bw[j], type: "added" }); j++; }
  return out;
}

function DiffView({ your, exemplar }: { your: string; exemplar: string }) {
  const segs = wordDiff(your, exemplar);
  return (
    <p style={{ fontSize: "0.85rem", lineHeight: 1.85, color: "var(--text)", margin: 0 }}>
      {segs.map((s, i) => {
        if (s.type === "added")
          return <span key={i} style={{ background: "rgba(200,164,106,0.22)", color: "#7a5a1e", borderRadius: 2 }}>{s.text}</span>;
        if (s.type === "removed")
          return <span key={i} style={{ color: "#9a8f7a", textDecoration: "line-through" }}>{s.text}</span>;
        return <span key={i}>{s.text}</span>;
      })}
    </p>
  );
}

export function BenchmarkLanguage({ content }: { content: ReportSection["content"] }) {
  const available = content.sme_cleaned_available as boolean;
  const entries   = (content.entries as ExemplarEntry[]) ?? [];
  const [showDiff, setShowDiff] = useState(false);  // off by default

  if (!available || entries.length === 0) {
    return (
      <div data-testid="section-8" className="report-section">
        <h2>8. Benchmark Language Comparison</h2>
        <div data-testid="exemplar-placeholder" style={{
          background: "rgba(200,164,106,0.08)", border: "1px dashed var(--gold)",
          padding: "16px 20px", borderRadius: "var(--radius)",
          color: "var(--text-secondary)", fontSize: "0.88rem",
        }}>
          Pending SME-reviewed exemplar — this section will be populated once subject-matter
          expert review is complete.
        </div>
      </div>
    );
  }

  return (
    <div data-testid="section-8" className="report-section">
      <h2>8. Benchmark Language Comparison</h2>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>
          How your privacy notice language compares to best-practice exemplars across key domains.
        </p>
        {/* Show-differences toggle (off by default): gold = language the exemplar
            adds, warm-gray strikethrough = language it drops. */}
        <button
          type="button"
          onClick={() => setShowDiff(v => !v)}
          aria-pressed={showDiff}
          data-testid="diff-toggle"
          style={{
            fontSize: "0.74rem", fontWeight: 600, padding: "5px 12px",
            border: `1px solid ${showDiff ? "var(--gold)" : "var(--border)"}`,
            background: showDiff ? "rgba(200,164,106,0.12)" : "white",
            color: showDiff ? "#7a5a1e" : "var(--text-secondary)",
            borderRadius: "var(--radius)", cursor: "pointer", whiteSpace: "nowrap",
          }}
        >
          {showDiff ? "Hide differences" : "Show differences"}
        </button>
      </div>
      {showDiff && (
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 14 }}>
          <span style={{ background: "rgba(200,164,106,0.22)", color: "#7a5a1e", padding: "0 4px", borderRadius: 2 }}>gold</span> = exemplar adds ·{" "}
          <span style={{ color: "#9a8f7a", textDecoration: "line-through" }}>strike-through</span> = your notice drops
        </div>
      )}

      {entries.map((e, i) => {
        const yourText     = (e.your_text ?? "").trim();
        const exemplarText = (e.exemplar_text ?? "").trim();
        const hasYour      = yourText.length > 0;
        const hasExemplar  = exemplarText.length > 0;
        const domainLabel  = e.domain.replace(/_/g, " ");

        return (
          <div key={i} style={{ marginBottom: 28 }}>
            {/* Domain header */}
            <div style={{
              display: "flex", alignItems: "center", gap: 10, marginBottom: 8,
            }}>
              <span className="domain-eyebrow">{domainLabel.toUpperCase()}</span>
              {/* DDR-006: finding codes are hover/focus Codex targets */}
              {e.finding_code && <CodexTooltip code={e.finding_code} />}
              {!hasYour && (
                <span style={{
                  fontSize: "0.7rem", fontWeight: 600,
                  color: "var(--red)", background: "rgba(248,113,113,0.08)",
                  border: "1px solid rgba(248,113,113,0.2)",
                  padding: "1px 8px", borderRadius: 4,
                }}>
                  Gap — not found in your notice
                </span>
              )}
            </div>

            {/* Diff view — merged single column when toggled on and both sides exist */}
            {showDiff && hasExemplar && hasYour ? (
              <div style={{
                padding: "16px 18px", border: "1px solid var(--border)",
                borderRadius: "var(--radius)", background: "rgba(9,35,79,0.02)",
              }}>
                <div style={{
                  fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.09em", color: "var(--navy)", marginBottom: 10,
                }}>
                  Your Notice → Exemplar (differences)
                </div>
                <DiffView
                  your={yourText.length > 500 ? yourText.slice(0, 500) : yourText}
                  exemplar={exemplarText.length > 500 ? exemplarText.slice(0, 500) : exemplarText}
                />
              </div>
            ) : (
            /* Content cards */
            <div style={{
              display: "grid",
              gridTemplateColumns: hasExemplar && hasYour ? "1fr 1fr" : "1fr",
              gap: 0,
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              overflow: "hidden",
            }}>
              {/* Your clause */}
              <div style={{
                padding: "16px 18px",
                borderRight: hasExemplar && hasYour ? "1px solid var(--border)" : "none",
              }}>
                <div style={{
                  fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.09em", color: "var(--navy)", marginBottom: 10,
                }}>
                  Your Notice
                </div>
                {hasYour ? (
                  <p style={{
                    fontSize: "0.85rem", lineHeight: 1.75, color: "var(--text)",
                    margin: 0,
                  }}>
                    {yourText.length > 500 ? yourText.slice(0, 500) + "…" : yourText}
                  </p>
                ) : (
                  <p style={{
                    fontSize: "0.85rem", lineHeight: 1.6, color: "var(--text-muted)",
                    fontStyle: "italic", margin: 0,
                  }}>
                    Your privacy notice does not appear to include a dedicated clause
                    for {domainLabel}. Adding one would strengthen your disclosure maturity.
                  </p>
                )}
              </div>

              {/* Exemplar */}
              {hasExemplar && (
                <div style={{
                  padding: "16px 18px",
                  background: "rgba(9,35,79,0.02)",
                }}>
                  <div style={{
                    fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
                    letterSpacing: "0.09em", color: "var(--exec-blue)", marginBottom: 10,
                  }}>
                    Best-Practice Exemplar
                  </div>
                  <p style={{
                    fontSize: "0.85rem", lineHeight: 1.75, color: "var(--text)",
                    margin: 0,
                  }}>
                    {exemplarText.length > 500 ? exemplarText.slice(0, 500) + "…" : exemplarText}
                  </p>
                </div>
              )}
            </div>
            )}

            {/* Footer */}
            {e.maturity_note && (
              <div style={{
                padding: "8px 16px",
                background: "var(--soft-white)",
                border: "1px solid var(--border)", borderTop: "none",
                borderRadius: "0 0 var(--radius) var(--radius)",
                fontSize: "0.75rem", color: "var(--text-muted)",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <span style={{ fontWeight: 600, color: "var(--navy)" }}>
                  {/* Honest n only — never a fabricated fallback (M-12 / Hard Rule 7) */}
                  {e.cohort_size ? `Cohort: n=${e.cohort_size} peers` : "Cohort size unavailable"}
                </span>
                <span style={{ fontStyle: "italic" }}>· {e.maturity_note}</span>
              </div>
            )}
          </div>
        );
      })}
      {/* DDR-007: every report section carries the mark */}
      <div style={{ marginTop: 4 }}><IntelligenceMark /></div>
    </div>
  );
}
