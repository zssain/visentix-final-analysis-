import "./furniture.css";

interface ProvenanceRibbonProps {
  snapshotId: string;
  formulaVersion?: string;
  frozenDate?: string;
  status: "draft" | "approved";
  condensed?: boolean;
}

export function ProvenanceRibbon({
  snapshotId,
  formulaVersion,
  frozenDate,
  status,
  condensed = false,
}: ProvenanceRibbonProps) {
  const cls = ["prov-ribbon", status, condensed ? "condensed" : ""].filter(Boolean).join(" ");

  return (
    <div className={cls} role="status" aria-label={`Report status: ${status}`}>
      <span className="ribbon-id">{snapshotId}</span>
      {formulaVersion && (
        <>
          <span className="ribbon-sep">·</span>
          <span>{formulaVersion}</span>
        </>
      )}
      {frozenDate && (
        <>
          <span className="ribbon-sep">·</span>
          <span>Frozen {frozenDate}</span>
        </>
      )}
      <div className="ribbon-mark">
        <div className="ribbon-dot" />
        {status === "approved" ? "Reproducible" : "Draft — Pending Review"}
      </div>
    </div>
  );
}
