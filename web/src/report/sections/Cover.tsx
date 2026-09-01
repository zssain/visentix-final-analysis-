import { ScoreDial } from "../ScoreDial";
import type { ReportSection } from "../types";
import { humanize } from "../../lib/labels";

/**
 * Cover — editorial first page: eyebrow, Fraunces org name, meta row,
 * score dial (Workstream B item 1), scope & limitations, mark.
 * The provenance ribbon renders ONCE, in Traceability — not here and not above
 * the cover (audit 2026-07-16 removed a duplicate here; 2026-09-01 moved the
 * survivor to the appendix, where the machinery it names already lives).
 */
export function Cover({ content }: { content: ReportSection["content"] }) {
  const orgName   = content.organization  as string | undefined;
  const domain    = content.org_domain    as string | undefined;
  const industry  = content.org_industry  as string | undefined;
  const size      = content.org_size      as string | undefined;
  const geography = content.org_geography as string | undefined;
  const vciScore  = content.vci_score     as number | undefined;
  const scope = (content.assessment_scope as Record<string, { value?: unknown; provenance?: string }> | undefined) ?? {};
  const scopeLabels: Record<string, string> = {
    source: "Assessed source", notice_version: "Notice version", capture_date: "Capture date",
    effective_date: "Effective date", intake_method: "Intake method", organization_name: "Organization",
    organization_size: "Organization size", public_private: "Ownership type", geography: "Geography",
    industry: "Industry",
    cohort_definition: "Peer cohort", state_footprint: "State footprint",
    selected_laws: "Selected legal scope", data_categories: "Data categories",
    business_practices: "Business practices",
  };
  const displayValue = (value: unknown) => Array.isArray(value) ? value.join(", ") : value === null || value === undefined || value === "" ? "Not recorded" : String(value);

  const hasMeta = domain || industry || size || geography;

  return (
    <div data-testid="section-1" className="report-section cover-section">
      {/* Gold hairline rule */}
      <div className="cover-hairline" aria-hidden="true" />

      {/* Eyebrow — the report type, quiet small caps */}
      <div className="cover-eyebrow">{(content.report_title as string) ?? "Privacy Intelligence Assessment"}</div>

      {/* Org name — display font */}
      <h1 className="cover-org-name">{orgName}</h1>

      {/* Who this is for, in a sentence. The cover named the organisation and
          the report type but never said the two were related — a reader handed
          this second-hand saw a company name above a gauge and had to infer
          that the document was ABOUT that company. Composed from the payload,
          so it asserts nothing the snapshot does not already carry. */}
      {orgName && (
        <p className="cover-lede">
          A privacy intelligence assessment prepared for {orgName}, based on its
          published privacy notice.
        </p>
      )}

      {/* Meta row */}
      {hasMeta && (
        <div className="cover-meta">
          {domain    && <span><b>Domain</b> {domain}</span>}
          {industry  && <span className="capitalize"><b>Industry</b> {industry}</span>}
          {size      && <span className="capitalize"><b>Size</b> {size}</span>}
          {geography && <span><b>Geography</b> {geography}</span>}
        </div>
      )}

      {/* Score dial — band-colored arc, maturity band, VCI (when real) */}
      <div className="cover-dial-wrap">
        <ScoreDial score={(content.overall_score as number) ?? 0} vci={vciScore} />
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

      {Object.keys(scope).length > 0 && <div className="cover-scope-block" data-testid="assessment-scope">
        <div className="cover-scope-label">Assessment Scope</div>
        <table className="w-full border-collapse text-xs">
          <tbody>{Object.entries(scopeLabels).map(([key, label]) => {
            const item = scope[key] ?? {};
            return <tr key={key}><th className="px-1.5 py-1 text-left">{label}</th><td className="px-1.5 py-1">{displayValue(item.value)}</td><td className="px-1.5 py-1 text-muted-foreground">{humanize(item.provenance ?? "not recorded")}</td></tr>;
          })}</tbody>
        </table>
        <p className="cover-scope-text">Unconfirmed values are shown as assumptions; legacy assessments are not back-filled.</p>
      </div>}

      <div className="cover-footer">
      </div>
    </div>
  );
}
