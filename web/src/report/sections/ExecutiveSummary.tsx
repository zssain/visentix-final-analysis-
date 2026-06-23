import { CohortLabel } from "../CohortLabel";
import type { ReportSection } from "../types";

export function ExecutiveSummary({ content }: { content: ReportSection["content"] }) {
  const takeaways = (content.takeaways as string[]) ?? [];
  return (
    <div data-testid="section-2" className="report-section">
      <h2>2. Executive Summary</h2>
      <p>{content.summary as string}</p>
      {takeaways.length > 0 && (
        <>
          <h3>Key Takeaways</h3>
          <ul>{takeaways.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </>
      )}
      <CohortLabel size={content.cohort_size as number} date={content.cohort_date as string} />
    </div>
  );
}
