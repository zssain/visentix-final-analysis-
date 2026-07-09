import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

interface Rec { severity: string; code: string; title: string; prose: string; }

// Guardrail-compliant severity label mapping
// Maps severity to exposure language — never legal verdict language
const SEVERITY_LABEL: Record<string, string> = {
  high:     "High Exposure",
  elevated: "Elevated Exposure",
  moderate: "Moderate Exposure",
  low:      "Lower Exposure",
};

const SEVERITY_BORDER: Record<string, string> = {
  high:     "var(--red)",
  elevated: "var(--gold)",
  moderate: "var(--exec-blue)",
  low:      "var(--teal)",
};

export function Recommendations({ content }: { content: ReportSection["content"] }) {
  const recs = (content.recommendations as Rec[]) ?? [];

  return (
    <div data-testid="section-9" className="report-section">
      <h2>9. Strategic Recommendations</h2>
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: 16 }}>
        Recommendations are ordered by exposure level. They describe disclosure gaps and maturity
        improvements — not legal requirements.
      </p>

      {recs.length === 0 ? (
        <div style={{
          background: "var(--soft-white)", border: "1px solid var(--border)",
          borderRadius: "var(--radius)", padding: "16px 18px",
          color: "var(--text-muted)", fontSize: "0.88rem",
        }}>
          No recommendations to display at this time.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {recs.map((r, i) => (
            <div key={i} style={{
              borderLeft: `3px solid ${SEVERITY_BORDER[r.severity.toLowerCase()] ?? "var(--border)"}`,
              paddingLeft: 16, paddingTop: 4, paddingBottom: 4,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                <span style={{
                  background: "var(--navy)", color: "white",
                  fontFamily: "var(--font-data)", fontSize: "0.72rem", fontWeight: 700,
                  padding: "2px 8px", borderRadius: 4, letterSpacing: "0.04em",
                }}>{r.code}</span>
                <span style={{
                  fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.07em", color: SEVERITY_BORDER[r.severity.toLowerCase()] ?? "var(--text-muted)",
                }}>
                  {SEVERITY_LABEL[r.severity.toLowerCase()] ?? r.severity}
                </span>
              </div>
              {r.title && (
                <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--navy)", marginBottom: 4 }}>
                  {r.title}
                </div>
              )}
              <p style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>
                {r.prose}
              </p>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <IntelligenceMark />
      </div>
    </div>
  );
}
