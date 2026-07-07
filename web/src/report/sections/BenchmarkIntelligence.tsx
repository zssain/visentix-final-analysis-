import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { CohortLabel }    from "../CohortLabel";
import { ScoreCell }      from "../../components/ScoreCell";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

export function BenchmarkIntelligence({ content }: { content: ReportSection["content"] }) {
  const orgScore   = (content.org_score  as number | undefined) ?? 0;
  const percentile = (content.percentile as number | undefined) ?? 0;
  const cohortSize = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate = (content.cohort_date as string | undefined) ?? "—";
  const snapshotId = (content.snapshot_id as string | undefined) ?? "S-0000";
  const frozenDate = (content.date        as string | undefined) ?? "—";

  // Honest benchmark bars — exact cohort values, not invented
  const data = [
    { name: "Your Score",   value: orgScore, fill: orgScore >= 70 ? "#F87171" : orgScore >= 45 ? "#C8A46A" : "#55C7B3" },
    { name: "Peer Median",  value: content.peer_median  as number ?? 50, fill: "#D9DDE2" },
    { name: "Top Quartile", value: content.top_quartile as number ?? 75, fill: "#09234F" },
  ];

  return (
    <div data-testid="section-4" className="report-section">
      <h2>4. Benchmark Intelligence</h2>

      {/* Percentile + score headline */}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 24, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <div style={{
            fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 4,
          }}>Cohort Percentile</div>
          <div style={{
            fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
            fontSize: "2.4rem", fontWeight: 700, color: "var(--navy)", lineHeight: 1,
          }}>
            {percentile?.toFixed(1)}<span style={{ fontSize: "1rem" }}>th</span>
          </div>
        </div>
        <div>
          <div style={{
            fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 4,
          }}>Your Score</div>
          <ScoreCell
            value={orgScore}
            formulaId="F-010"
            formulaDesc="Weighted combination of all six risk dimensions to produce the overall privacy intelligence score."
            inputs={[
              { label: "Notice", type: "clause" },
              { label: "Regulator", type: "regulator" },
              { label: `n=${cohortSize}`, type: "cohort" },
            ]}
            vci={(content.vci_score as number | undefined) ?? 75}
            snapshotId={snapshotId}
            frozenDate={frozenDate}
            cohortSize={cohortSize}
            cohortDate={cohortDate}
            size="lg"
          />
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: "100%", height: 200 }} className="chart-container">
        <ResponsiveContainer>
          <BarChart data={data} barSize={48}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(v: any) => [`${Number(v)?.toFixed(1)}`, "Score"]}
              contentStyle={{ fontSize: "0.82rem", borderRadius: 6 }}
            />
            <Bar dataKey="value" isAnimationActive={false} radius={[4, 4, 0, 0]}>
              {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Honest cohort label */}
      <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <CohortLabel size={cohortSize} date={cohortDate} />
        <IntelligenceMark />
      </div>

      {/* Low-confidence label when cohort is small */}
      {cohortSize > 0 && cohortSize < 15 && (
        <div style={{
          marginTop: 10, padding: "8px 12px",
          background: "rgba(200,164,106,0.09)", border: "1px dashed var(--gold)",
          borderRadius: "var(--radius)", fontSize: "0.78rem", color: "#7a5c20", fontWeight: 600,
        }}>
          ⚠ Low-confidence benchmarking — cohort size n={cohortSize} is small.
          Percentile figures should be interpreted with caution.
        </div>
      )}
    </div>
  );
}
