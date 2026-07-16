import { trendColor } from "../../lib/scoreBands";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import type { ReportSection } from "../types";

// Fallback trend data when F-012 Trend Delta has not yet produced real snapshots
const FALLBACK_TREND: number[] = [];

function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const w = 120, h = 32, pad = 4;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x},${y}`;
  });
  const last = data[data.length - 1];
  const prev = data[data.length - 2];
  // Colored by improvement: exposure falling = teal
  const color = trendColor(last - prev);

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={pts[pts.length - 1].split(",")[0]}
        cy={pts[pts.length - 1].split(",")[1]}
        r={3}
        fill={color}
      />
    </svg>
  );
}

export function TrendPanel({ content }: { content: ReportSection["content"] }) {
  const note          = content.note          as string | undefined;
  const noPrior       = content.no_prior_history as boolean | undefined;
  const trendDelta    = content.trend_delta   as number | undefined;
  const trendData     = (content.trend_data   as number[] | undefined) ?? FALLBACK_TREND;
  const isDeltaUp     = (trendDelta ?? 0) >= 0;

  return (
    <div data-testid="section-12" className="report-section">
      <h2>12. Trend &amp; Emerging Risk</h2>

      {noPrior ? (
        <div style={{
          background: "rgba(200,164,106,0.08)", border: "1px dashed var(--gold)",
          borderRadius: "var(--radius)", padding: "14px 18px",
          color: "var(--text-secondary)", fontSize: "0.88rem",
        }}>
          <strong>Baseline established.</strong> This is the first assessment for this organisation.
          Trend data will be available on the next assessment run.
        </div>
      ) : (
        <>
          {/* Sparkline + delta */}
          <div style={{
            display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap",
            background: "var(--soft-white)", border: "1px solid var(--border)",
            borderRadius: "var(--radius)", padding: "14px 18px", marginBottom: 16,
          }}>
            <div>
              <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>
                Score over time
              </div>
              <Sparkline data={trendData} />
              {trendData.length === 0 && (
                <div style={{ marginTop: 4, fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  Trend data will appear after the next assessment snapshot.
                </div>
              )}
            </div>
            {trendDelta !== undefined && (
              <div>
                <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>
                  Delta vs last snapshot
                </div>
                <div style={{
                  fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                  fontSize: "1.6rem", fontWeight: 700,
                  color: trendColor(trendDelta),
                }}>
                  {isDeltaUp ? "▲" : "▼"} {Math.abs(trendDelta).toFixed(1)}
                </div>
              </div>
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 4 }}>
                Trend scores
              </div>
              <div style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                {trendData.map((v, i) => (
                  <span key={i} style={{ marginRight: 8 }}>
                    {i > 0 && <span style={{ color: "var(--border)", marginRight: 8 }}>·</span>}
                    {v.toFixed(1)}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {note && (
            <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", lineHeight: 1.7 }}>{note}</p>
          )}
        </>
      )}
      {/* DDR-007: every report section carries the mark */}
      <div style={{ marginTop: 12 }}><IntelligenceMark /></div>
    </div>
  );
}
