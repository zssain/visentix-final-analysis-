import type { ReportSection } from "../types";

export function RegulatorExposure({ content }: { content: ReportSection["content"] }) {
  return (
    <div data-testid="section-5" className="report-section">
      <h2>5. Regulator Exposure</h2>
      <p>Regulatory exposure score: {(content.regulatory_score as number)?.toFixed(1)} ({content.tier as string})</p>
    </div>
  );
}
