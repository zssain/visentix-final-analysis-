import { CohortLabel }    from "../CohortLabel";
import { ScoreCell }      from "../../components/ScoreCell";
import { maturityBandColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";

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
  const measure = (content.measure_label as string | undefined) ?? "Privacy programme maturity";
  const methodology = (content.methodology as {
    dimensions?: string[]; relaxations?: string[]; benchmark_population_version?: number | string;
    as_of_date?: string; low_confidence?: boolean; confidence_penalty?: number;
  } | undefined);
  // A cohort is what makes a percentile mean anything. With no constructed
  // cohort there is no peer population to rank against, so a percentile figure
  // would be a confident-looking number standing on nothing (Hard Rule 7 /
  // DIR-006). It is withheld rather than printed.
  const hasCohort = cohortSize > 0;
  const showPercentile = hasCohort && typeof percentile === "number";
  const hasPeerMark = hasCohort && typeof topQuartile === "number";

  return (
    <div data-testid="section-4" className="report-section">
      <SectionHeading n={4} title="Benchmark Intelligence" />

      {/* Percentile + score headline */}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 24, flexWrap: "wrap", marginBottom: 16 }}>
        {showPercentile && (
          <div>
            <div style={{
              fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 4,
            }}>{measure} Percentile</div>
            <div style={{
              fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
              fontSize: "2.4rem", fontWeight: 700, color: "var(--navy)", lineHeight: 1,
            }}>
              {percentile!.toFixed(1)}<span style={{ fontSize: "1rem" }}>th</span>
            </div>
          </div>
        )}
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

      {/* Position meter — NOT a bar chart.
          This data is one value against a 0–100 scale with an optional peer
          reference. A bar chart of a single bar is a named anti-pattern: it
          spends 200px of axis chrome to say what one marked track says better,
          and with no peer bar it compares the score against nothing at all.
          A meter also survives the PDF renderer (static SVG, no animation). */}
      {typeof orgScore === "number" ? (
        <figure className="bm-meter" style={{ margin: "18px 0 0" }}>
          <div className="bm-meter-track" role="img"
            aria-label={
              `${measure} ${orgScore.toFixed(1)} out of 100` +
              (hasPeerMark ? `, peer top quartile ${topQuartile!.toFixed(1)}` : ", no peer reference recorded")
            }>
            <div className="bm-meter-fill" style={{
              width: `${Math.max(0, Math.min(100, orgScore))}%`,
              background: maturityBandColor(orgScore),
            }} />
            {hasPeerMark && (
              <div className="bm-meter-mark" style={{ left: `${Math.max(0, Math.min(100, topQuartile!))}%` }}>
                <span className="bm-meter-mark-label">Peer top quartile {topQuartile!.toFixed(1)}</span>
              </div>
            )}
          </div>
          <div className="bm-meter-scale">
            <span>0</span>
            <span style={{ color: maturityBandColor(orgScore), fontWeight: 700 }}>
              This organization · {orgScore.toFixed(1)}
            </span>
            <span>100</span>
          </div>
          {!hasPeerMark && (
            <figcaption className="bm-meter-note">
              No peer reference is recorded for this assessment, so this shows where the score sits
              on the scale — not where it sits against comparable organizations.
            </figcaption>
          )}
        </figure>
      ) : (
        <div style={{ padding: "14px 16px", background: "var(--soft-white)", color: "var(--text-muted)" }}>
          A stored peer comparison is not available for this assessment.
        </div>
      )}

      {/* Honest cohort label */}
      <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <CohortLabel size={cohortSize} date={cohortDate} />
      </div>

      {/* Low-confidence label when cohort is small */}
      {methodology?.low_confidence && (
        <div style={{
          marginTop: 10, padding: "8px 12px",
          background: "rgba(200,164,106,0.09)", border: "1px dashed var(--gold)",
          borderRadius: "var(--radius)", fontSize: "0.78rem", color: "var(--provisional)", fontWeight: 600,
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
