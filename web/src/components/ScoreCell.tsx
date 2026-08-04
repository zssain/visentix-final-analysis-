import { useState, useCallback } from "react";
import { LineageDrawer } from "./LineageDrawer";
import "./furniture.css";

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
  value,
  unit,
  formulaId,
  formulaDesc,
  inputs = [],
  vci,
  snapshotId = "—",
  frozenDate = "—",
  cohortSize = 0,
  cohortDate = "—",
  size = "md",
}: ScoreCellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const open  = useCallback(() => setDrawerOpen(true),  []);
  const close = useCallback(() => setDrawerOpen(false), []);

  const sizeMap = { sm: "0.9rem", md: "1.4rem", lg: "2rem" };

  return (
    <>
      <button
        className="score-cell"
        onClick={open}
        aria-label={`${value.toFixed(1)} — click to view score lineage`}
        title="Click to view score lineage"
      >
        <span className="score-num" style={{ fontSize: sizeMap[size] }}>
          {value.toFixed(1)}
        </span>
        {unit && <span className="score-unit">{unit}</span>}
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
