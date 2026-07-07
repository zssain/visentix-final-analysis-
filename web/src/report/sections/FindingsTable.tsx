import { Fragment, useState } from "react";
import { AdvisorNote } from "../../components/AdvisorNote";
import { CodexTooltip } from "../../components/CodexTooltip";
import type { ReportSection } from "../types";

interface Finding {
  id: string;
  domain: string;
  severity: string;
  score: number;
  confidence: string;
  finding_code?: string;
  advisor_lede?: string;
  advisor_body?: string;
  percentile?: number;
  lineage_refs?: string[];
}

function severityBadgeClass(s: string): string {
  const m: Record<string, string> = {
    high: "badge-high", elevated: "badge-elevated",
    moderate: "badge-moderate", low: "badge-low",
  };
  return m[s.toLowerCase()] ?? "badge-moderate";
}

export function FindingsTable({ content }: { content: ReportSection["content"] }) {
  const findings     = (content.findings    as Finding[]) ?? [];
  const snapshotId   = (content.snapshot_id as string | undefined) ?? "S-0000";
  const frozenDate   = (content.date        as string | undefined) ?? "—";
  const cohortSize   = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate   = (content.cohort_date as string | undefined) ?? "—";
  const isDraft      = (content.is_draft    as boolean | undefined) ?? false;
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div data-testid="section-6" className="report-section">
      <h2>6. Disclosure Findings</h2>
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 16 }}>
        {content.total as number} findings · Click a finding to view the full Analyst / Advisor note
      </p>

      {/* Summary table */}
      <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 16 }}>
        <thead>
          <tr style={{ background: "var(--soft-white)" }}>
            <th style={th}>Code</th>
            <th style={th}>Domain</th>
            <th style={th}>Severity</th>
            <th style={th}>Score</th>
            <th style={th}>Confidence</th>
            <th style={th}>Detail</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f) => {
            const code = f.finding_code ?? f.id;
            const isOpen = expanded === f.id;
            return (
              <Fragment key={f.id}>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={td}>
                    <CodexTooltip code={code} />
                  </td>
                  <td style={{ ...td, textTransform: "capitalize" }}>
                    {f.domain.replace(/_/g, " ")}
                  </td>
                  <td style={td}>
                    <span className={`badge ${severityBadgeClass(f.severity)}`}>
                      {f.severity}
                    </span>
                  </td>
                  <td style={{ ...td, fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums" }}>
                    {f.score?.toFixed(1)}
                  </td>
                  <td style={{ ...td, color: "var(--text-muted)", fontSize: "0.82rem" }}>
                    {f.confidence}
                  </td>
                  <td style={td}>
                    <button
                      className="btn btn-ghost btn-xs"
                      onClick={() => setExpanded(isOpen ? null : f.id)}
                      aria-expanded={isOpen}
                      aria-label={`${isOpen ? "Collapse" : "Expand"} finding ${code}`}
                    >
                      {isOpen ? "Collapse ↑" : "View ↓"}
                    </button>
                  </td>
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={6} style={{ padding: "16px 8px 20px" }}>
                      <AdvisorNote
                        findingCode={code}
                        title={f.id}
                        domain={f.domain}
                        status={isDraft ? "draft" : "approved"}
                        snapshotId={snapshotId}
                        frozenDate={frozenDate}
                        exposureScore={f.score}
                        cohortPercentile={f.percentile ?? 50}
                        vci={Number(f.confidence?.replace("%", "")) || 75}
                        formulaId="F-002"
                        formulaDesc="Multiplies jurisdiction importance by regulator priority and disclosure severity across each domain."
                        cohortSize={cohortSize}
                        cohortDate={cohortDate}
                        advisorLede={f.advisor_lede ?? "This finding reflects elevated exposure in this disclosure domain relative to the assessed peer cohort."}
                        advisorBody={f.advisor_body ?? "The organisation's notice language in this area presents a measurable exposure gap compared to the cohort benchmark. The disclosure scope and specificity fall below the 75th percentile of peer practice, indicating a maturity gap that warrants attention."}
                        lineageRefs={f.lineage_refs}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const th: React.CSSProperties = {
  border: "1px solid var(--border)", padding: "9px 12px",
  textAlign: "left", fontWeight: 700, fontSize: "0.72rem",
  textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--text-secondary)",
};
const td: React.CSSProperties = { border: "1px solid var(--border)", padding: "10px 12px" };
