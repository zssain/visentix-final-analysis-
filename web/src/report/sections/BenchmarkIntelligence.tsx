import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { CohortLabel } from "../CohortLabel";
import type { ReportSection } from "../types";

export function BenchmarkIntelligence({ content }: { content: ReportSection["content"] }) {
  const orgScore = content.org_score as number;
  const percentile = content.percentile as number;
  const data = [
    { name: "Your Score", value: orgScore },
    { name: "Peer Median", value: 50 },
    { name: "Top Quartile", value: 75 },
  ];

  return (
    <div data-testid="section-4" className="report-section">
      <h2>4. Benchmark Intelligence</h2>
      <p style={{ fontSize: "1.5em", fontWeight: "bold" }}>{percentile?.toFixed(1)}th percentile</p>
      <div style={{ width: "100%", height: 200 }} className="chart-container">
        <ResponsiveContainer>
          <BarChart data={data} isAnimationActive={false}>
            <XAxis dataKey="name" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#0f3460" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <CohortLabel size={content.cohort_size as number} date={content.cohort_date as string} />
    </div>
  );
}
