import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { VciBadge } from "../VciBadge";
import { ScoreCell } from "../../components/ScoreCell";
import { InfoButton } from "../explain";
import { bandColor, metricPolarity } from "../../lib/scoreBands";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";

const FID_TO_FKEY: Record<string, string> = {
  "F-002": "f002", "F-005": "f005", "F-006": "f006",
  "F-007": "f007", "F-008": "f008", "F-010": "f010",
};

// Formula descriptions — static reference text (not data-bearing)
export function RiskDashboard({ content }: { content: ReportSection["content"] }) {
  // M-10: plain-English descriptions come from formula_version.description
  // (threaded by ReportView); honest absence when unavailable.
  const formulaDescs = (content.formula_descs as Record<string, string> | undefined) ?? {};
  const snapshotId   = (content.snapshot_id  as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const frozenDate   = (content.date         as string | undefined) ?? "—";
  const cohortSize   = (content.cohort_size  as number | undefined) ?? 0;
  const cohortDate   = (content.cohort_date  as string | undefined) ?? "—";
  const vci          = content.vci_score as number | undefined;
  const assessmentId = (content.assessment_id as string | undefined) ?? "";

  // One registry drives color and explanatory direction for every consumer.
  const metrics = [
    { name: "Overall", value: content.overall_intelligence as number | undefined, fid: "F-010", direction: "Maturity — higher is better" },
    { name: "Regulatory", value: content.regulatory_exposure as number | undefined, fid: "F-002", direction: "Exposure — lower is better" },
    { name: "Disclosure", value: content.disclosure_maturity as number | undefined, fid: "F-005", direction: "Maturity — higher is better" },
    { name: "Transparency", value: content.transparency as number | undefined, fid: "F-006", direction: "Maturity — higher is better" },
    { name: "AI Transparency", value: content.ai_transparency as number | undefined, fid: "F-007", direction: "Maturity — higher is better" },
    { name: "Compound Risk", value: content.compound_risk as number | undefined, fid: "F-008", direction: "Exposure — lower is better" },
  ];
  const chartMetrics = metrics
    .filter(m => typeof m.value === "number")
    .map(m => ({ ...m, value: m.value as number }));
  const quality = content.extraction_quality as { status?: string } | undefined;

  return (
    <div data-testid="section-3" className="report-section">
      <SectionHeading n={3} title="Risk Dashboard" />

      {/* Chart */}
      <div className="chart-container h-70 w-full">
        <ResponsiveContainer>
          <BarChart data={chartMetrics} layout="vertical" margin={{ left: 110, right: 24 }}>
            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={108} tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(v) => [`${Number(v).toFixed(1)}`, "Score"]}
              contentStyle={{ fontSize: "0.82rem", borderRadius: 6 }}
            />
            <Bar dataKey="value" isAnimationActive={false} radius={[0, 4, 4, 0]}>
              {chartMetrics.map((m, i) => (
                /* Polarity-aware: maturity metrics (Overall, Disclosure,
                   Transparency, AI) color by the maturity scale; exposure
                   metrics (Regulatory, Compound) by the exposure scale. */
                <Cell key={i} fill={bandColor(m.value ?? 0, metricPolarity(m.fid))} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {(quality?.status === "mismatch" || quality?.status === "insufficient") && <div className="mt-2.5 rounded-lg border border-[var(--provisional)] px-3 py-2.5 text-[var(--provisional)]">
        {quality.status === "mismatch" ? "The stored scoring record and the clauses available to this report do not agree." : "No substantive notice clauses are available to support parse-dependent measures."} Parse-dependent maturity and benchmark values are withheld pending review.
      </div>}
      <div className="mt-1 text-xs text-muted-foreground">
        Color shows standing — teal good · gold developing · red needs attention. Maturity scores read
        higher-is-better; exposure scores lower-is-better.
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
            <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {m.name}
              {assessmentId && (
                <InfoButton assessmentId={assessmentId} elementType="score" elementKey={FID_TO_FKEY[m.fid] ?? m.fid} label={m.name} />
              )}
            </div>
            <div className="text-xs text-muted-foreground mb-1">{m.direction}</div>
            {typeof m.value === "number" ? <ScoreCell
              value={m.value}
              formulaId={m.fid}
              formulaDesc={formulaDescs[m.fid] ?? ""}
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
            /> : <span className="text-muted-foreground">Not recorded</span>}
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2.5">
        <span className="text-sm text-muted-foreground">Confidence {typeof vci === "number" ? vci.toFixed(1) : "—"}</span>
        {typeof vci === "number" && <VciBadge label={content.vci_label as string} />}
        <span className="text-xs text-muted-foreground italic">
          Click any score to view its lineage
        </span>
      </div>
    </div>
  );
}
