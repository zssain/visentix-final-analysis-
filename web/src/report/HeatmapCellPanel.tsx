/**
 * Heatmap cell detail panel (F05 AC-13).
 *
 * Every value below is READ from the frozen snapshot cell. Nothing here
 * derives a new number at render time: `toFixed` and a fraction shown as a
 * percentage are formatting, and the band label comes off the governed
 * thresholds in `scoreBands.ts`. If a figure is not in the snapshot it does not
 * appear — it is never reconstructed (AC-7).
 *
 * Two cases the grid itself cannot express:
 *
 *  - **An unevidenced cell still carries an intensity.** The engine gives a
 *    domain with no matching clause a floor of `rpw x efw x 0.1`, so the number
 *    is real but it measures the REGULATOR's published interest, not this
 *    notice. Presenting it as exposure would read as a measurement of the
 *    reader's notice that nobody made. The panel says so in words and labels
 *    the inputs as the regulator's baseline.
 *
 *  - **A below-floor cohort gets no peer comparison at all.** Not a hedged one
 *    (OD-05 / DIR-006).
 */
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { domainLabel } from "../lib/domainLabels";
import { exposureBand, scoreBandColor, LOW_CONFIDENCE_COHORT_N } from "../lib/scoreBands";

/** The snapshot's cell, in full. `rpw`/`efw`/`f004_boost` are frozen inputs;
 *  `vci` is deliberately NOT rendered — see the note at the bottom of this file. */
export interface HeatmapCellData {
  domain: string;
  intensity: number;
  clause_density: number;
  rpw?: number;
  efw?: number;
  f004_boost?: number;
  vci?: number;
  evidenced?: boolean;
}

export interface HeatmapCellPanelProps {
  open: boolean;
  onClose: () => void;
  cell: HeatmapCellData | null;
  regulatorName: string;
  jurisdiction: string;
  evidenced: boolean;
  snapshotId: string;
  frozenDate: string;
  cohortSize: number;
  cohortDate: string;
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      {children}
    </section>
  );
}

/** A stored input, or honest absence. Never a zero standing in for "unknown". */
function Input({ label, value, hint }: { label: string; value: number | undefined; hint: string }) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-data text-lg font-bold tabular-nums">
        {typeof value === "number" ? value.toFixed(2) : "—"}
      </div>
      <div className="text-[11px] text-muted-foreground">{hint}</div>
    </div>
  );
}

export function HeatmapCellPanel({
  open, onClose, cell,
  regulatorName, jurisdiction, evidenced,
  snapshotId, frozenDate, cohortSize, cohortDate,
}: HeatmapCellPanelProps) {
  if (!cell) return null;

  const domain = domainLabel(cell.domain);
  /* The cohort floor is a gate, not a caveat: below it there is no peer
     comparison in this panel at all. */
  const hasCohort = cohortSize >= LOW_CONFIDENCE_COHORT_N;

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto" data-testid="heatmap-cell-panel">
        <SheetHeader>
          <SheetTitle>{regulatorName} · {domain}</SheetTitle>
        </SheetHeader>

        <div className="flex flex-col gap-6 px-4 pb-6">
          <Section label="Cell">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{jurisdiction || "Jurisdiction not recorded"}</Badge>
              <Badge variant="outline" className="font-data">F-002</Badge>
            </div>
          </Section>

          <Separator />

          {evidenced ? (
            <Section label="Standing">
              {/* Band label leads; the figure is secondary (AC-11). */}
              <div className="flex items-baseline gap-2.5">
                <span className="text-base font-semibold" style={{ color: scoreBandColor(cell.intensity) }}>
                  {exposureBand(cell.intensity)}
                </span>
                <span className="font-data text-2xl font-bold tabular-nums" data-testid="cell-intensity">
                  {cell.intensity.toFixed(1)}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                Your notice discloses in this domain, and this regulator publishes expectations
                for it. The figure combines the regulator's priority for the domain with how
                much of your notice addresses it.
              </p>
            </Section>
          ) : (
            <Section label="Evidence">
              {/* AC-13: an unevidenced cell opens to an explicit no-evidence line. */}
              <p className="text-sm" data-testid="cell-no-evidence">
                <strong>No clause from your notice maps to {domain}.</strong>
              </p>
              <p className="text-sm text-muted-foreground">
                Nothing about your notice was measured for this cell. The grid shows it hatched
                rather than scored, and the inputs below are {regulatorName}'s published baseline
                interest in the domain — not a reading of your notice.
              </p>
            </Section>
          )}

          <Separator />

          <Section label={evidenced ? "What this rests on" : "Regulator baseline"}>
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Priority weight"
                value={cell.rpw}
                hint={`${regulatorName}'s published priority for this domain`}
              />
              <Input
                label="Enforcement frequency"
                value={cell.efw}
                hint="How often this regulator acts"
              />
              <Input
                label="Notice share"
                value={cell.clause_density}
                hint={evidenced
                  ? "Fraction of your notice's clauses in this domain"
                  : "No clauses in this domain"}
              />
              <Input
                label="Enforcement correlation"
                value={cell.f004_boost}
                hint="F-004 boost, 0 when no precedent applies"
              />
            </div>
          </Section>

          <Separator />

          <Section label="Peer comparison">
            {hasCohort ? (
              <p className="text-sm text-muted-foreground" data-testid="cell-cohort">
                Benchmarked against {cohortSize} comparable organizations as of {cohortDate}.
              </p>
            ) : (
              /* AC-13: below the floor, no comparison is offered — not a
                 caveated one. A comparison the cohort cannot support is worse
                 than none, because the reader cannot see the cohort. */
              <p className="text-sm text-muted-foreground" data-testid="cell-no-cohort">
                No peer comparison for this cell. A cohort of at least{" "}
                {LOW_CONFIDENCE_COHORT_N} comparable organizations is required, and this
                snapshot {cohortSize > 0 ? `has ${cohortSize}` : "has none"}.
              </p>
            )}
          </Section>

          <Separator />

          <Section label="Snapshot">
            <dl className="flex flex-col gap-1.5 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Snapshot ID</dt>
                <dd className="font-data truncate">{snapshotId}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Frozen</dt>
                <dd className="font-data">{frozenDate}</dd>
              </div>
            </dl>
          </Section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/* Why `cell.vci` is not rendered here.
 *
 * Every VCI in this product is 0-100, and Hard Rule 5's do-not-present
 * threshold (VCI < 40) is written on that scale. The heatmap engine's per-cell
 * `vci` is 0-1: `base_vci` defaults to 0.5 and is multiplied down from there.
 * The two share a name and a meaning but not a scale, so a surface that renders
 * the cell value believing it is the usual one would show "0.4" where the
 * reader expects 40 — and a suppression check written as `vci < 40` would treat
 * EVERY cell as suppressible.
 *
 * Rather than convert here and bake the ambiguity into a customer surface, this
 * panel reports the cell's inputs and leaves confidence to the section score,
 * whose scale is unambiguous. Reconciling the two scales is a scoring change
 * (Hard Rule 3), not a display one.
 */
