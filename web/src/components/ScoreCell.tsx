import { useState, useCallback } from "react";
import { LineageDrawer } from "./LineageDrawer";
import { cn } from "@/lib/utils";

interface ScoreCellProps {
  value: number;
  unit?: string;
  formulaId: string;
  formulaDesc: string;
  inputs?: { label: string; type: string }[];
  vci?: number;
  snapshotId?: string;
  frozenDate?: string;
  cohortSize?: number;
  cohortDate?: string;
  size?: "sm" | "md" | "lg";
}

export function ScoreCell({
  value, unit, formulaId, formulaDesc,
  inputs = [], vci,
  snapshotId = "—", frozenDate = "—",
  cohortSize = 0, cohortDate = "—",
  size = "md",
}: ScoreCellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const open  = useCallback(() => setDrawerOpen(true),  []);
  const close = useCallback(() => setDrawerOpen(false), []);

  const sizeClass = { sm: "text-sm", md: "text-2xl", lg: "text-4xl" }[size];

  return (
    <>
      <button
        onClick={open}
        aria-label={`${value.toFixed(1)} — click to view score lineage`}
        title="Click to view score lineage"
        className={cn(
          "group inline-flex items-baseline gap-1 rounded-md px-1 -mx-1 transition-colors",
          "hover:bg-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
          "underline decoration-dotted decoration-muted-foreground/50 underline-offset-4"
        )}
      >
        <span className={cn("font-data font-bold tabular-nums leading-none", sizeClass)}>
          {value.toFixed(1)}
        </span>
        {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
      </button>

      <LineageDrawer
        open={drawerOpen}
        onClose={close}
        formulaId={formulaId}
        formulaDesc={formulaDesc}
        inputs={inputs}
        vci={vci}
        snapshotId={snapshotId}
        frozenDate={frozenDate}
        cohortSize={cohortSize}
        cohortDate={cohortDate}
      />
    </>
  );
}
