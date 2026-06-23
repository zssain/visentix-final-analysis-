import type { ReportSection } from "../types";

interface Rec { severity: string; code: string; title: string; prose: string; }

export function Recommendations({ content }: { content: ReportSection["content"] }) {
  const recs = (content.recommendations as Rec[]) ?? [];
  return (
    <div data-testid="section-9" className="report-section">
      <h2>9. Strategic Recommendations</h2>
      {recs.map((r, i) => (
        <div key={i} style={{ marginBottom: 12, padding: 8, borderLeft: `3px solid ${r.severity === "high" ? "#dc2626" : "#f59e0b"}` }}>
          <strong>[{r.severity.toUpperCase()}] {r.code}</strong>
          <p>{r.prose}</p>
        </div>
      ))}
    </div>
  );
}
