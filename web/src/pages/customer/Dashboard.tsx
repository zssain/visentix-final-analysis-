/**
 * CustomerDashboard — Real data from /findings/dashboard-stats + /assessments/
 *
 * No mock data. All scores, findings, and stats come from the backend.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { PageHeader }       from "../../components/PageHeader";
import { MonitoringHero }   from "./MonitoringHero";
import { bandColor, maturityBandColor, maturityBand, metricPolarity, vciBand } from "../../lib/scoreBands";

/** Plain-language VCI explainer — shown wherever a VCI number appears. */
const VCI_TITLE = "Visentix Confidence Index (0–100): how much weight to give this figure — reflects cohort size, source quality, and classification certainty.";

const DIRECTION_HINT: Record<string, string> = {
  maturity: "higher is better",
  exposure: "lower is better",
};
import "../../components/furniture.css";

interface Assessment {
  notice_id: string;
  organization_id: string;
  notice_type: string;
  effective_date: string | null;
  organization: { name: string; domain: string | null; industry: string | null; size: string | null; geography: string | null } | null;
}

interface DashboardStats {
  overall_score: number | null;
  overall_confidence: number;
  domain_scores: { domain: string; object_type: string; score: number; confidence: number }[];
  finding_count: number;
  high_findings: number;
  medium_findings: number;
  assessment_count: number;
  snapshot: { id: string | null; date: string | null; benchmark_population_version: number | null };
  training_stats: { confirmed: number; edited: number; dismissed: number };
}

