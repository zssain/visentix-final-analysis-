import { Badge } from "@/components/ui/badge";

interface Driver { judgment?: string; rests_on?: string; strength?: string; why?: string }
export interface SourceSummaryContent {
  drivers?: Driver[];
  strengths?: string[];
  limitations?: string[];
}

/** Evidence-base strength is NOT a score standing — a good score resting on thin
 *  evidence is still thin evidence, and collapsing the two would hide exactly
 *  what this block exists to show. Hence chart-ramp/neutral, not traffic light. */
function strengthLabel(s?: string) {
  switch (s) {
    case "strong":   return { text: "Strong",   variant: "verified" as const };
    case "moderate": return { text: "Moderate", variant: "secondary" as const };
    case "limited":  return { text: "Limited",  variant: "provisional" as const };
    default:         return { text: "Not recorded", variant: "outline" as const };
  }
}

/**
 * RPT-007 — what the judgments rest on, and where the base is thin.
 *
 * Per-figure lineage already answers "where did this number come from". This
 * answers the question a third-party reader opens with: which evidence is
 * carrying the conclusions?
 *
 * Frozen into the snapshot at assembly time (DIR-008 — presentation never
 * recalculates). Snapshots frozen before RPT-007 render honest absence and are
 * never back-filled (Hard Rule 6).
 */
export function SourceSummary({ summary }: { summary?: SourceSummaryContent }) {
  if (!summary) {
    return (
      <p className="mb-4 text-sm text-muted-foreground">
        No source summary was recorded for this snapshot. Per-figure lineage is unaffected
        and appears in the table below.
      </p>
    );
  }

  const drivers = summary.drivers ?? [];
  const strengths = summary.strengths ?? [];
  const limitations = summary.limitations ?? [];

  return (
    <section className="mb-6 flex flex-col gap-4" data-testid="source-summary">
      <p className="max-w-prose text-sm text-muted-foreground">
        The figures in this report rest on the evidence below. Where that evidence is thin,
        it is named rather than smoothed over.
      </p>

      {drivers.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40 text-left">
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Judgment</th>
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Rests on</th>
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Evidence base</th>
                <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Detail</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((d, i) => {
                const s = strengthLabel(d.strength);
                return (
                  <tr key={i} className="border-b last:border-0 align-top">
                    <td className="px-3 py-2.5 font-semibold">{d.judgment}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{d.rests_on}</td>
                    <td className="px-3 py-2.5"><Badge variant={s.variant}>{s.text}</Badge></td>
                    <td className="px-3 py-2.5 text-muted-foreground">{d.why}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No judgment drivers recorded.</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Strengths of this evidence base
          </h4>
          {strengths.length > 0 ? (
            <ul className="flex list-disc flex-col gap-1 pl-4 text-sm text-muted-foreground">
              {strengths.map((x, i) => <li key={i}>{x}</li>)}
            </ul>
          ) : <p className="text-sm text-muted-foreground">No particular strengths recorded.</p>}
        </div>
        <div>
          <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Limitations of this evidence base
          </h4>
          {limitations.length > 0 ? (
            <ul className="flex list-disc flex-col gap-1 pl-4 text-sm text-muted-foreground">
              {limitations.map((x, i) => <li key={i}>{x}</li>)}
            </ul>
          ) : <p className="text-sm text-muted-foreground">No limitations recorded.</p>}
        </div>
      </div>
    </section>
  );
}
