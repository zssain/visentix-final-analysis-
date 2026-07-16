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

export function BenchmarkLanguage({ content }: { content: ReportSection["content"] }) {
  const available = content.sme_cleaned_available as boolean;
  const entries   = (content.entries as ExemplarEntry[]) ?? [];

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
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 16 }}>
        How your privacy notice language compares to best-practice exemplars across key domains.
      </p>

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

            {/* Content cards */}
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
