/**
 * InfoButton — small "i" affordance that opens the ExplainPanel.
 * Placed next to scores, findings, and narrative sentences.
 */
import { useState } from "react";
import { ExplainPanel } from "./ExplainPanel";

export interface InfoButtonProps {
  /** The slice of the explanation bundle for this element */
  explanation: Record<string, unknown>;
  /** What kind of element: "score" | "finding" | "narrative" */
  kind: "score" | "finding" | "narrative";
  /** Display label shown in the panel header */
  label?: string;
}

export function InfoButton({ explanation, kind, label }: InfoButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        data-testid="info-button"
        className="info-button"
        onClick={() => setOpen(true)}
        aria-label={`Explain ${label ?? kind}`}
        title={`How was this ${kind} computed?`}
      >
        &#8505;&#65039;
      </button>
      {open && (
        <ExplainPanel
          explanation={explanation}
          kind={kind}
          label={label}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
