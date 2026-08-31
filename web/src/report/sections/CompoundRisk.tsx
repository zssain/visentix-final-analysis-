import { ScoreCell }      from "../../components/ScoreCell";
import { scoreBandColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";

export function CompoundRisk({ content }: { content: ReportSection["content"] }) {
  const compoundScore = content.compound_score as number | undefined;
  const vciScore      = content.vci_score as number | undefined;
  const lineage = (content.lineage as { risk_scores?: Record<string, number>; contributors?: { domain?: string; code?: string; score?: number }[]; drivers?: { domain?: string; code?: string; score?: number }[]; cm?: number; reason?: string } | undefined) ?? {};
  const labels: Record<string, string> = { regulatory: "Regulatory Exposure", benchmark: "Benchmark Deviation", disclosure: "Disclosure Maturity Gap", ai: "AI Transparency Gap" };
  const current = Object.entries(lineage.risk_scores ?? {}).map(([name, score]) => ({ name: labels[name] ?? name, score }));
  const legacy = (lineage.contributors ?? lineage.drivers ?? []).map(d => ({ name: labels[d.code ?? d.domain ?? ""] ?? (d.code ?? d.domain ?? "Not recorded"), score: d.score }));
  const dimensions = (current.length ? current : legacy).sort((a, b) => (Number(b.score ?? -1) - Number(a.score ?? -1)) || a.name.localeCompare(b.name));
  const snapshotId    = (content.snapshot_id as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const frozenDate    = (content.date        as string | undefined) ?? "—";
  const cohortSize    = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate    = (content.cohort_date as string | undefined) ?? "—";

  return (
    <div data-testid="section-7" className="report-section">
      <h2>7. Compound Risk Analysis</h2>

      {/* Headline */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        {typeof compoundScore === "number" ? <ScoreCell
          value={compoundScore}
          formulaId="F-008"
          formulaDesc={(content.formula_descs as Record<string, string> | undefined)?.["F-008"] ?? ""}
          inputs={[
            { label: "Regulatory", type: "regulator" },
            { label: "Disclosure", type: "clause" },
            { label: "Enforcement", type: "regulator" },
          ]}
          /* VCI comes from the payload only — never invented (Hard Rule 3/7).
             Missing → ScoreCell's conservative 0 default, not a flattering 75. */
          vci={vciScore}
          snapshotId={snapshotId}
          frozenDate={frozenDate}
          cohortSize={cohortSize}
          cohortDate={cohortDate}
          size="lg"
        /> : <span style={{ color: "var(--text-muted)" }}>Compound exposure not recorded</span>}
        <span style={{ fontSize: "0.82rem", color: "var(--text-muted)", fontStyle: "italic" }}>
          Compound Risk Score — click to view lineage
        </span>
      </div>

      {/* Dimension breakdown */}
      {dimensions.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {dimensions.map((d, i) => (
            <div key={i}>
              <div style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                marginBottom: 4,
              }}>
                <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--navy)" }}>{d.name}</span>
                <span style={{
                  fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                  fontSize: "0.82rem", fontWeight: 700, color: scoreBandColor(d.score ?? 0),
                }}>
                  {typeof d.score === "number" ? d.score.toFixed(1) : "Not recorded"}
                </span>
              </div>
              <div style={{ height: 5, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{
                  height: "100%", width: `${d.score ?? 0}%`,
                  background: scoreBandColor(d.score ?? 0), borderRadius: 3,
                  transition: "width 0.4s ease",
                }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{
          background: "var(--soft-white)", border: "1px solid var(--border)",
          borderRadius: "var(--radius)", padding: "12px 16px",
          fontSize: "0.85rem", color: "var(--text-muted)",
        }}>
          Compound risk dimension breakdown will appear once all formula inputs are available.
        </div>
      )}

      {typeof lineage.cm === "number" && <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
        Correlation multiplier: {lineage.cm.toFixed(2)}. The multiplier reflects how related exposure signals can reinforce one another.
      </p>}

      <div style={{ marginTop: 14 }}>
      </div>
    </div>
  );
}
