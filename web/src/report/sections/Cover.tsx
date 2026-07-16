import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { maturityBand } from "../../lib/scoreBands";
import type { ReportSection } from "../types";

export function Cover({ content }: { content: ReportSection["content"] }) {
  const domain    = content.org_domain    as string | undefined;
  const industry  = content.org_industry  as string | undefined;
  const size      = content.org_size      as string | undefined;
  const geography = content.org_geography as string | undefined;
  const snapshotId = (content.snapshot_id as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const frozenDate = (content.date as string | undefined) ?? "—";
  const formulaVer = (content.formula_version as string | undefined) ?? "v1.0";
  const isDraft    = (content.is_draft as boolean | undefined) ?? false;

  const hasMeta = domain || industry || size || geography;

  return (
    <div data-testid="section-1" className="report-section cover-section">
      {/* [MOCK M-09] Snapshot ID and date read from content — real: report_snapshot.id from API */}
      <ProvenanceRibbon
        snapshotId={snapshotId}
        formulaVersion={formulaVer}
        frozenDate={frozenDate}
        status={isDraft ? "draft" : "approved"}
      />

      {/* Gold hairline rule */}
      <div className="cover-hairline" aria-hidden="true" />

      {/* Org name — display font */}
      <h1 className="cover-org-name">{content.organization as string}</h1>

      {/* Meta row */}
      {hasMeta && (
        <div className="cover-meta">
          {domain    && <span><b>Domain</b> {domain}</span>}
          {industry  && <span style={{ textTransform: "capitalize" }}><b>Industry</b> {industry}</span>}
          {size      && <span style={{ textTransform: "capitalize" }}><b>Size</b> {size}</span>}
          {geography && <span><b>Geography</b> {geography}</span>}
        </div>
      )}

      <p className="cover-title">{content.report_title as string}</p>

      {/* Score + maturity band */}
      <div className="cover-score-block">
        <div className="cover-score-num">{(content.overall_score as number)?.toFixed(1)}</div>
        <div className="cover-score-label">Overall Privacy Intelligence Score</div>
        <span style={{
          display: "inline-block",
          marginTop: 6,
          padding: "2px 14px",
          borderRadius: 4,
          fontSize: "0.82rem",
          fontWeight: 700,
          border: "1.5px solid var(--navy)",
          color: "var(--navy)",
        }}>
          {maturityBand((content.overall_score as number) ?? 0)}
        </span>
      </div>

      {/* Scope & limitations */}
      <div className="cover-scope-block">
        <div className="cover-scope-label">Scope & Limitations</div>
        <p className="cover-scope-text">
          This assessment evaluates the organisation&apos;s public privacy notice against a cohort of peer
          organisations. It quantifies disclosure maturity, regulatory exposure likelihood, and transparency.
          It does not constitute legal advice, a compliance determination, or a verdict on the organisation&apos;s
          practices.
        </p>
      </div>

      <div className="cover-footer">
        <IntelligenceMark />
      </div>
    </div>
  );
}
