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
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatTile } from "@/components/ui/stat-tile";
import { AnimatedNumber } from "@/components/ui/animated-number";

/** Plain-language VCI explainer — shown wherever a VCI number appears. */
const VCI_TITLE =
  "Confidence (0–100): how much weight to give this figure — reflects cohort size, source quality, and classification certainty.";

const DIRECTION_HINT: Record<string, string> = {
  maturity: "higher is better",
  exposure: "lower is better",
};
import { StatusDot } from "@/components/StatusDot";

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
            <StatusDot /> Live data
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
        <Card className="mb-5 py-4">
          <CardContent className="flex flex-wrap gap-x-10 gap-y-4">
            <StatTile label="Assessments" value={stats.assessment_count} />
            <StatTile label="Findings"    value={stats.finding_count} />
            <StatTile label="High exposure"     value={stats.high_findings}   tone="bad" />
            <StatTile label="Elevated exposure" value={stats.medium_findings} tone="mid" />
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-5">

          {/* M-06/07/08: continuous-monitoring hero. Renders nothing at all while
              every monitoring endpoint is unpopulated — F07 surfacing rule. */}
          <MonitoringHero />

          {/* Overall score — the BAND leads, the number follows (design-system §2).
              "Developing" is what a reader can act on; 71.7 is not. The figure is
              kept, never removed: it sits beside the band and in full lineage. */}
          <Card className="py-4">
            <CardContent className="flex flex-col gap-1.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Overall Privacy Intelligence
              </div>
              {overallScore != null ? (
                <div className="flex flex-wrap items-baseline gap-3">
                  <span
                    className="text-3xl font-bold leading-tight"
                    style={{ color: maturityBandColor(overallScore) }}
                  >
                    {maturityBand(overallScore)}
                  </span>
                  <span className="font-data text-base font-semibold text-muted-foreground">
                    <AnimatedNumber value={overallScore} decimals={1} />
                    <span className="font-medium">/100</span>
                  </span>
                  <span
                    title={VCI_TITLE}
                    className="text-xs text-muted-foreground cursor-help underline decoration-dotted"
                  >
                    {vciBand((stats?.overall_confidence ?? 0) * 100)} confidence
                  </span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    benchmarked against your peer cohort · higher is better
                  </span>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  No scores computed yet. Submit an assessment via Intake to see real scores.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Domain scorecards — from real data */}
          {stats && stats.domain_scores.length > 0 && (
            <section>
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Score Breakdown
              </h2>
              {/* Legend: colour = judgement, and ONLY judgement (OD-13 traffic light) */}
              <p className="mt-1 mb-2.5 text-xs text-muted-foreground">
                <span className="font-bold text-[var(--standing-good)]">Green good</span> ·{" "}
                <span className="font-bold text-[var(--standing-mid)]">yellow needs attention</span> ·{" "}
                <span className="font-bold text-[var(--standing-bad)]">red poor</span>. Each metric notes which direction is better.
              </p>
              <div className="grid gap-2.5 [grid-template-columns:repeat(auto-fit,minmax(215px,1fr))]">
                {stats.domain_scores.map(ds => {
                  const polarity = metricPolarity(ds.domain);
                  const hasScore = ds.score > 0;
                  const color = hasScore ? bandColor(ds.score, polarity) : "var(--muted-foreground)";
                  return (
                    /* Compact tile: name + direction, figure, confidence as one quiet
                       chip rather than two repeated lines on every card (DDR-011). */
                    <Card key={ds.object_type} className="gap-0 py-3">
                      <CardContent className="px-3.5">
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                          {ds.domain}
                          {polarity && (
                            <span className="ml-1.5 font-medium normal-case tracking-normal">
                              · {DIRECTION_HINT[polarity]}
                            </span>
                          )}
                        </div>
                        <div className="flex items-baseline gap-2">
                          <span
                            className="font-data text-xl font-bold leading-tight"
                            style={{ color }}
                          >
                            {hasScore ? <AnimatedNumber value={ds.score} decimals={1} /> : "—"}
                          </span>
                          <span
                            title={VCI_TITLE}
                            className="ml-auto text-[11px] text-muted-foreground cursor-help underline decoration-dotted"
                          >
                            {vciBand((ds.confidence || 0) * 100).toLowerCase()} conf.
                          </span>
                        </div>
                        {/* Meter, not a chart: one value against a fixed 0-100 scale. */}
                        <div
                          className="mt-1.5 h-[3px] overflow-hidden rounded-sm bg-border"
                          role="img"
                          aria-label={hasScore ? `${ds.domain} ${ds.score.toFixed(1)} out of 100` : `${ds.domain} not recorded`}
                        >
                          {hasScore && (
                            <div
                              className="h-full rounded-sm transition-[width] duration-700 ease-out motion-reduce:transition-none"
                              style={{ width: `${Math.min(ds.score, 100)}%`, background: color }}
                            />
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </section>
          )}

          {/* Assessments list */}
          <Card className="gap-0 overflow-hidden py-0">
            <CardHeader className="flex-row items-center border-b py-4">
              <CardTitle>Active Assessments ({assessments.length})</CardTitle>
              <CardAction>
                <Button asChild variant="outline" size="sm" id="new-assessment-btn">
                  <Link to="/intake">+ New Assessment</Link>
                </Button>
              </CardAction>
            </CardHeader>
            {loading ? (
              <div className="px-6 py-10 text-center text-sm text-muted-foreground">Loading assessments...</div>
            ) : error ? (
              <div className="px-6 py-10 text-center text-sm text-[var(--standing-bad)]">{error}</div>
            ) : assessments.length === 0 ? (
              <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                <h3 className="text-base font-semibold">No assessments yet</h3>
                <p className="text-sm text-muted-foreground">Submit a privacy notice to begin</p>
                <Button asChild size="sm"><Link to="/intake">Start Intake</Link></Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40 text-left">
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Organisation</th>
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Industry</th>
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Type</th>
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assessments.slice(0, 20).map((a) => (
                      <tr key={a.notice_id} className="border-b last:border-0 hover:bg-muted/40 transition-colors">
                        <td className="px-6 py-3">
                          <div className="font-semibold">{a.organization?.name ?? "—"}</div>
                          {a.organization?.domain && (
                            <div className="text-xs text-muted-foreground">{a.organization.domain}</div>
                          )}
                        </td>
                        <td className="px-6 py-3 capitalize text-muted-foreground">{a.organization?.industry ?? "—"}</td>
                        <td className="px-6 py-3">
                          <Badge variant={a.notice_type === "live_assessment" ? "verified" : "provisional"}>
                            {a.notice_type?.replace(/_/g, " ")}
                          </Badge>
                        </td>
                        <td className="px-6 py-3">
                          <Button asChild variant="outline" size="sm">
                            <Link to={`/reports/${a.notice_id}`}>Report</Link>
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>


    </div>
  );
}
