import type { ReportSection } from "../types";

export function RiskReduction({ content }: { content: ReportSection["content"] }) {
  return (
    <div data-testid="section-10" className="report-section">
      <h2>10. Risk Reduction Priorities</h2>
      <p>High severity: {content.high_count as number} findings</p>
      <p>Medium severity: {content.medium_count as number} findings</p>
    </div>
  );
}
