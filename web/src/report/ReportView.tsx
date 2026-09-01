/**
 * ReportView — renders all 12 sections from the payload.
 * This SAME component drives both the portal view and the Playwright PDF.
 * It displays data only — no client-side score recomputation.
 *
 * DDR-001: draft_banner replaced by the provenance ribbon + diagonal watermark.
 * The ribbon renders ONCE, in Traceability, where the rest of the machinery
 * lives. It used to open the report as well — so a reader met a snapshot ID and
 * a formula version before they met the organisation the report is about.
 */
import { useEffect, useRef, useState } from "react";
import type { ReportPayload } from "./types";
import { api } from "../lib/api";
import { useExplain } from "./explain/ExplainContext";
import "./explain/explain.css";
import { Cover }              from "./sections/Cover";
import { ExecutiveSummary }   from "./sections/ExecutiveSummary";
import { RiskDashboard }      from "./sections/RiskDashboard";
import { BenchmarkIntelligence } from "./sections/BenchmarkIntelligence";
import { RegulatorExposure }  from "./sections/RegulatorExposure";
import { FindingsTable }      from "./sections/FindingsTable";
import { CompoundRisk }       from "./sections/CompoundRisk";
import { BenchmarkLanguage }  from "./sections/BenchmarkLanguage";
import { Recommendations }    from "./sections/Recommendations";
import { RiskReduction }      from "./sections/RiskReduction";
import { Traceability }       from "./sections/Traceability";
import { TrendPanel }         from "./sections/TrendPanel";
import { Disclosure }         from "./sections/Disclosure";
import { REPORT_PARTS }       from "./sectionGroups";
import { ReportContents }     from "./ReportContents";
import { ReportRail, partAnchor } from "./ReportRail";
import { NestedSectionContext } from "./SectionHeading";
import "./report.css";

const SECTION_MAP: Record<number, React.FC<{ content: Record<string, unknown> }>> = {
  1: Cover,
  2: ExecutiveSummary,
  3: RiskDashboard,
  4: BenchmarkIntelligence,
  5: RegulatorExposure,
  6: FindingsTable,
  7: CompoundRisk,
  8: BenchmarkLanguage,
  9: Recommendations,
  10: RiskReduction,
  11: Traceability,
  12: TrendPanel,
};

interface ReportViewProps { report: ReportPayload; }

