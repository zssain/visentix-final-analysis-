import { ScoreCell }    from "../../components/ScoreCell";
import { domainLabel } from "../../lib/domainLabels";
import { scoreBandColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { cn } from "@/lib/utils";

interface HeatmapCell {
  domain: string;
  intensity: number;
  clause_density: number;
  evidenced?: boolean;
}
interface RegulatorRow {
  regulator_id: string;
  regulator_name: string;
  jurisdiction: string;
  cells: HeatmapCell[];
}

/* Hatch marks a cell with no evidence. Token-built so it inverts with the theme
   — a light hatch on a dark card would read as a filled cell, i.e. as evidence
   that is not there. */
const HATCH = "repeating-linear-gradient(135deg, var(--muted), var(--muted) 4px, var(--border) 4px, var(--border) 8px)";

function isEvidenced(cell: HeatmapCell): boolean {
  return cell.evidenced ?? cell.clause_density > 0;
}

/** Exposure intensity is a standing judgement — it uses the ONE standing scale,
 *  never locally redefined colors or a second copy of the band thresholds
 *  (design-system §2; the previous local copy of 70/45 + teal/gold has been
 *  removed so a threshold or palette change can never diverge here). */
function cellColor(cell: HeatmapCell): string {
  return isEvidenced(cell) ? scoreBandColor(cell.intensity) : HATCH;
}

export function RegulatorExposure({ content }: { content: ReportSection["content"] }) {
  const regulatoryScore = content.regulatory_score as number | undefined;
  const vciScore        = content.vci_score as number | undefined; // real VCI or honest absence — never a fabricated 75 (DATA-003)
  const tier            = (content.tier as string | undefined) ?? "—";
  const regulators      = (content.heatmap as RegulatorRow[] | undefined) ?? [];
  const snapshotId      = (content.snapshot_id as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const frozenDate      = (content.date        as string | undefined) ?? "—";
  const cohortSize      = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate      = (content.cohort_date as string | undefined) ?? "—";

  const allCells      = regulators.flatMap(r => r.cells);
  const evidencedCells = allCells.filter(isEvidenced).length;
  const domainCount    = regulators[0]?.cells.length ?? 0;

  return (
    <div data-testid="section-5" className="report-section">
      <SectionHeading n={5} title="Regulator Exposure" />

      {/* Headline score */}
      <div className="flex items-baseline gap-3 mb-4 flex-wrap">
        {typeof regulatoryScore === "number" ? <ScoreCell
          value={regulatoryScore}
          formulaId="F-002"
          formulaDesc="Weights jurisdiction importance against regulator priority and disclosure severity per domain."
          inputs={[
            { label: "Regulator", type: "regulator" },
            { label: "Jurisdiction", type: "jurisdiction" },
            { label: "Notice", type: "clause" },
          ]}
          vci={vciScore}
          snapshotId={snapshotId}
          frozenDate={frozenDate}
          cohortSize={cohortSize}
          cohortDate={cohortDate}
          size="lg"
        /> : <span className="text-muted-foreground">Exposure score not recorded</span>}
        <span className={`badge badge-${tier.toLowerCase()}`}>{tier}</span>
        <span className="text-sm text-muted-foreground italic">
          Click score to view lineage
        </span>
      </div>

      {regulators.length > 0 && evidencedCells === 0 ? (
        /* A grid in which NOTHING is evidenced is not a heatmap — it is a wall of
           dashes that reads as a broken product. The honest thing is to say what
           happened and why, and not spend a page on an empty lattice (DDR-011).
           The underlying cells stay in the snapshot and in Traceability. */
        <div style={{
          padding: "14px 16px", background: "var(--soft-white)",
          border: "1px solid var(--border)", borderRadius: "var(--radius)",
          fontSize: "0.85rem", color: "var(--text-secondary)",
        }}>
          <strong>No regulator-domain evidence in this assessment.</strong>
          <div className="mt-1.5 text-muted-foreground">
            None of this notice's clauses mapped to a domain that the {regulators.length} tracked
            regulators publish expectations for, so every cell of the {regulators.length}×{domainCount} grid
            would be blank. The grid is withheld rather than shown empty. The regulator
            baselines and the unmapped cells remain in the frozen snapshot.
          </div>
        </div>
      ) : regulators.length > 0 ? (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-muted/40">
              <th style={th}>Regulator</th>
              {(regulators[0]?.cells ?? []).map(cell => <th style={th} key={cell.domain}>{domainLabel(cell.domain)}</th>)}
            </tr>
          </thead>
          <tbody>
            {regulators.map((r) => (
              <tr key={r.regulator_id}>
                <td style={td} className="font-semibold">{r.regulator_name}<div className="text-[11px] text-muted-foreground">{r.jurisdiction}</div></td>
                {r.cells.map(cell => <td
                  key={cell.domain}
                  style={{ ...td, background: cellColor(cell) }}
                  className={cn("text-center", isEvidenced(cell) ? "text-[var(--primary-foreground)]" : "text-muted-foreground")}
                >
                  {isEvidenced(cell) ? cell.intensity.toFixed(1) : "—"}
                </td>)}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{
          padding: "14px 16px", background: "var(--soft-white)",
          border: "1px solid var(--border)", borderRadius: "var(--radius)",
          fontSize: "0.85rem", color: "var(--text-muted)",
        }}>
          Regulatory heatmap will appear here once regulator data is populated.
        </div>
      )}
      {regulators.length > 0 && evidencedCells > 0 && <div className="mt-2 text-xs text-muted-foreground">
        Hatched cells are regulator baselines with no clause from your notice mapped to that domain.
        {" "}{evidencedCells} of {allCells.length} cells are backed by notice-clause evidence.
      </div>}
    </div>
  );
}

const th: React.CSSProperties = {
  border: "1px solid var(--border)", padding: "9px 12px", textAlign: "left",
  fontWeight: 700, fontSize: "0.72rem", textTransform: "uppercase",
  letterSpacing: "0.07em", color: "var(--text-secondary)",
};
const td: React.CSSProperties = { border: "1px solid var(--border)", padding: "10px 12px", fontSize: "0.88rem" };
