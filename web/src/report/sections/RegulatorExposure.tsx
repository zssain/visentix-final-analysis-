import { IntelligenceMark } from "../../components/IntelligenceMark";
import { ScoreCell }    from "../../components/ScoreCell";
import { domainLabel } from "../../lib/domainLabels";
import type { ReportSection } from "../types";

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

function cellColor(cell: HeatmapCell): string {
  if (!(cell.evidenced ?? cell.clause_density > 0)) return "repeating-linear-gradient(135deg, #f4f5f7, #f4f5f7 4px, #e3e6ea 4px, #e3e6ea 8px)";
  if (cell.intensity >= 70) return "var(--red)";
  if (cell.intensity >= 45) return "var(--gold)";
  return "var(--teal)";
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

  return (
    <div data-testid="section-5" className="report-section">
      <h2>5. Regulator Exposure</h2>

      {/* Headline score */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
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
        /> : <span style={{ color: "var(--text-muted)" }}>Exposure score not recorded</span>}
        <span className={`badge badge-${tier.toLowerCase()}`}>{tier}</span>
        <span style={{ fontSize: "0.82rem", color: "var(--text-muted)", fontStyle: "italic" }}>
          Click score to view lineage
        </span>
      </div>

      {regulators.length > 0 ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--soft-white)" }}>
              <th style={th}>Regulator</th>
              {(regulators[0]?.cells ?? []).map(cell => <th style={th} key={cell.domain}>{domainLabel(cell.domain)}</th>)}
            </tr>
          </thead>
          <tbody>
            {regulators.map((r) => (
              <tr key={r.regulator_id}>
                <td style={{ ...td, fontWeight: 600, color: "var(--navy)" }}>{r.regulator_name}<div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{r.jurisdiction}</div></td>
                {r.cells.map(cell => <td key={cell.domain} style={{ ...td, textAlign: "center", background: cellColor(cell), color: (cell.evidenced ?? cell.clause_density > 0) ? "white" : "var(--text-muted)" }}>
                  {(cell.evidenced ?? cell.clause_density > 0) ? cell.intensity.toFixed(1) : "—"}
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
      {regulators.length > 0 && <div style={{ marginTop: 8, fontSize: "0.75rem", color: "var(--text-muted)" }}>
        Hatched cells are regulator baselines with no clause from your notice mapped to that domain. {regulators.flatMap(r => r.cells).filter(c => c.evidenced ?? c.clause_density > 0).length} of {regulators.flatMap(r => r.cells).length} cells are backed by notice-clause evidence.
      </div>}
      {/* DDR-007: every report section carries the mark */}
      <div style={{ marginTop: 12 }}><IntelligenceMark /></div>
    </div>
  );
}

const th: React.CSSProperties = {
  border: "1px solid var(--border)", padding: "9px 12px", textAlign: "left",
  fontWeight: 700, fontSize: "0.72rem", textTransform: "uppercase",
  letterSpacing: "0.07em", color: "var(--text-secondary)",
};
const td: React.CSSProperties = { border: "1px solid var(--border)", padding: "10px 12px", fontSize: "0.88rem" };
