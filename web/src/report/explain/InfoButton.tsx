/**
 * InfoButton — circular "ⓘ" affordance.
 * 44px touch target, keyboard-focusable, opens ExplanationPanel.
 */
import { useState, useCallback } from "react";
import { ExplanationPanel } from "./ExplanationPanel";
import { useExplain } from "./ExplainContext";

interface InfoButtonProps {
  assessmentId: string;
  elementType: string;  // score | finding | domain | clause | cohort | recommendation | report_section
  elementKey: string;   // e.g. "f002", "SH-002", "CR", etc.
  label?: string;       // optional decoded label for the panel header
}

export function InfoButton({ assessmentId, elementType, elementKey, label }: InfoButtonProps) {
  const [open, setOpen] = useState(false);
  const { getEnvelope, prefetch } = useExplain();

  const handleOpen = useCallback(() => {
    prefetch(assessmentId);
    setOpen(true);
  }, [assessmentId, prefetch]);

  const envelope = getEnvelope(assessmentId, elementType, elementKey);

  return (
    <>
      <button
        className="info-btn"
        data-testid="info-button"
        onClick={handleOpen}
        aria-label={`Explain how ${label ?? elementKey} was calculated`}
        title={`Explain: ${label ?? elementKey}`}
        type="button"
      >
        <span aria-hidden="true">ⓘ</span>
      </button>
      {open && (
        <ExplanationPanel
          envelope={envelope}
          elementType={elementType}
          elementKey={elementKey}
          label={label}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
