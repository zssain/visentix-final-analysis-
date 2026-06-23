import type { ReportSection } from "../types";

export function Traceability({ content }: { content: ReportSection["content"] }) {
  return (
    <div data-testid="section-11" className="report-section">
      <h2>11. Source Traceability</h2>
      <p>{content.note as string}</p>
    </div>
  );
}
