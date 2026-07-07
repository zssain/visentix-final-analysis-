import { useEffect } from "react";
import "./furniture.css";

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
  vci: number;                 // 0-100
  snapshotId: string;
  frozenDate: string;
  cohortSize: number;
  cohortDate: string;
}

const TYPE_COLORS: Record<string, string> = {
  clause:       "#09234F",
  regulator:    "#005FA3",
  jurisdiction: "#55C7B3",
  cohort:       "#C8A46A",
};

export function LineageDrawer({
  open, onClose,
  formulaId, formulaDesc,
  inputs,
  vci, snapshotId, frozenDate,
  cohortSize, cohortDate,
}: LineageDrawerProps) {
  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="lineage-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        className="lineage-drawer"
        role="complementary"
        aria-label="Score lineage"
      >
        <div className="lineage-drawer-header">
          <h3>Score Lineage</h3>
          <button
            className="lineage-drawer-close"
            onClick={onClose}
            aria-label="Close lineage drawer"
          >
            ✕
          </button>
        </div>

        <div className="lineage-drawer-body">
          {/* Formula */}
          <section>
            <div className="section-label">Formula</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span className="lineage-formula-chip">{formulaId}</span>
            </div>
            <p className="lineage-formula-desc">{formulaDesc}</p>
          </section>

          {/* Input micro-timeline */}
          <section>
            <div className="section-label">Inputs</div>
            <div className="lineage-micro-timeline">
              {inputs.map((inp, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div className="lineage-micro-node">
                    <div
                      className="node-chip"
                      style={{
                        borderColor: TYPE_COLORS[inp.type] ?? "#D9DDE2",
                        color: TYPE_COLORS[inp.type] ?? "#09234F",
                        borderWidth: 1,
                        borderStyle: "solid",
                      }}
                    >
                      {inp.label}
                    </div>
                    <div className="node-label">{inp.type}</div>
                  </div>
                  {i < inputs.length - 1 && (
                    <div className="lineage-micro-arrow" aria-hidden="true">→</div>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* Metrics */}
          <section>
            <div className="section-label">Confidence</div>
            <div className="lineage-metrics">
              <div className="lineage-metric-cell">
                <div className="lm-label">VCI Score</div>
                <div className="lm-value">{vci.toFixed(0)}</div>
                <div className="lm-sub">Visentix Confidence Index</div>
              </div>
              <div className="lineage-metric-cell">
                <div className="lm-label">Cohort Size</div>
                <div className="lm-value">n={cohortSize}</div>
                <div className="lm-sub">as of {cohortDate}</div>
              </div>
            </div>
          </section>

          {/* Snapshot */}
          <section>
            <div className="section-label">Snapshot</div>
            <div className="lineage-snapshot">
              <div className="snap-row">
                <span className="snap-key">Snapshot ID</span>
                <span className="snap-val">{snapshotId}</span>
              </div>
              <div className="snap-row">
                <span className="snap-key">Frozen</span>
                <span className="snap-val">{frozenDate}</span>
              </div>
            </div>
          </section>

          {/* Intelligence mark */}
          <div style={{ marginTop: "auto", paddingTop: 8 }}>
            <span className="intelligence-mark">
              <span className="im-icon">ⓘ</span>
              Intelligence, not legal advice
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
