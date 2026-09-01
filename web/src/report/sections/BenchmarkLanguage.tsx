import { useState } from "react";
import { CodexTooltip } from "../../components/CodexTooltip";
import { domainLabel } from "../../lib/domainLabels";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";

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
          return <span key={i} style={{ background: "color-mix(in oklab, var(--provisional) 22%, transparent)", color: "var(--provisional)", borderRadius: 2 }}>{s.text}</span>;
        if (s.type === "removed")
          return <span key={i} style={{ color: "var(--muted-foreground)", textDecoration: "line-through" }}>{s.text}</span>;
        return <span key={i}>{s.text}</span>;
      })}
    </p>
  );
}

export function BenchmarkLanguage({ content }: { content: ReportSection["content"] }) {
  const entries   = (content.entries as ExemplarEntry[]) ?? [];
  const [showDiff, setShowDiff] = useState(false);  // off by default

  if (entries.length === 0) {
    return (
      <div data-testid="section-8" className="report-section">
        <SectionHeading n={8} title="Benchmark Language Comparison" />
        <div data-testid="exemplar-placeholder" style={{
          background: "color-mix(in oklab, var(--provisional) 8%, transparent)", border: "1px dashed var(--gold)",
          padding: "16px 20px", borderRadius: "var(--radius)",
          color: "var(--text-secondary)", fontSize: "0.88rem",
        }}>
          No substantive notice clause is available for a domain comparison.
        </div>
      </div>
    );
  }

  return (
    <div data-testid="section-8" className="report-section">
      <SectionHeading n={8} title="Benchmark Language Comparison" />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
        <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>
          Your notice language by disclosed domain, with an approved peer comparator only where the evidence gates are met.
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
            background: showDiff ? "color-mix(in oklab, var(--provisional) 12%, transparent)" : "white",
            color: showDiff ? "var(--provisional)" : "var(--text-secondary)",
            borderRadius: "var(--radius)", cursor: "pointer", whiteSpace: "nowrap",
          }}
        >
          {showDiff ? "Hide differences" : "Show differences"}
        </button>
      </div>
      {showDiff && (
        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: 14 }}>
          <span style={{ background: "color-mix(in oklab, var(--provisional) 22%, transparent)", color: "var(--provisional)", padding: "0 4px", borderRadius: 2 }}>gold</span> = exemplar adds ·{" "}
          <span style={{ color: "var(--muted-foreground)", textDecoration: "line-through" }}>strike-through</span> = your notice drops
        </div>
      )}

      {entries.map((e, i) => {
        const yourText     = (e.your_text ?? "").trim();
        const exemplarText = (e.exemplar_text ?? "").trim();
        const hasYour      = yourText.length > 0;
        const hasExemplar  = exemplarText.length > 0;
        const displayDomain = domainLabel(e.domain);

        return (
          <div key={i} style={{ marginBottom: 28 }}>
            {/* Domain header */}
            <div style={{
              display: "flex", alignItems: "center", gap: 10, marginBottom: 8,
            }}>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{displayDomain.toUpperCase()}</span>
              {/* DDR-006: finding codes are hover/focus Codex targets */}
              {e.finding_code && <CodexTooltip code={e.finding_code} />}
            </div>

            {/* Diff view — merged single column when toggled on and both sides exist */}
            {showDiff && hasExemplar && hasYour ? (
              <div style={{
                padding: "16px 18px", border: "1px solid var(--border)",
                borderRadius: "var(--radius)", background: "color-mix(in oklab, var(--primary) 2%, transparent)",
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
              gridTemplateColumns: hasYour ? "1fr 1fr" : "1fr",
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
                    for {displayDomain}.
                  </p>
                )}
              </div>

              {/* Exemplar */}
              {hasExemplar && (
                <div style={{
                  padding: "16px 18px",
                  background: "color-mix(in oklab, var(--primary) 2%, transparent)",
                }}>
                  <div style={{
                    fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
                    letterSpacing: "0.09em", color: "var(--exec-blue)", marginBottom: 10,
                  }}>
                    Approved Peer Comparator
                  </div>
                  <p style={{
                    fontSize: "0.85rem", lineHeight: 1.75, color: "var(--text)",
                    margin: 0,
                  }}>
                    {exemplarText.length > 500 ? exemplarText.slice(0, 500) + "…" : exemplarText}
                  </p>
                </div>
              )}
              {!hasExemplar && (
                <div style={{ padding: "16px 18px", background: "color-mix(in oklab, var(--primary) 2%, transparent)" }}>
                  <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--exec-blue)", marginBottom: 10 }}>
                    Approved Peer Comparator
                  </div>
                  <p style={{ fontSize: "0.85rem", lineHeight: 1.6, color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>
                    No comparable approved peer language is available for this domain.
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
    </div>
  );
}
