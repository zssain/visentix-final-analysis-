import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface LineageInput {
  label: string;    // e.g. "C-118"
  type: string;     // e.g. "clause" | "regulator" | "jurisdiction" | "cohort"
}

interface LineageDrawerProps {
  open: boolean;
  onClose: () => void;
  formulaId: string;           // e.g. "F-010"
  formulaDesc: string;         // plain English
  inputs: LineageInput[];
  vci?: number;                // 0-100, or undefined for honest absence (DATA-003)
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

export function LineageDrawer({
  open, onClose,
  formulaId, formulaDesc,
  inputs,
  vci, snapshotId, frozenDate,
  cohortSize, cohortDate,
}: LineageDrawerProps) {
  /* Escape, focus trap, restore-focus and the backdrop are Radix's job now —
     the hand-rolled version wired only Escape. */
  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Score Lineage</SheetTitle>
        </SheetHeader>

        <div className="flex flex-col gap-6 px-4 pb-6">
          <Section label="Formula">
            <Badge variant="outline" className="font-data w-fit">{formulaId}</Badge>
            <p className="text-sm text-muted-foreground">{formulaDesc}</p>
          </Section>

          <Separator />

          <Section label="Inputs">
            <div className="flex flex-wrap items-center gap-1.5">
              {inputs.map((inp, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <div className="flex flex-col items-center gap-0.5">
                    <Badge variant="outline" className="font-data">{inp.label}</Badge>
                    <span className="text-[10px] capitalize text-muted-foreground">{inp.type}</span>
                  </div>
                  {i < inputs.length - 1 && (
                    <span className="text-muted-foreground pb-3.5" aria-hidden="true">→</span>
                  )}
                </div>
              ))}
            </div>
          </Section>

          <Separator />

          <Section label="Confidence">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-md border p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">VCI Score</div>
                {/* Honest absence: an unmeasured confidence is a dash, never a 0. */}
                <div className="font-data text-xl font-bold" data-testid="lineage-vci">{vci !== undefined ? vci.toFixed(0) : "—"}</div>
                <div className="text-[11px] text-muted-foreground">Visentix Confidence Index</div>
              </div>
              <div className="rounded-md border p-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Cohort Size</div>
                <div className="font-data text-xl font-bold">n={cohortSize}</div>
                <div className="text-[11px] text-muted-foreground">as of {cohortDate}</div>
              </div>
            </div>
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
