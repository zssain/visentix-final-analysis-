import type { ReportSection } from "../types";

export function TrendPanel({ content }: { content: ReportSection["content"] }) {
  return (
    <div data-testid="section-12" className="report-section">
      <h2>12. Trend &amp; Emerging Risk</h2>
      <p>{content.note as string}</p>
    </div>
  );
}
