import type { ReportSection } from "../types";

interface Finding { id: string; domain: string; severity: string; score: number; confidence: string; }

export function FindingsTable({ content }: { content: ReportSection["content"] }) {
  const findings = (content.findings as Finding[]) ?? [];
  return (
    <div data-testid="section-6" className="report-section">
      <h2>6. Disclosure Findings</h2>
      <p>Total findings: {content.total as number}</p>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#f3f4f6" }}>
            <th style={th}>ID</th><th style={th}>Domain</th><th style={th}>Severity</th>
            <th style={th}>Score</th><th style={th}>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, i) => (
            <tr key={i}>
              <td style={td}>{f.id}</td><td style={td}>{f.domain}</td>
              <td style={td}><span className={`tier-${f.severity}`}>{f.severity}</span></td>
              <td style={td}>{f.score?.toFixed(1)}</td><td style={td}>{f.confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const th: React.CSSProperties = { border: "1px solid #d1d5db", padding: "8px 12px", textAlign: "left" };
const td: React.CSSProperties = { border: "1px solid #d1d5db", padding: "8px 12px" };
