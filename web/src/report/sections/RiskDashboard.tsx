import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { VciBadge } from "../VciBadge";
import type { ReportSection } from "../types";

const COLORS: Record<string, string> = { high: "#dc2626", elevated: "#f59e0b", moderate: "#3b82f6", low: "#22c55e" };

function tierColor(score: number): string {
  if (score >= 75) return COLORS.high;
  if (score >= 50) return COLORS.elevated;
  if (score >= 25) return COLORS.moderate;
  return COLORS.low;
}

export function RiskDashboard({ content }: { content: ReportSection["content"] }) {
  const metrics = [
    { name: "Overall", value: content.overall_intelligence as number },
    { name: "Regulatory", value: content.regulatory_exposure as number },
    { name: "Disclosure", value: content.disclosure_maturity as number },
    { name: "Transparency", value: content.transparency as number },
    { name: "AI Transparency", value: content.ai_transparency as number },
    { name: "Compound Risk", value: content.compound_risk as number },
  ];

  return (
    <div data-testid="section-3" className="report-section">
      <h2>3. Risk Dashboard</h2>
      <div style={{ width: "100%", height: 300 }} className="chart-container">
        <ResponsiveContainer>
          <BarChart data={metrics} layout="vertical" margin={{ left: 100 }}>
            <XAxis type="number" domain={[0, 100]} />
            <YAxis type="category" dataKey="name" width={100} />
            <Tooltip />
            <Bar dataKey="value" isAnimationActive={false}>
              {metrics.map((m, i) => (
                <Cell key={i} fill={tierColor(m.value ?? 0)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p>VCI: {(content.vci_score as number)?.toFixed(1)} <VciBadge label={content.vci_label as string} /></p>
    </div>
  );
}