export function CustomerDashboard() {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/assessments/").catch(() => []),
      api.get("/findings/dashboard-stats").catch(() => null),
    ]).then(([assessData, statsData]) => {
      setAssessments(Array.isArray(assessData) ? assessData : []);
      setStats(statsData as DashboardStats | null);
    }).catch((err) => {
      if (err instanceof ApiError && err.status === 401) return;
      setError("Failed to load dashboard data");
    }).finally(() => setLoading(false));
  }, []);

  const overallScore = stats?.overall_score ?? null;
  const snapshotId = stats?.snapshot?.id ?? null;
  const snapshotDate = stats?.snapshot?.date ?? "";

  return (
    <div>
      <PageHeader
        eyebrow="Monitor"
        title="Privacy Intelligence Monitor"
        description="Real-time privacy intelligence across all assessed notices. Every number comes from the scoring pipeline — nothing is mocked."
        actions={
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.78rem", fontWeight: 600, color: "var(--emerald)" }}>
            <span className="live-dot" /> Live data
          </div>
        }
      />

      {snapshotId && (
        <div style={{ marginBottom: 20 }}>
          <ProvenanceRibbon
            snapshotId={snapshotId}
            frozenDate={snapshotDate}
            status="approved"
          />
        </div>
      )}

      {/* Exposure counts as a compact labelled stat row in the primary scan path,
          not a talkative side card (DDR-011 "earn your place"). Real values only —
          an absent stat shows an em dash, never a zero standing in for unknown. */}
      {stats && (
        <div className="stat-row">
          <div className="stat-cell">
            <span className="stat-key">Assessments</span>
            <span className="stat-val">{stats.assessment_count ?? "—"}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-key">Findings</span>
            <span className="stat-val">{stats.finding_count ?? "—"}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-key">High exposure</span>
            <span className="stat-val" style={{ color: "var(--bad)" }}>{stats.high_findings ?? "—"}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-key">Elevated exposure</span>
            <span className="stat-val" style={{ color: "var(--mid)" }}>{stats.medium_findings ?? "—"}</span>
          </div>
        </div>
      )}

      <div className="monitor-grid" style={{ display: "flex", flexDirection: "column", gap: 20, alignItems: "stretch" }}>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* M-06/07/08: continuous-monitoring hero. Renders nothing at all while
              every monitoring endpoint is unpopulated — F07 surfacing rule. */}
          <MonitoringHero />

          {/* Overall score — the BAND leads, the number follows (design-system §2).
              "Developing" is what a reader can act on; 71.7 is not. The figure is
              kept, never removed: it sits beside the band and in full lineage. */}
          <div className="card" style={{ padding: "16px 20px" }}>
            <div className="micro-label">Overall Privacy Intelligence</div>
            {overallScore != null ? (
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginTop: 6 }}>
                <span style={{
                  fontSize: "1.7rem", fontWeight: 700, lineHeight: 1.1,
                  color: maturityBandColor(overallScore),
                }}>
                  {maturityBand(overallScore)}
                </span>
                <span style={{
                  fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                  fontSize: "1rem", fontWeight: 600, color: "var(--text-secondary)",
                }}>
                  {overallScore.toFixed(1)}<span style={{ color: "var(--text-muted)", fontWeight: 500 }}>/100</span>
                </span>
                <span
                  title={VCI_TITLE}
                  style={{ fontSize: "0.74rem", color: "var(--text-muted)", cursor: "help", textDecoration: "underline dotted" }}
                >
                  {vciBand((stats?.overall_confidence ?? 0) * 100)} confidence
                </span>
                <span style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                  benchmarked against your peer cohort · higher is better
                </span>
              </div>
            ) : (
              <div style={{ fontSize: "0.95rem", color: "var(--text-muted)", marginTop: 6 }}>
                No scores computed yet. Submit an assessment via Intake to see real scores.
              </div>
            )}
          </div>

          {/* Domain scorecards — from real data */}
          {stats && stats.domain_scores.length > 0 && (
            <div>
              <div className="section-label" style={{ marginBottom: 4 }}>Score Breakdown</div>
              {/* Legend: color = judgement, per design-system §2 v1.6 (traffic light) */}
              <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: 10 }}>
                <span style={{ color: "var(--good)", fontWeight: 700 }}>Green good</span> ·{" "}
                <span style={{ color: "var(--mid)", fontWeight: 700 }}>yellow needs attention</span> ·{" "}
                <span style={{ color: "var(--bad)", fontWeight: 700 }}>red poor</span>. Each metric notes which direction is better.
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(215px, 1fr))", gap: 10 }}>
                {stats.domain_scores.map(ds => {
                  const polarity = metricPolarity(ds.domain);
                  const hasScore = ds.score > 0;
                  const color = hasScore ? bandColor(ds.score, polarity) : "var(--text-muted)";
                  return (
                    /* Compact tile: name + direction, figure, confidence as one quiet
                       chip rather than two repeated lines on every card (DDR-011). */
                    <div key={ds.object_type} className="card" style={{ padding: "10px 13px" }}>
                      <div className="micro-label" style={{ marginBottom: 4 }}>
                        {ds.domain}
                        {polarity && (
                          <span style={{ fontWeight: 500, textTransform: "none", letterSpacing: 0, color: "var(--text-muted)", marginLeft: 6 }}>
                            · {DIRECTION_HINT[polarity]}
                          </span>
                        )}
                      </div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                        <span style={{
                          fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                          fontSize: "1.25rem", fontWeight: 700, color, lineHeight: 1.15,
                        }}>
                          {hasScore ? ds.score.toFixed(1) : "—"}
                        </span>
                        <span
                          title={VCI_TITLE}
                          style={{ fontSize: "0.68rem", color: "var(--text-muted)", cursor: "help", textDecoration: "underline dotted", marginLeft: "auto" }}
                        >
                          {vciBand((ds.confidence || 0) * 100).toLowerCase()} conf.
                        </span>
                      </div>
                      <div style={{ height: 3, background: "var(--border)", borderRadius: 2, marginTop: 7, overflow: "hidden" }}>
                        {hasScore && (
                          <div style={{ height: "100%", width: `${Math.min(ds.score, 100)}%`, background: color, borderRadius: 2 }} />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Assessments list */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div className="card-head card-head-row">
              <div className="card-title">Active Assessments ({assessments.length})</div>
              <Link to="/intake" className="btn btn-sm btn-outline" id="new-assessment-btn">+ New Assessment</Link>
            </div>
            {loading ? (
              <div className="empty-state"><p>Loading assessments...</p></div>
            ) : error ? (
              <div className="empty-state"><h3>{error}</h3></div>
            ) : assessments.length === 0 ? (
              <div className="empty-state">
                <h3>No assessments yet</h3>
                <p style={{ marginBottom: 12 }}>Submit a privacy notice to begin</p>
                <Link to="/intake" className="btn btn-primary btn-sm">Start Intake</Link>
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
                  {assessments.slice(0, 20).map((a) => (
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
                          Report
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

      </div>

      <style>{`
        .stat-row {
          display: flex;
          flex-wrap: wrap;
          gap: 28px;
          padding: 14px 18px;
          margin-bottom: 20px;
          background: var(--surface, #fff);
          border: 1px solid var(--border);
          border-radius: var(--radius);
        }
        .stat-cell { display: flex; flex-direction: column; gap: 2px; min-width: 92px; }
        .stat-key {
          font-size: 0.68rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--text-muted);
        }
        .stat-val {
          font-family: var(--font-data);
          font-variant-numeric: tabular-nums;
          font-size: 1.4rem;
          font-weight: 700;
          line-height: 1.1;
        }
        @media (max-width: 640px) {
          .stat-row { gap: 18px 24px; }
        }
      `}</style>
    </div>
  );
}
