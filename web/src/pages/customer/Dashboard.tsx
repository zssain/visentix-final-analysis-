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

      <div className="monitor-grid" style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, alignItems: "start" }}>

        {/* ── LEFT ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Overall score */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 24, flexWrap: "wrap" }}>
              <div>
                <div className="micro-label">Overall Privacy Intelligence Score</div>
                {overallScore != null ? (
                  <>
                    {/* Maturity polarity: higher = better; color agrees with the band label
                        ("Deficient" is never teal) — design-system §2 v1.3 */}
                    <div style={{
                      fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                      fontSize: "3rem", fontWeight: 700, color: maturityBandColor(overallScore),
                      lineHeight: 1.1,
                    }}>
                      {overallScore.toFixed(1)}
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: 4 }}>
                      <span style={{ fontWeight: 700, color: maturityBandColor(overallScore) }}>{maturityBand(overallScore)}</span>
                      {" · "}
                      <span title={VCI_TITLE} style={{ cursor: "help", textDecoration: "underline dotted" }}>
                        VCI {((stats?.overall_confidence ?? 0) * 100).toFixed(0)} · {vciBand((stats?.overall_confidence ?? 0) * 100)} confidence
                      </span>
                    </div>
                    <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginTop: 4 }}>
                      0–100, benchmarked against your peer cohort · higher is better
                    </div>
                  </>
                ) : (
                  <div style={{ fontSize: "1.2rem", color: "var(--text-muted)", marginTop: 8 }}>
                    No scores computed yet. Submit an assessment via Intake to see real scores.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Domain scorecards — from real data */}
          {stats && stats.domain_scores.length > 0 && (
            <div>
              <div className="section-label" style={{ marginBottom: 4 }}>Score Breakdown</div>
              {/* Legend: color = judgement, per design-system §2 v1.3 */}
              <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: 10 }}>
                Color shows standing — <span style={{ color: "var(--teal)", fontWeight: 700 }}>teal good</span> ·{" "}
                <span style={{ color: "#8a6a2b", fontWeight: 700 }}>gold developing</span> ·{" "}
                <span style={{ color: "#b91c1c", fontWeight: 700 }}>red needs attention</span>.
                Each metric notes which direction is better.
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
                {stats.domain_scores.map(ds => {
                  const polarity = metricPolarity(ds.domain);
                  const hasScore = ds.score > 0;
                  const color = hasScore ? bandColor(ds.score, polarity) : "var(--text-muted)";
                  return (
                    <div key={ds.object_type} className="card" style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <div className="micro-label" style={{ marginBottom: 3 }}>
                            {ds.domain}
                            {polarity && (
                              <span style={{ fontWeight: 500, textTransform: "none", letterSpacing: 0, color: "var(--text-muted)", marginLeft: 6 }}>
                                · {DIRECTION_HINT[polarity]}
                              </span>
                            )}
                          </div>
                          <div style={{
                            fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums",
                            fontSize: "1.5rem", fontWeight: 700, color,
                          }}>
                            {hasScore ? ds.score.toFixed(1) : "—"}
                          </div>
                        </div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", cursor: "help", textDecoration: "underline dotted", textAlign: "right" }} title={VCI_TITLE}>
                          VCI {((ds.confidence || 0) * 100).toFixed(0)}
                          <div style={{ fontSize: "0.66rem" }}>{vciBand((ds.confidence || 0) * 100)} confidence</div>
                        </div>
                      </div>
                      <div style={{ height: 3, background: "var(--border)", borderRadius: 2, marginTop: 8, overflow: "hidden" }}>
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

        {/* ── RIGHT ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>

          {/* Stats */}
          <div className="card" style={{ padding: "16px 18px" }}>
            <div className="card-title" style={{ marginBottom: 12 }}>Pipeline Stats</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <span style={{ color: "var(--text-muted)" }}>Assessments</span>
                <span style={{ fontWeight: 700 }}>{stats?.assessment_count ?? 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <span style={{ color: "var(--text-muted)" }}>Findings</span>
                <span style={{ fontWeight: 700 }}>{stats?.finding_count ?? 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <span style={{ color: "var(--text-muted)" }}>High exposure</span>
                <span style={{ fontWeight: 700, color: "var(--red)" }}>{stats?.high_findings ?? 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                <span style={{ color: "var(--text-muted)" }}>Elevated exposure</span>
                <span style={{ fontWeight: 700, color: "var(--gold)" }}>{stats?.medium_findings ?? 0}</span>
              </div>
            </div>
          </div>

          {/* Training stats */}
          {stats?.training_stats && (
            <div className="card" style={{ padding: "16px 18px" }}>
              <div className="card-title" style={{ marginBottom: 12 }}>Review Activity</div>
              <div style={{ display: "flex", gap: 16, fontSize: "0.85rem" }}>
                <span style={{ color: "var(--teal)", fontWeight: 700 }}>✓ {stats.training_stats.confirmed}</span>
                <span style={{ color: "var(--exec-blue)", fontWeight: 700 }}>✎ {stats.training_stats.edited}</span>
                <span style={{ color: "var(--red)", fontWeight: 700 }}>✕ {stats.training_stats.dismissed}</span>
              </div>
            </div>
          )}

          {/* Snapshot info */}
          {stats?.snapshot?.id && (
            <div className="card" style={{ padding: "16px 18px" }}>
              <div className="card-title" style={{ marginBottom: 8 }}>Latest Snapshot</div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                <div>{stats.snapshot.id.slice(0, 12)}</div>
                <div>{stats.snapshot.date}</div>
                {stats.snapshot.benchmark_population_version && (
                  <div>Population v{stats.snapshot.benchmark_population_version}</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .monitor-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
