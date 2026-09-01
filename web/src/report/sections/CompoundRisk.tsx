import { ScoreCell }      from "../../components/ScoreCell";
import { scoreBandColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";

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
      <SectionHeading n={7} title="Compound Risk Analysis" />

      {/* Headline */}
      <div className="mb-5 flex flex-wrap items-baseline gap-3">
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
        /> : <span className="text-muted-foreground">Compound exposure not recorded</span>}
        <span className="text-sm italic text-muted-foreground">
          Compound Risk Score — click to view lineage
        </span>
      </div>

      {/* Dimension breakdown */}
      {dimensions.length > 0 ? (
        <div className="flex flex-col gap-2.5">
          {dimensions.map((d, i) => {
            /* An unrecorded dimension must not be coloured as if it scored.
               This previously passed `d.score ?? 0` into scoreBandColor, so a
               missing score rendered GREEN — 0 exposure reads as good, which is
               a judgement invented from absence (Hard Rule 7). */
            const hasScore = typeof d.score === "number";
            const color = hasScore ? scoreBandColor(d.score as number) : "var(--muted-foreground)";
            return (
              <div key={i}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">{d.name}</span>
                  <span
                    className="font-data text-sm font-bold tabular-nums"
                    style={{ color }}
                  >
                    {hasScore ? (d.score as number).toFixed(1) : "Not recorded"}
                  </span>
                </div>
                <div
                  className="h-[5px] overflow-hidden rounded-sm bg-border"
                  role="img"
                  aria-label={hasScore ? `${d.name} ${(d.score as number).toFixed(1)} out of 100` : `${d.name} not recorded`}
                >
                  {/* No bar at all when there is no score — a zero-width bar and
                      a genuine zero would otherwise look identical. */}
                  {hasScore && (
                    <div
                      className="h-full rounded-sm transition-[width] duration-500 ease-out motion-reduce:transition-none"
                      style={{ width: `${Math.max(0, Math.min(100, d.score as number))}%`, background: color }}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          Compound risk dimension breakdown will appear once all formula inputs are available.
        </div>
      )}

      {typeof lineage.cm === "number" && (
        <p className="mt-3 max-w-prose text-sm text-muted-foreground">
          Correlation multiplier: {lineage.cm.toFixed(2)}. The multiplier reflects how related exposure signals can reinforce one another.
        </p>
      )}
    </div>
  );
}
