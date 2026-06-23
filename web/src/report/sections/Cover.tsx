import { VciBadge } from "../VciBadge";
import type { ReportSection } from "../types";

export function Cover({ content }: { content: ReportSection["content"] }) {
  return (
    <div data-testid="section-1" className="report-section">
      <h1>{content.organization as string}</h1>
      <p>{content.report_title as string}</p>
      <div className="score-display" style={{ fontSize: "3em", fontWeight: "bold", color: "#0f3460" }}>
        {(content.overall_score as number)?.toFixed(1)}
      </div>
      <p>Overall Privacy Intelligence Score</p>
      <VciBadge label={content.vci_label as string} />
      <p style={{ marginTop: 8, color: "#9ca3af", fontSize: "0.85em" }}>
        {content.date as string} · Snapshot: {(content.snapshot_id as string)?.slice(0, 12)}
      </p>
    </div>
  );
}
