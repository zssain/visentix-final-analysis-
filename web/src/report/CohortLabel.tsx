/** Honest cohort label — always shows real n + date. */

interface CohortLabelProps {
  size: number;
  date: string;
}

export function CohortLabel({ size, date }: CohortLabelProps) {
  return (
    <span className="cohort-label" data-testid="cohort-label" style={{
      fontSize: "0.85em", color: "#6b7280", fontStyle: "italic",
    }}>
      Benchmarked against {size} peers as of {date}
      {size < 50 && " (small cohort; interpret with caution)"}
    </span>
  );
}
