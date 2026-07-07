/** Honest cohort label — always shows real n + date. */
import { LOW_CONFIDENCE_COHORT_N } from "../lib/scoreBands";

interface CohortLabelProps {
  size: number;
  date: string;
}

export function CohortLabel({ size, date }: CohortLabelProps) {
  return (
    <span className="cohort-label" data-testid="cohort-label" style={{
      fontSize: "0.85em", color: "var(--text-muted)", fontStyle: "italic",
    }}>
      Benchmarked against {size} peers as of {date}
      {size < LOW_CONFIDENCE_COHORT_N && " (small cohort; interpret with caution)"}
    </span>
  );
}
