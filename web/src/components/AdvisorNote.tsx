import { useState } from "react";
import { ViewSwitch } from "./ViewSwitch";
import { CodexTooltip } from "./CodexTooltip";
import { ProvenanceRibbon } from "./ProvenanceRibbon";
import { ScoreCell } from "./ScoreCell";
import { scoreBandColor } from "../lib/scoreBands";
import { domainLabel } from "../lib/domainLabels";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export interface AdvisorNoteProps {
  /* Identity */
  findingCode: string;       // e.g. "TRK-007"
  title: string;
  domain: string;            // e.g. "data_sharing"

  /* Status */
  status: "draft" | "approved";
  snapshotId: string;
  formulaVersion?: string;
  frozenDate?: string;

  /* Analyst layer */
  exposureScore: number;
  cohortPercentile?: number;  // 0-100; undefined means honestly absent
  vci?: number;              // 0-100, or undefined for honest absence (DATA-003)
  formulaId: string;
  formulaDesc: string;
  cohortSize: number;
  cohortDate: string;

  /* Advisor layer */
  advisorLede: string;
  advisorBody: string;

  /* Lineage chips (clause refs etc.) */
  lineageRefs?: string[];
  /** Rendered inside a row that already shows the code, domain, score and
   *  confidence. Drops everything that would restate them. */
  embedded?: boolean;

  /* View switch default */
  defaultView?: "analyst" | "advisor";
}

