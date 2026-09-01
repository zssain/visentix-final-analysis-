import { trendColor } from "../../lib/scoreBands";
import type { ReportSection } from "../types";
import { SectionHeading } from "../SectionHeading";

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
      <SectionHeading n={12} title="Trend & Emerging Risk" />

      {noPrior ? (
        <div className="rounded-lg border border-dashed border-[var(--provisional)] bg-[color-mix(in_oklab,var(--provisional)_8%,transparent)] px-4.5 py-3.5 text-sm text-muted-foreground">
          <strong>Baseline established.</strong> This is the first assessment for this organisation.
          Trend data will be available on the next assessment run.
        </div>
      ) : (
        <>
          {/* Sparkline + delta */}
          <div className="mb-4 flex flex-wrap items-center gap-5 rounded-lg border bg-muted/40 px-4.5 py-3.5">
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Score over time
              </div>
              <Sparkline data={trendData} />
              {trendData.length === 0 && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Trend data will appear after the next assessment snapshot.
                </div>
              )}
            </div>
            {trendDelta !== undefined && (
              <div>
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Delta vs last snapshot
                </div>
                {/* Direction is carried by the arrow AND the accessible label,
                    never by colour alone. */}
                <div
                  className="font-data text-2xl font-bold tabular-nums"
                  style={{ color: trendColor(trendDelta) }}
                  aria-label={`${isDeltaUp ? "Up" : "Down"} ${Math.abs(trendDelta).toFixed(1)} versus the last snapshot`}
                >
                  <span aria-hidden="true">{isDeltaUp ? "▲" : "▼"} {Math.abs(trendDelta).toFixed(1)}</span>
                </div>
              </div>
            )}
            <div className="flex-1">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Trend scores
              </div>
              <div className="font-data text-sm tabular-nums text-muted-foreground">
                {trendData.map((v, i) => (
                  <span key={i} className="mr-2">
                    {i > 0 && <span className="mr-2 text-border" aria-hidden="true">·</span>}
                    {v.toFixed(1)}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {note && (
            <p className="text-muted-foreground text-sm leading-relaxed">{note}</p>
          )}
        </>
      )}
    </div>
  );
}
