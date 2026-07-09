import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { VciBadge } from "../VciBadge";
import { ScoreCell } from "../../components/ScoreCell";
import { InfoButton } from "../explain";
import { scoreBandColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";

const FID_TO_FKEY: Record<string, string> = {
  "F-002": "f002", "F-005": "f005", "F-006": "f006",
  "F-007": "f007", "F-008": "f008", "F-010": "f010",
};

// Formula descriptions — static reference text (not data-bearing)
const FORMULA_DESCS: Record<string, string> = {
  "F-002": "Regulatory Exposure — jurisdiction importance weighted by regulator priority across each domain.",
  "F-005": "Disclosure Maturity — required disclosure elements present versus the master checklist.",
  "F-006": "Transparency — readability, clarity, and completeness indicators.",
  "F-007": "AI Transparency — how specifically the notice addresses automated decision-making.",
  "F-008": "Compound Risk — regulatory, disclosure, and enforcement dimensions combined.",
  "F-010": "Overall Intelligence — weighted combination of all risk dimensions.",
};

export function RiskDashboard({ content }: { content: ReportSection["content"] }) {
  const snapshotId   = (content.snapshot_id  as string | undefined) ?? "S-0000";
  const frozenDate   = (content.date         as string | undefined) ?? "—";
  const cohortSize   = (content.cohort_size  as number | undefined) ?? 0;
  const cohortDate   = (content.cohort_date  as string | undefined) ?? "—";
  const vci          = (content.vci_score    as number | undefined) ?? 0;
  const assessmentId = (content.assessment_id as string | undefined) ?? "";

  const metrics = [
    { name: "Overall",        value: content.overall_intelligence as number, fid: "F-010" },
    { name: "Regulatory",     value: content.regulatory_exposure  as number, fid: "F-002" },
    { name: "Disclosure",     value: content.disclosure_maturity  as number, fid: "F-005" },
    { name: "Transparency",   value: content.transparency         as number, fid: "F-006" },
    { name: "AI Transparency",value: content.ai_transparency      as number, fid: "F-007" },
    { name: "Compound Risk",  value: content.compound_risk        as number, fid: "F-008" },
  ];

  return (
    <div data-testid="section-3" className="report-section">
      <h2>3. Risk Dashboard</h2>

      {/* Chart */}
      <div style={{ width: "100%", height: 280 }} className="chart-container">
        <ResponsiveContainer>
          <BarChart data={metrics} layout="vertical" margin={{ left: 110, right: 24 }}>
            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={108} tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(v: any) => [`${Number(v)?.toFixed(1)}`, "Score"]}
              contentStyle={{ fontSize: "0.82rem", borderRadius: 6 }}
            />
            <Bar dataKey="value" isAnimationActive={false} radius={[0, 4, 4, 0]}>
              {metrics.map((m, i) => (
                <Cell key={i} fill={scoreBandColor(m.value ?? 0)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Score cells with lineage affordance */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 1,
        background: "var(--border)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        overflow: "hidden",
        marginTop: 16,
      }}>
        {metrics.map(m => (
          <div key={m.name} style={{
            background: "var(--bg-card)",
            padding: "12px 14px",
          }}>
            <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4, display: "flex", alignItems: "center", gap: 4 }}>
              {m.name}
              {assessmentId && (
                <InfoButton assessmentId={assessmentId} elementType="score" elementKey={FID_TO_FKEY[m.fid] ?? m.fid} label={m.name} />
              )}
            </div>
            <ScoreCell
              value={m.value ?? 0}
              formulaId={m.fid}
              formulaDesc={FORMULA_DESCS[m.fid] ?? "Score computed by the Visentix formula engine."}
              inputs={[
                { label: "Notice", type: "clause" },
                { label: "Regulator", type: "regulator" },
                { label: `n=${cohortSize}`, type: "cohort" },
              ]}
              vci={vci}
              snapshotId={snapshotId}
              frozenDate={frozenDate}
              cohortSize={cohortSize}
              cohortDate={cohortDate}
              size="md"
            />
          </div>
        ))}
      </div>

      <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>VCI {vci?.toFixed(1)}</span>
        <VciBadge label={content.vci_label as string} />
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontStyle: "italic" }}>
          Click any score to view its lineage
        </span>
      </div>
    </div>
  );
}
