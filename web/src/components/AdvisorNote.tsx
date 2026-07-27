import { useState } from "react";
import { ViewSwitch } from "./ViewSwitch";
import { CodexTooltip } from "./CodexTooltip";
import { ProvenanceRibbon } from "./ProvenanceRibbon";
import { ScoreCell } from "./ScoreCell";
import { IntelligenceMark } from "./IntelligenceMark";
import { scoreBandColor } from "../lib/scoreBands";
import "./advisor-note.css";
import "./furniture.css";

export interface AdvisorNoteProps {
  /* Identity */
  findingCode: string;       // e.g. "TRK-007"
  title: string;
  domain: string;            // e.g. "data_sharing"

  /* Status */
  status: "draft" | "approved";
  snapshotId: string;
  formulaVersion?: string;
  frozenDate?: string;

  /* Analyst layer */
  exposureScore: number;
  cohortPercentile: number;  // 0-100
  vci: number;               // 0-100
  formulaId: string;
  formulaDesc: string;
  cohortSize: number;
  cohortDate: string;

  /* Advisor layer */
  advisorLede: string;
  advisorBody: string;

  /* Lineage chips (clause refs etc.) */
  lineageRefs?: string[];

  /* View switch default */
  defaultView?: "analyst" | "advisor";
}

function domainLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function AdvisorNote({
  findingCode, title, domain,
  status, snapshotId, formulaVersion, frozenDate,
  exposureScore, cohortPercentile, vci,
  formulaId, formulaDesc, cohortSize, cohortDate,
  advisorLede, advisorBody,
  lineageRefs = [],
  defaultView = "analyst",
}: AdvisorNoteProps) {
  const [view, setView] = useState<"analyst" | "advisor">(defaultView);
  const isDraft = status === "draft";

  const lineageInputs = [
    { label: findingCode, type: "clause" },
    { label: "Regulator", type: "regulator" },
    { label: "Jurisdiction", type: "jurisdiction" },
    { label: `n=${cohortSize}`, type: "cohort" },
  ];

  return (
    <div className={`advisor-note-wrap ${isDraft ? "draft-state" : ""}`}>
      {/* Provenance ribbon */}
      <div style={{ padding: "12px 20px 0" }}>
        <ProvenanceRibbon
          snapshotId={snapshotId}
          formulaVersion={formulaVersion}
          frozenDate={frozenDate}
          status={status}
        />
      </div>

      {/* Header */}
      <div className="an-header">
        <div className="an-header-left">
          <div className="an-header-meta">
            <CodexTooltip code={findingCode} />
            <span className="domain-eyebrow">{domainLabel(domain)}</span>
          </div>
          <h3 className="an-title">{title}</h3>
        </div>
        <ViewSwitch value={view} onChange={setView} />
      </div>

      {/* Body */}
      <div className="an-body">
        {view === "analyst" ? (
          <>
            {/* 3-up metric grid */}
            <div className="an-analyst-grid">
              {/* Exposure */}
              <div className="an-metric-cell">
                <div className="an-metric-label">Exposure Score</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <ScoreCell
                    value={exposureScore}
                    formulaId={formulaId}
                    formulaDesc={formulaDesc}
                    inputs={lineageInputs}
                    vci={vci}
                    snapshotId={snapshotId}
                    frozenDate={frozenDate ?? "—"}
                    cohortSize={cohortSize}
                    cohortDate={cohortDate}
                    size="lg"
                  />
                  <span className="an-metric-sub">/ 100</span>
                </div>
                <div className="an-score-bar">
                  <div
                    className="an-score-bar-fill"
                    style={{
                      width: `${exposureScore}%`,
                      background: scoreBandColor(exposureScore),
                    }}
                  />
                </div>
              </div>

              {/* Cohort percentile */}
              <div className="an-metric-cell">
                <div className="an-metric-label">Cohort Percentile</div>
                <div className="an-metric-value">{cohortPercentile}<span style={{ fontSize: "0.6em" }}>th</span></div>
                <div className="an-metric-sub">n={cohortSize} peers · {cohortDate}</div>
              </div>

              {/* VCI */}
              <div className="an-metric-cell">
                <div className="an-metric-label">Confidence (VCI)</div>
                <div className="an-metric-value">{vci}<span style={{ fontSize: "0.6em" }}>%</span></div>
                <div className="an-metric-sub">Visentix Confidence Index</div>
              </div>
            </div>

            {/* Lineage refs */}
            {lineageRefs.length > 0 && (
              <div className="an-lineage-chips">
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600 }}>Sources:</span>
                {lineageRefs.map(ref => (
                  <span key={ref} className="an-lineage-chip">{ref}</span>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            {/* Advisor prose — M-05: rendered verbatim from the frozen snapshot's
                Advisor layer, never regenerated at render time. When the snapshot
                carries no Advisor prose, show honest absence (no house-voice
                filler is fabricated on the client). */}
            <div className="an-advisor-body">
              {(advisorLede.trim() || advisorBody.trim()) ? (
                <>
                  {advisorLede.trim() && <p className="an-advisor-lede">{advisorLede}</p>}
                  {advisorBody.trim() && <p className="an-advisor-prose">{advisorBody}</p>}
                </>
              ) : (
                <p className="an-advisor-prose" data-testid="advisor-absent" style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
                  An advisor perspective for this finding is not part of this snapshot.
                </p>
              )}

              {/* Metric pills */}
              <div className="an-pills">
                <span className="an-pill exposure">Exposure: {exposureScore.toFixed(1)}</span>
                <span className="an-pill cohort">{cohortPercentile}th percentile · n={cohortSize}</span>
                <span className="an-pill vci">VCI {vci}%</span>
              </div>
            </div>

            {/* Attribution */}
            <div className="an-attribution">
              <div>
                <div className="an-attribution-name">The Visentix Privacy Desk</div>
                <div className="an-attribution-role">Intelligence authored in house voice</div>
              </div>
              <div className="an-reviewer-slot">
                <div className="slot-label">Expert Reviewer</div>
                <div className="slot-value">Pending SME review</div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="an-footer">
        <IntelligenceMark />
      </div>
    </div>
  );
}
