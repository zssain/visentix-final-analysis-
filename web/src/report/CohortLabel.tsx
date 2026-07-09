/** Honest cohort label — shows real n + date + population version. */
import { LOW_CONFIDENCE_COHORT_N } from "../lib/scoreBands";

interface CohortLabelProps {
  size: number;
  date: string;
  populationVersion?: number | string;
}

export function CohortLabel({ size, date, populationVersion }: CohortLabelProps) {
  const cohortDesc = size > 0
    ? `Benchmarked vs ${size} normalized peers`
    : "Benchmark cohort not yet constructed";
  const dateDesc = date ? ` as of ${date}` : "";
  const popDesc = populationVersion ? ` (population ${populationVersion})` : "";

  return (
    <span className="cohort-label" data-testid="cohort-label" style={{
      fontSize: "0.85em", color: "var(--text-muted)", fontStyle: "italic",
    }}>
      {cohortDesc}{dateDesc}{popDesc}
      {size > 0 && size < LOW_CONFIDENCE_COHORT_N && " — small cohort; interpret with caution"}
    </span>
  );
}