export function ReportView({ report }: ReportViewProps) {
  const isDraft = !!report.draft_banner;
  const { prefetch } = useExplain();
  const contentsRef = useRef<HTMLElement>(null);

  // M-10: real plain-English formula descriptions from formula_version.description
  // (14/14 populated). Threaded into every section so lineage drawers stop using
  // hardcoded copy. Empty until loaded → sections fall back to honest absence.
  const [formulaDescs, setFormulaDescs] = useState<Record<string, string>>({});
  useEffect(() => {
    api.get("/api/formulas").then((res: { formulas?: Record<string, { description?: string }> }) => {
      const map: Record<string, string> = {};
      for (const [fid, v] of Object.entries(res.formulas ?? {})) {
        if (v?.description) map[fid] = v.description;
      }
      setFormulaDescs(map);
    }).catch(() => { /* backend down → sections render honest absence */ });
  }, []);

  // Prefetch all explain envelopes when the report loads
  useEffect(() => {
    if (report.assessment_id) {
      prefetch(report.assessment_id);
    }
  }, [report.assessment_id, prefetch]);

  // M-09: prefer the authoritative stored snapshot id + frozen-at threaded
  // from the report_snapshot row; fall back to the Cover section, then honest
  // absence — never a plausible-looking fake ID (Hard Rule 7).
  const coverContent = report.sections.find(s => s.number === 1)?.content ?? {};
  const snapshotId   = report._snapshot_id
    ?? (coverContent.snapshot_id as string | undefined)
    ?? "—";
  const formulaVer   = coverContent.formula_version as string | undefined;

  // Parts whose blocks are actually in this payload. Computed once so the
  // contents map, the rail, and the rendered parts cannot disagree.
  const presentParts = REPORT_PARTS.filter(part =>
    part.blocks.some(n => {
      const sec = report.sections.find(s => s.number === n);
      return !!sec && !!SECTION_MAP[sec.number];
    })
  );

  return (
    <div className="report-shell">
    <div
      className={`report-container ${isDraft ? "draft-watermark-wrap" : ""}`}
      data-testid="report-view"
    >
      {/* The reader's map, built from the parts that actually rendered — it can
          never list a section this snapshot does not carry.

          The cover is included even though it prints no part heading of its
          own. Excluding it made the index open at "2. Executive Summary",
          which tells a reader either that part 1 is missing or that the index
          is wrong. A contents list numbers the DOCUMENT, not the subset of it
          that happens to carry a heading. */}
      <ReportContents parts={presentParts} innerRef={contentsRef} />

      {/* Presented as six parts + an appendix (see sectionGroups.ts). The payload
          is untouched — each part simply renders the blocks it groups, in order,
          and a part with no blocks present is skipped rather than left empty. */}
      {REPORT_PARTS.map((part) => {
        const blocks = part.blocks
          .map(n => report.sections.find(s => s.number === n))
          .filter((s): s is NonNullable<typeof s> => !!s && !!SECTION_MAP[s.number]);
        if (blocks.length === 0) return null;

        const headed = part.headed !== false;
        const anchor = partAnchor(part);
        // One block under a part heading would otherwise print the same name
        // twice; several blocks each need naming.
        const mode = !headed ? "own" : blocks.length > 1 ? "sub" : "hidden";
        const body = blocks.map((section) => {
          const Component = SECTION_MAP[section.number]!;
          // Thread snapshot context into every section's content
          const enrichedContent = {
            ...section.content,
            snapshot_id:   snapshotId,
            is_draft:      isDraft,
            formula_descs: formulaDescs,
            cohort_size:   report.cohort_size,
            cohort_date:   report.cohort_date,
            date:          report.generated_date,
            // The cover carries the formula version; Traceability is where it is
            // labelled. A block that already has its own wins — this only fills
            // a gap, it never overwrites what the snapshot froze.
            formula_version: section.content.formula_version ?? formulaVer,
            assessment_id: report.assessment_id,
          };
          return (
            <div key={section.number} id={`section-${section.number}`}>
              <Component content={enrichedContent} />
            </div>
          );
        });

        return (
          <div key={part.title} id={anchor} className="report-page-break report-part">
            {headed && (
              /* One heading shape for every part, so the reader learns it once:
                 the number as a standing marker, the title, then a plain-English
                 statement of the question the part answers. The number used to
                 be glued to the title as "3. Where You Stand", which reads as
                 part of the sentence rather than as a position in a sequence. */
              <header className="report-part-head">
                <span className="report-part-num" aria-hidden="true">
                  {part.n ?? "·"}
                </span>
                <div className="report-part-titles">
                  <h2>{part.title}</h2>
                  {part.lede && <p className="report-part-lede">{part.lede}</p>}
                </div>
              </header>
            )}
            <NestedSectionContext.Provider value={mode}>
              {body}
            </NestedSectionContext.Provider>
          </div>
        );
      })}

      {/* Closing bookend (revised DDR-007): one Disclosure where the reader
          finishes, paired with the scope statement where they started. */}
      <div className="report-page-break">
        <Disclosure cohortSize={report.cohort_size} cohortDate={report.cohort_date} />
      </div>

      <div className="report-footer">
        Generated by Visentix Privacy Intelligence Platform
        &nbsp;·&nbsp;{report.generated_date}
        &nbsp;·&nbsp;Assessment: {report.assessment_id?.slice(0, 12)}
        &nbsp;·&nbsp;Cohort: n={report.cohort_size} as of {report.cohort_date}
      </div>
    </div>

    {/* Pinned "on this page", revealed once the contents card scrolls away. */}
    <ReportRail parts={presentParts} revealAfter={contentsRef} />
    </div>
  );
}
