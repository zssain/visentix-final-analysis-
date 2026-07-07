import { VciBadge } from "../VciBadge";
import type { ReportSection } from "../types";

export function Cover({ content }: { content: ReportSection["content"] }) {
  const domain = content.org_domain as string | undefined;
  const industry = content.org_industry as string | undefined;
  const size = content.org_size as string | undefined;
  const geography = content.org_geography as string | undefined;

  const hasMeta = domain || industry || size || geography;

  return (
    <div data-testid="section-1" className="report-section">
      <h1>{content.organization as string}</h1>

      {hasMeta && (
        <div style={{
          display: "flex", gap: 24, flexWrap: "wrap",
          marginTop: 4, marginBottom: 8,
          fontSize: "0.9rem", color: "#6b7280",
        }}>
          {domain && (
            <span>
              <span style={{ fontWeight: 600 }}>Domain</span>&nbsp;{domain}
            </span>
          )}
          {industry && (
            <span style={{ textTransform: "capitalize" }}>
              <span style={{ fontWeight: 600 }}>Industry</span>&nbsp;{industry}
            </span>
          )}
          {size && (
            <span style={{ textTransform: "capitalize" }}>
              <span style={{ fontWeight: 600 }}>Size</span>&nbsp;{size}
            </span>
          )}
          {geography && (
            <span>
              <span style={{ fontWeight: 600 }}>Geography</span>&nbsp;{geography}
            </span>
          )}
        </div>
      )}

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
