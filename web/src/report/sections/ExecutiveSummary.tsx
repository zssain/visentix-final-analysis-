import { CohortLabel } from "../CohortLabel";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

type Register = "executive" | "practitioner" | "plain";

const REGISTER_LABELS: Record<Register, string> = {
  executive:   "Executive",
  practitioner: "Practitioner",
  plain:       "Plain English",
};

export function ExecutiveSummary({ content }: { content: ReportSection["content"] }) {
  const takeaways     = (content.takeaways as string[]) ?? [];
  const summary       = content.summary as string;
  const summaryPract  = (content.summary_practitioner as string | undefined);
  const summaryPlain  = (content.summary_plain        as string | undefined);

  // Reader-register toggle — stub until backend supplies the two alternative texts
  // Rendered as a controlled element but note we don't useState here (this file is deterministic for PDF)
  // PDF snapshot always renders the executive register.
  const registers: Register[] = summaryPract || summaryPlain
    ? ["executive", "practitioner", "plain"]
    : ["executive"];

  const textByRegister: Record<Register, string> = {
    executive:   summary,
    practitioner: summaryPract ?? summary,
    plain:        summaryPlain ?? summary,
  };

  return (
    <div data-testid="section-2" className="report-section">
      <h2>2. Executive Summary</h2>

      {/* Register tabs — shown only when alternatives exist */}
      {registers.length > 1 && (
        <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
          {registers.map(r => (
            <span
              key={r}
              className={`badge ${r === "executive" ? "badge-navy" : "badge-moderate"}`}
              style={{ fontSize: "0.7rem", cursor: "default" }}
            >
              {REGISTER_LABELS[r]}
            </span>
          ))}
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginLeft: 6, lineHeight: "22px" }}>
            (reader-register selector — stub, PDF always uses Executive register)
          </span>
        </div>
      )}

      {/* Main summary paragraph */}
      <p style={{ fontSize: "0.95rem", lineHeight: 1.8, color: "var(--text)" }}>
        {textByRegister["executive"]}
      </p>

      {/* Key takeaways */}
      {takeaways.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{
            fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 8,
          }}>Key Takeaways</div>
          <ul style={{ display: "flex", flexDirection: "column", gap: 6, paddingLeft: 0, listStyle: "none" }}>
            {takeaways.map((t, i) => (
              <li key={i} style={{
                display: "flex", gap: 10, alignItems: "flex-start",
                padding: "6px 0", borderBottom: i < takeaways.length - 1 ? "1px solid var(--border)" : "none",
              }}>
                <span style={{ color: "var(--teal)", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>→</span>
                <span style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <CohortLabel size={content.cohort_size as number} date={content.cohort_date as string} />
        <IntelligenceMark />
      </div>
    </div>
  );
}
