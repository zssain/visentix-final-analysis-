import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { VciBadge } from "../VciBadge";
import { ScoreCell } from "../../components/ScoreCell";
import type { ReportSection } from "../types";

// Formula descriptions (plain English only — no math)
// [MOCK M-10] Real descriptions from formula_version.description column in Supabase
const FORMULA_DESCS: Record<string, string> = {
  "F-002": "Multiplies jurisdiction importance by regulator priority and disclosure severity across each domain.",
  "F-005": "Scores how many required disclosure elements are present versus the master checklist.",
  "F-006": "Combines readability, clarity, and completeness indicators into a composite transparency figure.",
  "F-007": "Evaluates how specifically the notice addresses automated and AI-driven decision-making.",
  "F-008": "Blends regulatory, disclosure, and enforcement dimensions into a single compound risk indicator.",
  "F-010": "Weighted combination of all six risk dimensions to produce the overall privacy intelligence score.",
};

function tierColor(score: number): string {
  if (score >= 70) return "#F87171"; // red — high exposure (only legitimate use)
  if (score >= 45) return "#C8A46A"; // gold — elevated
  return "#55C7B3";                  // teal — lower exposure
}

export function RiskDashboard({ content }: { content: ReportSection["content"] }) {
  const snapshotId = (content.snapshot_id as string | undefined) ?? "S-0000";
  const frozenDate = (content.date        as string | undefined) ?? "—";
  const cohortSize = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate = (content.cohort_date as string | undefined) ?? "—";
  const vci        = (content.vci_score   as number | undefined) ?? 0;

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
                <Cell key={i} fill={tierColor(m.value ?? 0)} />
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
            <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>
              {m.name}
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
