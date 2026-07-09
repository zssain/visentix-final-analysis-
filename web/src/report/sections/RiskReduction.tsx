import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

interface Priority {
  code: string;
  domain: string;
  effort: "low" | "medium" | "high";
  impact: "low" | "medium" | "high";
  description: string;
}

const EFFORT_COLOR: Record<string, string> = {
  low: "var(--teal)", medium: "var(--gold)", high: "var(--red)",
};
const IMPACT_COLOR: Record<string, string> = {
  low: "var(--warm-gray-dark)", medium: "var(--exec-blue)", high: "var(--navy)",
};

export function RiskReduction({ content }: { content: ReportSection["content"] }) {
  const highCount    = (content.high_count   as number | undefined) ?? 0;
  const mediumCount  = (content.medium_count as number | undefined) ?? 0;
  const priorities   = (content.priorities   as Priority[] | undefined) ?? [];
  const prose        = content.prose         as string | undefined;

  return (
    <div data-testid="section-10" className="report-section">
      <h2>10. Risk Reduction Priorities</h2>

      {/* Summary count row */}
      <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
        {[
          { label: "High Exposure", count: highCount, color: "var(--red)" },
          { label: "Elevated Exposure", count: mediumCount, color: "var(--gold)" },
        ].map(item => (
          <div key={item.label} style={{
            display: "flex", alignItems: "baseline", gap: 6,
            padding: "8px 16px",
            background: "var(--soft-white)", border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
          }}>
            <span style={{
              fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
              fontSize: "1.6rem", fontWeight: 700, color: item.color, lineHeight: 1,
            }}>{item.count}</span>
            <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: 600 }}>
              {item.label} findings
            </span>
          </div>
        ))}
      </div>

      {/* Prose */}
      {prose && (
        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 16 }}>
          {prose}
        </p>
      )}

      {/* Prioritised actions */}
      {priorities.length > 0 && (
        <>
          <div style={{
            fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.09em", color: "var(--text-muted)", marginBottom: 10,
          }}>
            Prioritised actions — ordered by impact × effort
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {priorities.map((p, i) => (
              <div key={i} style={{
                display: "flex", gap: 14, padding: "10px 14px",
                border: "1px solid var(--border)", borderRadius: "var(--radius)",
                background: "var(--bg-card)", alignItems: "flex-start",
              }}>
                {/* Rank */}
                <div style={{
                  width: 24, height: 24, borderRadius: "50%",
                  background: "var(--navy)", color: "white",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "0.7rem", fontWeight: 800, flexShrink: 0,
                }}>{i + 1}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3, flexWrap: "wrap" }}>
                    <span style={{
                      background: "var(--navy)", color: "white",
                      fontFamily: "var(--font-data)", fontSize: "0.7rem", fontWeight: 700,
                      padding: "2px 7px", borderRadius: 4, letterSpacing: "0.04em",
                    }}>{p.code}</span>
                    <span className="domain-eyebrow">{p.domain.replace(/_/g, " ")}</span>
                  </div>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    {p.description}
                  </p>
                </div>
                {/* Effort + Impact pills */}
                <div style={{ display: "flex", flexDirection: "column", gap: 4, flexShrink: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", width: 40 }}>Effort</span>
                    <div style={{
                      padding: "2px 8px", borderRadius: 4,
                      background: `${EFFORT_COLOR[p.effort]}18`,
                      color: EFFORT_COLOR[p.effort],
                      fontSize: "0.72rem", fontWeight: 700, textTransform: "capitalize",
                    }}>{p.effort}</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", width: 40 }}>Impact</span>
                    <div style={{
                      padding: "2px 8px", borderRadius: 4,
                      background: `${IMPACT_COLOR[p.impact]}18`,
                      color: IMPACT_COLOR[p.impact],
                      fontSize: "0.72rem", fontWeight: 700, textTransform: "capitalize",
                    }}>{p.impact}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <div style={{ marginTop: 14 }}>
        <IntelligenceMark />
      </div>
    </div>
  );
}
