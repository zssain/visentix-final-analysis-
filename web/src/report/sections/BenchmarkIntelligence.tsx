import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { CohortLabel }    from "../CohortLabel";
import { ScoreCell }      from "../../components/ScoreCell";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { maturityBandColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";

export function BenchmarkIntelligence({ content }: { content: ReportSection["content"] }) {
  const orgScore   = content.org_score as number | null | undefined;
  const percentile = content.percentile as number | null | undefined;
  const cohortSize = (content.cohort_size as number | undefined) ?? 0;
  const cohortDate = (content.cohort_date as string | undefined) ?? "—";
  const snapshotId = (content.snapshot_id as string | undefined) ?? "—" /* honest absence — never a plausible-looking fake ID (Hard Rule 7) */;
  const frozenDate = (content.date        as string | undefined) ?? "—";

  // Honest benchmark bars — a bar renders only when its value is real.
  // A missing peer median must never fall back to an invented 50 (Hard Rule 7).
  const topQuartile = content.top_quartile_score as number | null | undefined;
  const measure = (content.measure_label as string | undefined) ?? "Governance Maturity (PGMS)";
  const methodology = (content.methodology as {
    dimensions?: string[]; relaxations?: string[]; benchmark_population_version?: number | string;
    as_of_date?: string; low_confidence?: boolean; confidence_penalty?: number;
  } | undefined);
  const data = [
    ...(typeof orgScore === "number" ? [{ name: `Your ${measure}`, value: orgScore, fill: maturityBandColor(orgScore) }] : []),
    ...(typeof topQuartile === "number" ? [{ name: "Peer Top Quartile", value: topQuartile, fill: "#09234F" }] : []),
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
          }}>{measure} Percentile</div>
          <div style={{
            fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
            fontSize: "2.4rem", fontWeight: 700, color: "var(--navy)", lineHeight: 1,
          }}>
            {typeof percentile === "number" ? <>{percentile.toFixed(1)}<span style={{ fontSize: "1rem" }}>th</span></> : "Not recorded"}
          </div>
        </div>
        <div>
          <div style={{
            fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 4,
          }}>Your {measure} Score · higher is better</div>
          {typeof orgScore === "number" ? <ScoreCell
            value={orgScore}
            formulaId="F-003"
            formulaDesc={(content.formula_descs as Record<string, string> | undefined)?.["F-003"] ?? ""}
            inputs={[
              { label: "Notice", type: "clause" },
              { label: "Regulator", type: "regulator" },
              { label: `n=${cohortSize}`, type: "cohort" },
            ]}
            /* Never invent confidence: missing VCI stays absent in lineage. */
            vci={content.vci_score as number | undefined}
            snapshotId={snapshotId}
            frozenDate={frozenDate}
            cohortSize={cohortSize}
            cohortDate={cohortDate}
            size="lg"
          /> : <div style={{ color: "var(--text-muted)" }}>Not recorded</div>}
        </div>
      </div>

      {/* Chart */}
      {data.length > 0 ? <div style={{ width: "100%", height: 200 }} className="chart-container">
        <ResponsiveContainer>
          <BarChart data={data} barSize={48}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(v) => [`${Number(v).toFixed(1)}`, "Score"]}
              contentStyle={{ fontSize: "0.82rem", borderRadius: 6 }}
            />
            <Bar dataKey="value" isAnimationActive={false} radius={[4, 4, 0, 0]}>
              {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div> : <div style={{ padding: "14px 16px", background: "var(--soft-white)", color: "var(--text-muted)" }}>
        A stored peer comparison is not available for this assessment.
      </div>}

      {/* Honest cohort label */}
      <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <CohortLabel size={cohortSize} date={cohortDate} />
        <IntelligenceMark />
      </div>

      {/* Low-confidence label when cohort is small */}
      {methodology?.low_confidence && (
        <div style={{
          marginTop: 10, padding: "8px 12px",
          background: "rgba(200,164,106,0.09)", border: "1px dashed var(--gold)",
          borderRadius: "var(--radius)", fontSize: "0.78rem", color: "#7a5c20", fontWeight: 600,
        }}>
          ⚠ Low-confidence benchmarking — cohort size n={cohortSize} is small.
          Percentile figures should be interpreted with caution.
        </div>
      )}

      {methodology ? (
        <div style={{ marginTop: 12, padding: "12px 14px", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: "0.8rem" }}>
          <strong>Peer-cohort methodology</strong>
          <div>Dimensions: {methodology.dimensions?.length ? methodology.dimensions.join(" · ") : "Not recorded"}</div>
          <div>Population version: {methodology.benchmark_population_version ?? "Not recorded"} · as of {methodology.as_of_date ?? cohortDate}</div>
          {!!methodology.relaxations?.length && <div>Cohort widening: {methodology.relaxations.join(", ")}. Confidence is reduced to reflect the broader comparison.</div>}
          <div>Comparison formula: F-003 · percentile formula: F-011</div>
        </div>
      ) : <div style={{ marginTop: 12, color: "var(--text-muted)", fontSize: "0.8rem" }}>Cohort methodology not recorded.</div>}
    </div>
  );
}
