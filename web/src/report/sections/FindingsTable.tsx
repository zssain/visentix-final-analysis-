import { Fragment, useState } from "react";
import { AdvisorNote } from "../../components/AdvisorNote";
import { CodexTooltip } from "../../components/CodexTooltip";
import { InfoButton } from "../explain";
import { EvidenceStack } from "./EvidenceStack";
import { domainLabel } from "../../lib/domainLabels";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { Button } from "@/components/ui/button";
import { severityLabel } from "../../lib/labels";

interface Finding {
  id: string;
  domain: string;
  severity: string;
  score: number;
  confidence: string | number;
  evidence?: { clause_id?: string; section_reference?: string; excerpt?: string }[];
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
  const snapshotId   = (content.snapshot_id as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const frozenDate   = (content.date        as string | undefined) ?? "—";
  const cohortSize   = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate   = (content.cohort_date as string | undefined) ?? "—";
  const isDraft      = (content.is_draft    as boolean | undefined) ?? false;
  const assessmentId = (content.assessment_id as string | undefined) ?? "";
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div data-testid="section-6" className="report-section">
      <SectionHeading n={6} title="Disclosure Findings" />
      <p className="text-muted-foreground text-sm mb-4">
        {content.total as number} findings · Click a finding to view the full Analyst / Advisor note
      </p>

      {/* Summary table */}
      <table className="mb-4 w-full border-collapse text-sm">
        <thead>
          <tr className="bg-muted/40">
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
            // Real VCI parsed from the finding's confidence, or honest absence —
            // never a fabricated 75 (DATA-003).
            const confidenceText = f.confidence === undefined || f.confidence === null ? "" : String(f.confidence);
            const parsedVci = Number(confidenceText.replace("%", ""));
            const vci = Number.isFinite(parsedVci) && confidenceText.trim() ? parsedVci : undefined;
            return (
              <Fragment key={f.id}>
                <tr className="border-b">
                  <td style={td}>
                    <div className="flex items-center gap-1">
                      <CodexTooltip code={code} />
                      {assessmentId && <InfoButton assessmentId={assessmentId} elementType="finding" elementKey={code} label={code} />}
                    </div>
                  </td>
                  <td style={td}>
                    {domainLabel(f.domain)}
                  </td>
                  <td style={td}>
                    <span className={`badge ${severityBadgeClass(f.severity)}`}>
                      {severityLabel(f.severity)}
                    </span>
                  </td>
                  <td style={td} className="font-data tabular-nums">
                    {f.score?.toFixed(1)}
                  </td>
                  <td style={td} className="text-sm text-muted-foreground">
                    {vci !== undefined ? confidenceText : "Not recorded"}
                  </td>
                  <td style={td}>
                    <Button variant="ghost" size="sm" onClick={() => setExpanded(isOpen ? null : f.id)}
                      aria-expanded={isOpen}
                      aria-label={`${isOpen ? "Collapse" : "Expand"} finding ${code}`}
                    >
                      {isOpen ? "Collapse ↑" : "View ↓"}
                    </Button>
                  </td>
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={6} className="px-2 pb-5 pt-4">
                      <AdvisorNote
                        findingCode={code}
                        title={f.id}
                        domain={f.domain}
                        status={isDraft ? "draft" : "approved"}
                        snapshotId={snapshotId}
                        frozenDate={frozenDate}
                        exposureScore={f.score}
                        cohortPercentile={f.percentile}
                        vci={vci}
                        formulaId="F-002"
                        formulaDesc={(content.formula_descs as Record<string, string> | undefined)?.["F-002"] ?? ""}
                        cohortSize={cohortSize}
                        cohortDate={cohortDate}
                        advisorLede={f.advisor_lede ?? ""}
                        advisorBody={f.advisor_body ?? ""}
                        lineageRefs={f.lineage_refs}
                      />
                      {assessmentId && <EvidenceStack assessmentId={assessmentId} findingId={f.id} />}
                      <div className="mt-3 text-sm text-muted-foreground">
                        {(f.evidence ?? []).length > 0 ? (f.evidence ?? []).map((ev, i) => (
                          <blockquote key={i} className="my-2 border-l-[3px] border-[var(--provisional)] px-3 py-2">
                            <strong>{ev.section_reference ?? ev.clause_id ?? "Stored clause"}</strong>
                            <div>{ev.excerpt ?? "Excerpt not recorded"}</div>
                          </blockquote>
                        )) : <em>No triggering clause reference is stored for this finding.</em>}
                      </div>
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
