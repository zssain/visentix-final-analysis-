import { useState } from "react";
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

// Simple word-level diff:
// Returns segments marked as shared, added (gold), or removed (gray strikethrough)
function diffWords(
  yourText: string,
  exemplarText: string
): { word: string; kind: "shared" | "added" | "removed" }[] {
  const yourWords     = yourText.split(/\s+/).filter(Boolean);
  const exemplarWords = exemplarText.split(/\s+/).filter(Boolean);
  const yourSet       = new Set(yourWords.map(w => w.toLowerCase().replace(/[^a-z0-9]/g, "")));
  const exemplarSet   = new Set(exemplarWords.map(w => w.toLowerCase().replace(/[^a-z0-9]/g, "")));

  const result: { word: string; kind: "shared" | "added" | "removed" }[] = [];

  yourWords.forEach(w => {
    const k = w.toLowerCase().replace(/[^a-z0-9]/g, "");
    result.push({ word: w, kind: exemplarSet.has(k) ? "shared" : "removed" });
  });

  exemplarWords.forEach(w => {
    const k = w.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (!yourSet.has(k)) result.push({ word: w, kind: "added" });
  });

  return result;
}

function DiffSpan({ word, kind }: { word: string; kind: "shared" | "added" | "removed" }) {
  if (kind === "removed") return (
    <span style={{ color: "var(--warm-gray-dark)", textDecoration: "line-through", marginRight: 4 }}>{word}</span>
  );
  if (kind === "added") return (
    <span style={{
      background: "rgba(200,164,106,0.25)", color: "#7a5c20",
      padding: "0 2px", borderRadius: 2, marginRight: 4, fontWeight: 600,
    }}>{word}</span>
  );
  return <span style={{ marginRight: 4 }}>{word}</span>;
}

// [MOCK M-03] Exemplar clauses are hardcoded — real source: disclosure_clause where is_exemplar=true
export function BenchmarkLanguage({ content }: { content: ReportSection["content"] }) {
  const available = content.sme_cleaned_available as boolean;
  const entries   = (content.entries as ExemplarEntry[]) ?? [];
  const [diffsOnly, setDiffsOnly] = useState(false);

  if (!available) {
    return (
      <div data-testid="section-8" className="report-section">
        <h2>8. Benchmark Language Comparison</h2>
        <div style={{
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
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 12 }}>
        Your clause language compared to the SME-reviewed cohort exemplar.
        {/* [MOCK M-03] */}
        <span style={{
          marginLeft: 8, fontSize: "0.68rem", background: "rgba(200,164,106,0.15)",
          color: "#7a5c20", border: "1px dashed var(--gold)",
          padding: "1px 6px", borderRadius: 10, fontWeight: 700,
        }}>MOCK M-03</span>
      </p>

      {/* Toggle */}
      <div style={{ marginBottom: 16, display: "flex", gap: 8 }}>
        <button
          className={`btn btn-sm ${!diffsOnly ? "btn-primary" : "btn-outline"}`}
          onClick={() => setDiffsOnly(false)}
          aria-pressed={!diffsOnly}
          id="blc-show-full"
        >
          Show full clauses
        </button>
        <button
          className={`btn btn-sm ${diffsOnly ? "btn-primary" : "btn-outline"}`}
          onClick={() => setDiffsOnly(true)}
          aria-pressed={diffsOnly}
          id="blc-show-diffs"
        >
          Show differences only
        </button>
      </div>

      {entries.map((e, i) => {
        const yourText     = e.your_text ?? "";
        const exemplarText = e.exemplar_text ?? "";
        const yourDiff     = diffWords(yourText, exemplarText);
        const exemplarDiff = diffWords(exemplarText, yourText);

        return (
          <div key={i} style={{ marginBottom: 24 }}>
            {/* Domain header */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <span className="domain-eyebrow">{e.domain.replace(/_/g, " ").toUpperCase()}</span>
              {e.finding_code && (
                <span className="code-chip">{e.finding_code}</span>
              )}
            </div>

            {/* Side-by-side */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0,
              border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden",
            }}>
              {/* Your clause */}
              <div style={{ padding: "14px 16px", borderRight: "1px solid var(--border)" }}>
                <div style={{
                  fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 8,
                }}>Your Clause</div>
                <p style={{ fontSize: "0.88rem", lineHeight: 1.7 }}>
                  {yourText ? (
                    diffsOnly
                      ? yourDiff.filter(s => s.kind !== "shared").map((s, j) => (
                          <DiffSpan key={j} {...s} />
                        ))
                      : yourDiff.map((s, j) => <DiffSpan key={j} {...s} />)
                  ) : (
                    <em style={{ color: "var(--text-muted)" }}>No clause found in your notice for this domain.</em>
                  )}
                </p>
              </div>

              {/* Exemplar */}
              <div style={{ padding: "14px 16px", background: "rgba(9,35,79,0.02)" }}>
                <div style={{
                  fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 8,
                }}>Cohort Exemplar</div>
                <p style={{ fontSize: "0.88rem", lineHeight: 1.7 }}>
                  {diffsOnly
                    ? exemplarDiff.filter(s => s.kind !== "shared").map((s, j) => (
                        <DiffSpan key={j} {...s} />
                      ))
                    : exemplarDiff.map((s, j) => <DiffSpan key={j} {...s} />)
                  }
                </p>
              </div>
            </div>

            {/* Cohort footer */}
            <div style={{
              display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
              padding: "8px 14px", background: "var(--soft-white)",
              border: "1px solid var(--border)", borderTop: "none",
              borderRadius: "0 0 var(--radius) var(--radius)",
              fontSize: "0.75rem", color: "var(--text-muted)",
            }}>
              <span>
                Cohort: <strong style={{ color: "var(--navy)" }}>
                  n={e.cohort_size ?? 30} peers
                </strong>
              </span>
              {e.cohort_date && <span>· {e.cohort_date}</span>}
              {e.maturity_note && (
                <span style={{ fontStyle: "italic" }}>· {e.maturity_note}</span>
              )}
            </div>
          </div>
        );
      })}

      {/* Diff legend */}
      <div style={{ display: "flex", gap: 16, fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 8 }}>
        <span>
          <span style={{ background: "rgba(200,164,106,0.25)", padding: "0 4px", borderRadius: 2, fontWeight: 600, color: "#7a5c20" }}>Gold highlight</span>
          {" "}= exemplar adds this
        </span>
        <span>
          <span style={{ textDecoration: "line-through", color: "var(--warm-gray-dark)" }}>Strikethrough</span>
          {" "}= your weaker phrasing
        </span>
      </div>
    </div>
  );
}
