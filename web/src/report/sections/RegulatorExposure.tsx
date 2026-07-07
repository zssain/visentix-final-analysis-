import { CodexTooltip } from "../../components/CodexTooltip";
import { ScoreCell }    from "../../components/ScoreCell";
import type { ReportSection } from "../types";

interface RegulatorRow {
  regulator: string;
  jurisdiction: string;
  tier: string;
  score: number;
  finding_codes?: string[];
}

function tierColor(tier: string): string {
  return { high: "var(--red)", elevated: "var(--gold)", moderate: "var(--exec-blue)", low: "var(--teal)" }[tier.toLowerCase()] ?? "var(--border)";
}

export function RegulatorExposure({ content }: { content: ReportSection["content"] }) {
  const regulatoryScore = (content.regulatory_score as number | undefined) ?? 0;
  const tier            = (content.tier as string | undefined) ?? "—";
  const regulators      = (content.regulators as RegulatorRow[] | undefined) ?? [];
  const snapshotId      = (content.snapshot_id as string | undefined) ?? "S-0000";
  const frozenDate      = (content.date        as string | undefined) ?? "—";
  const cohortSize      = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate      = (content.cohort_date as string | undefined) ?? "—";

  return (
    <div data-testid="section-5" className="report-section">
      <h2>5. Regulator Exposure</h2>

      {/* Headline score */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <ScoreCell
          value={regulatoryScore}
          formulaId="F-002"
          formulaDesc="Weights jurisdiction importance against regulator priority and disclosure severity per domain."
          inputs={[
            { label: "Regulator", type: "regulator" },
            { label: "Jurisdiction", type: "jurisdiction" },
            { label: "Notice", type: "clause" },
          ]}
          vci={75}
          snapshotId={snapshotId}
          frozenDate={frozenDate}
          cohortSize={cohortSize}
          cohortDate={cohortDate}
          size="lg"
        />
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
              <th style={th}>Jurisdiction</th>
              <th style={th}>Tier</th>
              <th style={th}>Exposure Score</th>
              <th style={th}>Finding Codes</th>
            </tr>
          </thead>
          <tbody>
            {regulators.map((r, i) => (
              <tr key={i}>
                <td style={{ ...td, fontWeight: 600, color: "var(--navy)" }}>{r.regulator}</td>
                <td style={td}>{r.jurisdiction}</td>
                <td style={td}>
                  <span style={{
                    display: "inline-block", width: 10, height: 10,
                    borderRadius: "50%", background: tierColor(r.tier),
                    marginRight: 6, verticalAlign: "middle",
                  }} />
                  {r.tier}
                </td>
                <td style={{ ...td, fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums" }}>
                  {r.score?.toFixed(1)}
                </td>
                <td style={td}>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {(r.finding_codes ?? []).map(code => (
                      <CodexTooltip key={code} code={code} />
                    ))}
                    {(!r.finding_codes || r.finding_codes.length === 0) && (
                      <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>—</span>
                    )}
                  </div>
                </td>
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
    </div>
  );
}

const th: React.CSSProperties = {
  border: "1px solid var(--border)", padding: "9px 12px", textAlign: "left",
  fontWeight: 700, fontSize: "0.72rem", textTransform: "uppercase",
  letterSpacing: "0.07em", color: "var(--text-secondary)",
};
const td: React.CSSProperties = { border: "1px solid var(--border)", padding: "10px 12px", fontSize: "0.88rem" };
