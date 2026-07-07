/**
 * CustomerDashboard — Continuous Monitoring hero screen
 *
 * Layout per screens.md §2:
 *   Left:  Overall score + sparkline + delta · Domain scorecards (8)
 *   Right: Change feed (chronological) · Alert center
 *
 * [MOCK M-06] Sparkline data static — real: F-012 Trend outputs
 * [MOCK M-07] Change feed static — real: monitoring_event table
 * [MOCK M-08] Alert cards static — real: F-013 Alert Escalation
 * [MOCK M-09] Snapshot ID static — real: report_snapshot.id
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { AdvisorNote }      from "../../components/AdvisorNote";
import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { PageHeader }       from "../../components/PageHeader";
import { scoreBandColor, trendColor } from "../../lib/scoreBands";
import "../../components/furniture.css";

interface Assessment {
  notice_id: string;
  organization_id: string;
  notice_type: string;
  effective_date: string | null;
  organization: { name: string; domain: string | null; industry: string | null; size: string | null; geography: string | null } | null;
}

// ── Mock data (M-06, M-07, M-08, M-09) ────────────────────────────────────────
const MOCK_SNAPSHOT = "S-2041";
const MOCK_SCORE    = 41.3;
const MOCK_DELTA    = -3.0;
const MOCK_TREND    = [48, 46, 44, 47, 43, 44, 41];

const MOCK_DOMAIN_SCORES = [
  { domain: "Data Sharing",          score: 58, delta: -2 },
  { domain: "Tracking & Cookies",    score: 71, delta:  0 },
  { domain: "Consumer Rights",       score: 34, delta: -4 },
  { domain: "Cross-Border",          score: 62, delta:  1 },
  { domain: "Sensitive Data",        score: 47, delta:  0 },
  { domain: "Retention",             score: 29, delta: -1 },
  { domain: "Children & Teens",      score: 52, delta:  0 },
  { domain: "AI & Decisions",        score: 38, delta: -2 },
];

const MOCK_CHANGE_FEED = [
  { id: "cf-1", type: "score_moved",    label: "Overall score moved",     detail: "41.3 → 38.0", time: "2h ago", delta: -3 },
  { id: "cf-2", type: "notice_updated", label: "Privacy notice updated",  detail: "New section detected: AI & Decisions", time: "2h ago", delta: null },
  { id: "cf-3", type: "regulator",      label: "Regulator signal",        detail: "FTC — new enforcement action in data_sharing domain", time: "1d ago", delta: null },
  { id: "cf-4", type: "cohort",         label: "Cohort re-benchmarked",   detail: "n=30 peers updated", time: "3d ago", delta: null },
];

const MOCK_ALERTS = [
  {
    id: "alert-1", severity: "high", code: "TRK-007",
    title: "Third-Party Tracking Disclosure",
    domain: "tracking_cookies",
    advisorLede: "Tracking disclosure language presents a measurable exposure gap against cohort norms.",
    advisorBody: "The organisation's current tracking notice lacks specificity regarding third-party recipient categories and data retention limits. This falls below the 70th percentile of peer practice.",
    score: 71, percentile: 72, vci: 82,
  },
  {
    id: "alert-2", severity: "medium", code: "RT-003",
    title: "Retention Duration Absent",
    domain: "retention",
    advisorLede: "Retention language offers no bounded ceiling, creating a maturity gap relative to leading peer practice.",
    advisorBody: "The notice defers to 'legal requirements' without citing specific retention periods. This is below the 40th percentile of the assessed cohort.",
    score: 29, percentile: 31, vci: 75,
  },
];

// Inline SVG sparkline — colored by improvement (exposure falling = teal)
function Sparkline({ data, size = "sm" }: { data: number[]; size?: "sm" | "lg" }) {
  const w = size === "lg" ? 180 : 80;
  const h = size === "lg" ? 48 : 28;
  const pad = 3;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = data[data.length - 1], prev = data[data.length - 2];
  const color = trendColor(last - prev);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={size === "lg" ? 2.5 : 1.5}
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1].split(",")[0]} cy={pts[pts.length - 1].split(",")[1]}
        r={size === "lg" ? 4 : 2.5} fill={color} />
    </svg>
  );
}

function FeedIcon({ type }: { type: string }) {
  const icons: Record<string, string> = {
    score_moved:    "▲",
    notice_updated: "◉",
    regulator:      "⚖",
    cohort:         "◎",
  };
  return <span aria-hidden="true" style={{ fontSize: "0.85rem" }}>{icons[type] ?? "•"}</span>;
}

function AlertCard({ alert, expanded, onToggle }: {
  alert: typeof MOCK_ALERTS[number];
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{
      border: `1px solid ${alert.severity === "high" ? "rgba(248,113,113,0.3)" : "var(--border)"}`,
      borderRadius: "var(--radius)",
      overflow: "hidden",
    }}>
      <button
        style={{
          width: "100%", textAlign: "left",
          padding: "10px 14px",
          background: alert.severity === "high" ? "rgba(248,113,113,0.05)" : "var(--soft-white)",
          display: "flex", alignItems: "center", gap: 10,
          cursor: "pointer", border: "none",
        }}
        onClick={onToggle}
        aria-expanded={expanded}
        id={`alert-toggle-${alert.id}`}
      >
        <span className={`badge ${alert.severity === "high" ? "badge-high" : "badge-elevated"}`}>
          {alert.severity.toUpperCase()}
        </span>
        <span className="code-chip" style={{ fontSize: "0.7rem" }}>{alert.code}</span>
        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--navy)", flex: 1 }}>
          {alert.title}
        </span>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{expanded ? "↑" : "↓"}</span>
      </button>
      {expanded && (
        <div style={{ padding: "12px 14px" }}>
          <AdvisorNote
            findingCode={alert.code}
            title={alert.title}
            domain={alert.domain}
            status="draft"
            snapshotId={MOCK_SNAPSHOT}
            frozenDate="2026-07-07"
            exposureScore={alert.score}
            cohortPercentile={alert.percentile}
            vci={alert.vci}
            formulaId="F-008"
            formulaDesc="Blends regulatory, disclosure, and enforcement dimensions into a single compound risk indicator."
            cohortSize={30}
            cohortDate="2026-06-19"
            advisorLede={alert.advisorLede}
            advisorBody={alert.advisorBody}
            defaultView="advisor"
          />
        </div>
      )}
    </div>
  );
}

export function CustomerDashboard() {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);

  useEffect(() => {
    api.get("/assessments/")
      .then((data) => setAssessments(Array.isArray(data) ? data : []))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) return;
        setError("Failed to load assessments");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* ── Page header ── */}
      <PageHeader
        eyebrow="Monitor"
        title="Privacy Intelligence Monitor"
        description="Watches your assessed privacy notices and their peer benchmarks. Score changes, notice edits, and regulator signals appear here as they happen."
        actions={
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.78rem", fontWeight: 600, color: "var(--emerald)" }}>
            <span className="live-dot" /> Monitoring active
          </div>
        }
      />

      {/* [MOCK M-09] */}
      <div style={{ marginBottom: 20 }}>
        <ProvenanceRibbon
          snapshotId={MOCK_SNAPSHOT}
          frozenDate="2026-07-07"
          status="draft"
        />
      </div>

      {/* ── Main monitoring layout ── */}
      <div className="monitor-grid" style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, alignItems: "start" }}>

        {/* ── LEFT ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Overall score hero */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 24, flexWrap: "wrap" }}>
              <div>
                <div className="micro-label">
                  Overall Privacy Intelligence Score
                </div>
                <div style={{
                  fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                  fontSize: "3rem", fontWeight: 700, color: scoreBandColor(MOCK_SCORE),
                  lineHeight: 1.1,
                }}>
                  {MOCK_SCORE.toFixed(1)}
                </div>
                <div style={{
                  fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                  fontSize: "0.88rem", fontWeight: 700,
                  color: trendColor(MOCK_DELTA),
                  marginTop: 4,
                }}>
                  {MOCK_DELTA >= 0 ? "▲" : "▼"} {Math.abs(MOCK_DELTA).toFixed(1)} vs last snapshot
                </div>
              </div>
              <div>
                <div className="micro-label">
                  Trend {/* [MOCK M-06] */}
                </div>
                <Sparkline data={MOCK_TREND} size="lg" />
              </div>
            </div>
          </div>

          {/* Domain scorecards */}
          <div>
            <div className="section-label" style={{ marginBottom: 10 }}>Domain Scorecards</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
              {MOCK_DOMAIN_SCORES.map(ds => (
                <div key={ds.domain} className="card" style={{ padding: "12px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div className="micro-label" style={{ marginBottom: 3 }}>
                        {ds.domain}
                      </div>
                      <div style={{
                        fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                        fontSize: "1.5rem", fontWeight: 700, color: scoreBandColor(ds.score),
                      }}>
                        {ds.score}
                      </div>
                    </div>
                    {/* Delta only — one sparkline per screen (the hero); 8 mini-sparklines read as noise */}
                    <div style={{
                      fontFamily: "var(--font-data)", fontSize: "0.78rem", fontWeight: 700,
                      color: ds.delta !== 0 ? trendColor(ds.delta) : "var(--text-muted)",
                    }}>
                      {ds.delta === 0 ? "—" : `${ds.delta > 0 ? "▲" : "▼"}${Math.abs(ds.delta)}`}
                    </div>
                  </div>
                  {/* Score bar */}
                  <div style={{ height: 3, background: "var(--border)", borderRadius: 2, marginTop: 8, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${ds.score}%`, background: scoreBandColor(ds.score), borderRadius: 2 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Assessments list */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div className="card-head card-head-row">
              <div className="card-title">Active Assessments</div>
              <Link to="/intake" className="btn btn-sm btn-outline" id="new-assessment-btn">+ New Assessment</Link>
            </div>
            {loading ? (
              <div className="empty-state"><p>Loading assessments…</p></div>
            ) : error ? (
              <div className="empty-state"><h3>{error}</h3></div>
            ) : assessments.length === 0 ? (
              <div className="empty-state">
                <h3>No assessments yet</h3>
                <p style={{ marginBottom: 12 }}>Submit a privacy notice to begin monitoring</p>
                <Link to="/intake" className="btn btn-primary btn-sm">Start Intake →</Link>
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Organisation</th>
                    <th>Industry</th>
                    <th>Type</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {assessments.slice(0, 8).map((a) => (
                    <tr key={a.notice_id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{a.organization?.name ?? "—"}</div>
                        {a.organization?.domain && (
                          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{a.organization.domain}</div>
                        )}
                      </td>
                      <td style={{ textTransform: "capitalize", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                        {a.organization?.industry ?? "—"}
                      </td>
                      <td>
                        <span className={`badge ${a.notice_type === "live_assessment" ? "badge-teal" : "badge-moderate"}`}>
                          {a.notice_type?.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td>
                        <Link to={`/reports/${a.notice_id}`} className="btn btn-outline btn-xs">
                          Report →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ── RIGHT ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>

          {/* Change feed [MOCK M-07] */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div className="card-head">
              <div className="card-title">Change Feed<span className="mock-badge">MOCK M-07</span></div>
            </div>
            <div style={{ padding: "8px 0" }}>
              {MOCK_CHANGE_FEED.map((ev, i) => (
                <div key={ev.id} style={{
                  padding: "10px 16px",
                  borderBottom: i < MOCK_CHANGE_FEED.length - 1 ? "1px solid var(--border)" : "none",
                  display: "flex", gap: 10, alignItems: "flex-start",
                }}>
                  {/* Left stripe */}
                  <div style={{
                    width: 2, borderRadius: 1, alignSelf: "stretch", flexShrink: 0,
                    background: ev.type === "score_moved" ? trendColor(ev.delta ?? 0) : "var(--border)",
                  }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                      <FeedIcon type={ev.type} />
                      <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--navy)" }}>{ev.label}</span>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{ev.detail}</div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 3 }}>{ev.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Alert center [MOCK M-08] */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div className="card-head" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div className="card-title">Alert Center<span className="mock-badge">MOCK M-08</span></div>
              <span className="badge badge-high" style={{ fontSize: "0.65rem" }}>
                {MOCK_ALERTS.filter(a => a.severity === "high").length} HIGH
              </span>
            </div>
            <div style={{ padding: "10px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {MOCK_ALERTS.map(a => (
                  <AlertCard
                    key={a.id}
                    alert={a}
                    expanded={expandedAlert === a.id}
                    onToggle={() => setExpandedAlert(expandedAlert === a.id ? null : a.id)}
                  />
                ))}
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Mobile: collapse right panel below left at 900px via inline responsive */}
      <style>{`
        @media (max-width: 900px) {
          .monitor-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
