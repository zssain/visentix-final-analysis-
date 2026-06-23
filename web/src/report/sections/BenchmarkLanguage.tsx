import type { ReportSection } from "../types";

interface ExemplarEntry { domain: string; exemplar_text: string; maturity_note?: string; }

export function BenchmarkLanguage({ content }: { content: ReportSection["content"] }) {
  const available = content.sme_cleaned_available as boolean;
  const entries = (content.entries as ExemplarEntry[]) ?? [];

  return (
    <div data-testid="section-8" className="report-section">
      <h2>8. Benchmark Language Comparison</h2>
      {!available && (
        <div className="placeholder" data-testid="exemplar-placeholder" style={{
          background: "#fefce8", border: "1px dashed #ca8a04", padding: 12, borderRadius: 4,
        }}>
          Pending SME-cleaned exemplar — this section will be populated once
          subject-matter expert review is complete.
        </div>
      )}
      {available && entries.map((e, i) => (
        <div key={i} style={{ marginBottom: 16 }}>
          <h3>{e.domain}</h3>
          <blockquote style={{ borderLeft: "3px solid #0f3460", paddingLeft: 12 }}>
            {e.exemplar_text}
          </blockquote>
          {e.maturity_note && <p><em>{e.maturity_note}</em></p>}
        </div>
      ))}
    </div>
  );
}
