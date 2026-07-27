/**
 * MonitoringHero — F07 continuous-monitoring surface (M-06 / M-07 / M-08).
 *
 * Real data only, from the three org-scoped monitoring endpoints. Deltas are
 * F-012 outputs (never fabricated); a single-snapshot org shows an explicit
 * baseline state. The change feed leads score moves with from→to numbers, never
 * prose diffs. Alerts surface stored F-013 escalations joined to *resolved*
 * enforcement only — unresolved enforcement never appears here.
 */
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { trendColor } from "../../lib/scoreBands";

const VCI_TITLE =
  "Visentix Confidence Index (0–100): how much weight to give this figure.";

interface TrendPoint {
  snapshot_id: string;
  date: string;
  overall: number | null;
  domains: Record<string, number>;
  vci: number | null;
}
interface TrendDelta {
  from: number | null;
  to: number | null;
  delta_pct: number;
  formula_version_id: string;
  reason?: string;
}
interface TrendResponse {
  state: "no_history" | "baseline_established" | "populated";
  series: TrendPoint[];
  deltas: { overall: TrendDelta; domains: Record<string, TrendDelta> } | null;
  formula_version_id?: string;
}
interface MonEvent {
  event_id: string;
  type: string;
  raw_trigger_type: string;
  severity: string | null;
  source_url: string;
  occurred_at: string;
  from?: string;
  to?: string;
}
interface EventsResponse {
  state: "no_events" | "populated";
  events: MonEvent[];
}
interface Alert {
  alert_id: string;
  escalation_score: number | null;
  severity: string | null;
  formula_version_id: string;
  vci: number | null;
  snapshot_id: string | null;
  enforcement_refs: {
    enforcement_id: string;
    entity_name: string;
    regulator_id: string | null;
    official_url: string | null;
    resolution_status: string;
  }[];
}
interface AlertsResponse {
  state: "no_alerts" | "populated";
  alerts: Alert[];
}

function Sparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null;
  const w = 160, h = 40, pad = 4;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x},${y}`;
  });
  // Exposure/maturity polarity of the overall score: higher = better (maturity).
  const color = trendColor(data[data.length - 1] - data[data.length - 2], "maturity");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline points={pts.join(" ")} fill="none" stroke={color}
        strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1].split(",")[0]}
        cy={pts[pts.length - 1].split(",")[1]} r={3} fill={color} />
    </svg>
  );
}

function fmtType(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function MonitoringHero() {
  const [trend, setTrend] = useState<TrendResponse | null>(null);
  const [events, setEvents] = useState<EventsResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Customer role → endpoints auto-scope to the caller's org (no org_id needed).
    Promise.all([
      api.get("/api/monitoring/trend").catch(() => null),
      api.get("/api/monitoring/events").catch(() => null),
      api.get("/api/monitoring/alerts").catch(() => null),
    ]).then(([t, e, a]) => {
      setTrend(t as TrendResponse);
      setEvents(e as EventsResponse);
      setAlerts(a as AlertsResponse);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return null;

  const series = trend?.series ?? [];
  const overallVals = series.map(s => s.overall).filter((v): v is number => v != null);
  const overallDelta = trend?.deltas?.overall ?? null;
  const isBaseline = trend?.state === "baseline_established";

  return (
    <div className="card" style={{ padding: 20 }} data-testid="monitoring-hero">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div className="card-title">Continuous Monitoring</div>
        <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          Trend · change feed · alerts
        </span>
      </div>

      {/* ── M-06: trend sparkline + F-012 delta ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 20, flexWrap: "wrap" }}>
        {overallVals.length >= 2 ? (
          <>
            <Sparkline data={overallVals} />
            {overallDelta && (
              <div>
                <div className="tabular" style={{
                  fontSize: "1.1rem", fontWeight: 700,
                  color: trendColor(overallDelta.delta_pct, "maturity"),
                }}>
                  {overallDelta.from} → {overallDelta.to}
                  <span style={{ fontSize: "0.85rem", marginLeft: 8 }}>
                    ({overallDelta.delta_pct >= 0 ? "▲" : "▼"} {Math.abs(overallDelta.delta_pct)}%)
                  </span>
                </div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                  F-012 trend · {overallDelta.formula_version_id}
                </div>
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            {isBaseline
              ? "Baseline established — trend appears after your next assessment."
              : "No trend history yet. Submit an assessment to begin monitoring."}
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }} className="mon-hero-grid">
        {/* ── M-07: change feed ── */}
        <div>
          <div className="section-label" style={{ marginBottom: 8 }}>Change Feed</div>
          {events && events.events.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, borderLeft: "2px solid var(--border)", paddingLeft: 12 }}>
              {events.events.slice(0, 6).map(ev => (
                <div key={ev.event_id} style={{ fontSize: "0.78rem" }}>
                  <div style={{ fontWeight: 600, color: "var(--navy)" }}>
                    {fmtType(ev.type)}
                    {ev.severity && (
                      <span style={{ fontSize: "0.66rem", marginLeft: 6, color: "var(--text-muted)" }}>
                        · {ev.severity}
                      </span>
                    )}
                  </div>
                  {ev.type === "score_moved" && ev.from != null && (
                    <div className="tabular" style={{ color: "var(--text-secondary)" }}>
                      {ev.from} → {ev.to}
                    </div>
                  )}
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                    {(ev.occurred_at || "").slice(0, 10)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              No changes detected. Your monitored notices are stable.
            </div>
          )}
        </div>

        {/* ── M-08: alert center (F-013) ── */}
        <div>
          <div className="section-label" style={{ marginBottom: 8 }}>Alert Center</div>
          {alerts && alerts.alerts.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {alerts.alerts.slice(0, 5).map(al => (
                <div key={al.alert_id} className="card" style={{ padding: "10px 12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span style={{ fontWeight: 700, fontSize: "0.8rem", color: "var(--navy)" }}>
                      {al.severity ? fmtType(al.severity) : "Escalation"}
                    </span>
                    <span className="tabular" style={{ fontSize: "0.72rem", color: "var(--text-muted)", cursor: "help" }} title={VCI_TITLE}>
                      VCI {al.vci ?? "—"}
                    </span>
                  </div>
                  <div className="tabular" style={{ fontSize: "0.74rem", color: "var(--text-secondary)" }}>
                    F-013 {al.escalation_score ?? "—"} · {al.formula_version_id}
                  </div>
                  {al.enforcement_refs.length > 0 && (
                    <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 4 }}>
                      Related resolved matters: {al.enforcement_refs.map(e => e.entity_name).join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              No active alerts.
            </div>
          )}
        </div>
      </div>

      <style>{`
        @media (max-width: 640px) {
          .mon-hero-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
