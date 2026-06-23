import type { ReportSection } from "../types";

export function CompoundRisk({ content }: { content: ReportSection["content"] }) {
  return (
    <div data-testid="section-7" className="report-section">
      <h2>7. Compound Risk Analysis</h2>
      <p>Compound risk score: {(content.compound_score as number)?.toFixed(1)}</p>
    </div>
  );
}