export function AdvisorNote({
  findingCode, title, domain,
  status, snapshotId, formulaVersion, frozenDate,
  exposureScore, cohortPercentile, vci,
  formulaId, formulaDesc, cohortSize, cohortDate,
  advisorLede, advisorBody,
  lineageRefs = [],
  embedded = false,
  defaultView = "analyst",
}: AdvisorNoteProps) {
  const [view, setView] = useState<"analyst" | "advisor">(defaultView);
  const isDraft = status === "draft";

  const lineageInputs = [
    { label: findingCode, type: "clause" },
    { label: "Regulator", type: "regulator" },
    { label: "Jurisdiction", type: "jurisdiction" },
    { label: `n=${cohortSize}`, type: "cohort" },
  ];

  return (
    <Card className={cn("gap-0 overflow-hidden py-0", isDraft && "border-dashed")}>
      {/* The ribbon names the snapshot. Inside a findings row that is the third
          time the same snapshot is named on one screen — the report's own
          Traceability part owns it. */}
      {!embedded && <div className="p-5 pb-0">
        <ProvenanceRibbon
          snapshotId={snapshotId}
          formulaVersion={formulaVersion}
          frozenDate={frozenDate}
          status={status}
        />
      </div>}

      {/* Header. Embedded, the row above already carries the code, the domain
          and the title — repeating them is what made expanding a finding feel
          like being shown the same line twice. Only the view switch survives. */}
      <div className={cn("flex flex-wrap items-start justify-between gap-3 p-5", embedded && "px-5 py-3")}>
        {!embedded && (
          <div className="min-w-0 flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <CodexTooltip code={findingCode} />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {domainLabel(domain)}
              </span>
            </div>
            <h3 className="font-display text-lg font-semibold leading-snug">{title}</h3>
          </div>
        )}
        {embedded && (
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            The note
          </span>
        )}
        <ViewSwitch value={view} onChange={setView} />
      </div>

      <Separator />

      <CardContent className="p-5">
        {view === "analyst" ? (
          <>
            <div className={cn("grid gap-5", embedded ? "sm:grid-cols-1" : "sm:grid-cols-3")}>
              {/* Exposure. Hidden when embedded: the row's Score column is this
                  number, and a second copy an inch below it is not detail. */}
              {!embedded && <div className="flex flex-col gap-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Exposure Score
                </div>
                <div className="flex items-baseline gap-1">
                  <ScoreCell
                    value={exposureScore}
                    formulaId={formulaId}
                    formulaDesc={formulaDesc}
                    inputs={lineageInputs}
                    vci={vci}
                    snapshotId={snapshotId}
                    frozenDate={frozenDate ?? "—"}
                    cohortSize={cohortSize}
                    cohortDate={cohortDate}
                    size="lg"
                  />
                  <span className="text-xs text-muted-foreground">/ 100</span>
                </div>
                {/* Meter: one value against a fixed 0-100 scale, not a chart. */}
                <div
                  className="mt-1.5 h-1 overflow-hidden rounded-sm bg-border"
                  role="img"
                  aria-label={`Exposure ${exposureScore.toFixed(1)} out of 100`}
                >
                  <div
                    className="h-full rounded-sm transition-[width] duration-700 ease-out motion-reduce:transition-none"
                    style={{ width: `${exposureScore}%`, background: scoreBandColor(exposureScore) }}
                  />
                </div>
              </div>}

              {/* Cohort percentile — NOT in the row, so it survives embedding.
                  This is the analyst figure the table has no column for. */}
              <div className="flex flex-col gap-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Cohort Percentile
                </div>
                <div className="font-data text-2xl font-bold leading-none">
                  {cohortPercentile !== undefined
                    ? <>{cohortPercentile}<span className="text-[0.6em]">th</span></>
                    : <span className="text-base font-normal text-muted-foreground">Not recorded</span>}
                </div>
                <div className="text-xs text-muted-foreground">n={cohortSize} peers · {cohortDate}</div>
              </div>

              {/* VCI. Also hidden when embedded — the row's Confidence column. */}
              {!embedded && <div className="flex flex-col gap-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Confidence
                </div>
                <div className="font-data text-2xl font-bold leading-none" data-testid="advisor-vci">
                  {vci !== undefined
                    ? <>{vci}<span className="text-[0.6em]">%</span></>
                    : <span className="text-base font-normal text-muted-foreground">Not recorded</span>}
                </div>
                <div className="text-xs text-muted-foreground">Visentix Confidence Index</div>
              </div>}
            </div>

            {lineageRefs.length > 0 && (
              <div className="mt-5 flex flex-wrap items-center gap-1.5 border-t pt-4">
                <span className="text-xs font-semibold text-muted-foreground">Sources:</span>
                {lineageRefs.map(ref => (
                  <Badge key={ref} variant="outline" className="font-data">{ref}</Badge>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            {/* Advisor prose — M-05: rendered verbatim from the frozen snapshot's
                Advisor layer, never regenerated at render time. When the snapshot
                carries no Advisor prose, show honest absence (no house-voice
                filler is fabricated on the client). */}
            <div className="flex flex-col gap-3">
              {(advisorLede.trim() || advisorBody.trim()) ? (
                <>
                  {advisorLede.trim() && (
                    <p className="font-display text-lg leading-relaxed">{advisorLede}</p>
                  )}
                  {advisorBody.trim() && (
                    <p className="max-w-prose text-sm leading-relaxed text-muted-foreground">{advisorBody}</p>
                  )}
                </>
              ) : (
                <p className="text-sm italic text-muted-foreground" data-testid="advisor-absent">
                  An advisor perspective for this finding is not part of this snapshot.
                </p>
              )}

              {/* Embedded, exposure and confidence are already two columns up.
                  The percentile is not, so it is the one that stays. */}
              <div className="flex flex-wrap gap-1.5">
                {!embedded && <Badge variant="outline">Exposure: {exposureScore.toFixed(1)}</Badge>}
                <Badge variant="outline">
                  {cohortPercentile !== undefined ? `${cohortPercentile}th percentile` : "Percentile not recorded"} · n={cohortSize}
                </Badge>
                {!embedded && <Badge variant="outline">Confidence {vci !== undefined ? `${vci}%` : "Not recorded"}</Badge>}
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-end justify-between gap-3 border-t pt-4">
              <div>
                <div className="text-sm font-semibold">The Visentix Privacy Desk</div>
                <div className="text-xs text-muted-foreground">Intelligence authored in house voice</div>
              </div>
              <div className="text-right">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Expert Reviewer</div>
                <div className="text-xs text-muted-foreground">Pending SME review</div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
