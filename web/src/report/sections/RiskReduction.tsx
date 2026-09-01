import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";
import { Badge } from "@/components/ui/badge";
import { StatTile } from "@/components/ui/stat-tile";
import { domainLabel } from "../../lib/labels";

interface Priority {
  code: string;
  domain: string;
  effort: "low" | "medium" | "high";
  impact: "low" | "medium" | "high";
  description: string;
}

export function RiskReduction({ content }: { content: ReportSection["content"] }) {
  const highCount    = (content.high_count   as number | undefined) ?? 0;
  const mediumCount  = (content.medium_count as number | undefined) ?? 0;
  const priorities   = (content.priorities   as Priority[] | undefined) ?? [];
  const prose        = content.prose         as string | undefined;

  return (
    <div data-testid="section-10" className="report-section">
      <SectionHeading n={10} title="Risk Reduction Priorities" />

      <div className="mb-4 flex flex-wrap gap-6 rounded-lg border bg-muted/40 px-4 py-3">
        <StatTile label="High exposure findings"     value={highCount}   tone="bad" />
        <StatTile label="Elevated exposure findings" value={mediumCount} tone="mid" />
      </div>

      {prose && (
        <p className="mb-4 max-w-prose text-sm leading-relaxed text-muted-foreground">{prose}</p>
      )}

      {priorities.length > 0 && (
        <>
          <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Prioritised actions — ordered by impact × effort
          </div>
          <ol className="flex flex-col gap-2">
            {priorities.map((p, i) => (
              <li key={i} className="flex items-start gap-3.5 rounded-lg border bg-card px-3.5 py-2.5">
                <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">
                  {i + 1}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <Badge className="font-data">{p.code}</Badge>
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {domainLabel(p.domain)}
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed text-muted-foreground">{p.description}</p>
                </div>

                {/* Effort and impact are MAGNITUDES, not standings.
                    They previously used red/gold/teal and navy/blue/grey, which
                    read "high effort = bad" — high effort is not bad, it is
                    effortful, and high impact is good. Neither belongs on the
                    traffic-light scale, so the word carries the meaning and the
                    pill stays neutral.
                    (The old pills also had no background at all: the code
                    appended a hex-alpha suffix to a var() reference —
                    `var(--teal)18` — which is not valid CSS.) */}
                <dl className="flex shrink-0 flex-col gap-1 text-xs">
                  <div className="flex items-center gap-1.5">
                    <dt className="w-10 font-semibold text-muted-foreground">Effort</dt>
                    <dd><Badge variant="outline" className="capitalize">{p.effort}</Badge></dd>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <dt className="w-10 font-semibold text-muted-foreground">Impact</dt>
                    <dd><Badge variant="secondary" className="capitalize">{p.impact}</Badge></dd>
                  </div>
                </dl>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
