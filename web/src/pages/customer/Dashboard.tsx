/**
 * CustomerDashboard — Real data from /findings/dashboard-stats + /assessments/
 *
 * No mock data. All scores, findings, and stats come from the backend.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { ReportCard } from "../../components/ReportCard";
import { SnapshotReference } from "./SnapshotReference";
import "../../components/report-card.css";
import { PageHeader }       from "../../components/PageHeader";
import { MonitoringHero }   from "./MonitoringHero";
import { bandKey, maturityBandColor, maturityBand, metricPolarity, vciBand, STANDING_RANK, type StandingKey } from "../../lib/scoreBands";
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatTile } from "@/components/ui/stat-tile";
import { ChevronDown } from "lucide-react";
import { AnimatedNumber } from "@/components/ui/animated-number";

/** Plain-language VCI explainer — shown wherever a VCI number appears. */
const VCI_TITLE =
  "Confidence (0–100): how much weight to give this figure — reflects cohort size, source quality, and classification certainty.";

/** Rows per page in the assessments table. */
const PAGE_SIZE = 10;

const DIRECTION_HINT: Record<string, string> = {
  maturity: "higher is better",
  exposure: "lower is better",
};
import { StatusDot } from "@/components/StatusDot";
import { noticeTypeLabel } from "../../lib/labels";
import { paginate } from "../../lib/paginate";

interface Assessment {
  notice_id: string;
  organization_id: string;
  notice_type: string;
  effective_date: string | null;
  organization: { name: string; domain: string | null; industry: string | null; size: string | null; geography: string | null } | null;
  /** THIS assessment's own overall score — null when it has not been scored.
   *  Never the org-wide figure: that one belongs to a portfolio, not a report. */
  overall_score: number | null;
  overall_confidence: number | null;
}

interface DashboardStats {
  overall_score: number | null;
  overall_confidence: number;
  /* score/confidence are null when nothing was computed. They used to arrive as
     0, which the client had to un-guess with `score > 0` — and that guess was
     wrong in both directions (a genuine 0 is the BEST result on an exposure
     metric, and it rendered as "not recorded"). Fixed server-side; the type
     records the contract. */
  domain_scores: { domain: string; object_type: string; score: number | null; confidence: number | null }[];
  finding_count: number;
  high_findings: number;
  medium_findings: number;
  assessment_count: number;
  snapshot: { id: string | null; date: string | null; benchmark_population_version: number | null };
  training_stats: { confirmed: number; edited: number; dismissed: number };
}


/** One metric, ready to render: the raw row plus the standing it sits in. */
interface Metric {
  domain: string;
  object_type: string;
  score: number | null;
  confidence: number | null;
  polarity: ReturnType<typeof metricPolarity>;
  standing: StandingKey | undefined;
}

const STANDING_COLOR: Record<StandingKey, string> = {
  good: "var(--standing-good)",
  mid:  "var(--standing-mid)",
  bad:  "var(--standing-bad)",
};

const STANDING_WORD: Record<StandingKey, string> = {
  good: "good", mid: "needs attention", bad: "poor",
};

/**
 * The mix of standings across every scored metric, as one bar.
 *
 * It is a proportion of a known whole, so it is a stacked bar, not a chart —
 * and the counts are printed beside it, because a reader must never have to
 * measure a bar to recover a number they could have been told.
 */
function StandingMix({ counts, total }: {
  counts: Record<StandingKey | "unknown", number>;
  total: number;
}) {
  const order: (StandingKey | "unknown")[] = ["good", "mid", "bad", "unknown"];
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-1.5 overflow-hidden rounded-full bg-border" role="img"
        aria-label={order
          .filter(k => counts[k] > 0)
          .map(k => `${counts[k]} ${k === "unknown" ? "not recorded" : STANDING_WORD[k]}`)
          .join(", ")}>
        {order.map(k => counts[k] > 0 && (
          <span
            key={k}
            style={{
              width: `${(counts[k] / total) * 100}%`,
              background: k === "unknown" ? "var(--muted-foreground)" : STANDING_COLOR[k],
            }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
        {order.filter(k => counts[k] > 0).map(k => (
          <span key={k}>
            <b className="font-data tabular-nums" style={{
              color: k === "unknown" ? "var(--muted-foreground)" : STANDING_COLOR[k],
            }}>{counts[k]}</b>{" "}
            {k === "unknown" ? "not recorded" : STANDING_WORD[k]}
          </span>
        ))}
      </div>
    </div>
  );
}

/** One compact metric line: name, meter, figure. */
function MetricRow({ metric }: { metric: Metric }) {
  const { domain, score, standing, polarity } = metric;
  const hasScore = score !== null && score !== undefined;
  const color = standing ? STANDING_COLOR[standing] : "var(--muted-foreground)";
  return (
    <li className="flex items-center gap-2.5 text-xs">
      <span className="min-w-0 flex-1 truncate text-muted-foreground">
        {domain}
        {polarity && (
          <span className="ml-1 text-[10px] opacity-70">· {DIRECTION_HINT[polarity]}</span>
        )}
      </span>
      <span
        className="h-1 w-16 shrink-0 overflow-hidden rounded-full bg-border"
        role="img"
        aria-label={hasScore
          ? `${domain} ${score.toFixed(1)} out of 100`
          : `${domain} not recorded`}
      >
        {hasScore && (
          <span
            className="block h-full rounded-full"
            style={{ width: `${Math.min(Math.max(score, 0), 100)}%`, background: color }}
          />
        )}
      </span>
      <span className="w-10 shrink-0 text-right font-data font-bold tabular-nums" style={{ color }}>
        {/* A genuine 0 prints as 0.0. Absence prints as an em dash. They are
            different facts and this line is the only place a reader sees which. */}
        {hasScore ? score.toFixed(1) : "\u2014"}
      </span>
    </li>
  );
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
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [page, setPage] = useState(0);

  const latest = assessments[0] ?? null;

  /* The card shows THIS report's own score, served by /assessments/.
     It used to fall back to the org-wide figure from dashboard-stats and, when
     that could not honestly be attributed (an admin sees many organisations),
     printed a sentence explaining our own plumbing to the reader. The score was
     always there — the list endpoint simply did not carry it. */
  const cardScore = latest?.overall_score ?? null;

  /* Clamped rather than trusted: a refresh that shortens the list while the
     reader is on the last page would otherwise render an empty table, which on
     this screen is indistinguishable from "you have no assessments". */
  const {
    rows: pageRows, page: safePage, pageCount,
    first: firstRow, last: lastRow,
  } = paginate(assessments, page, PAGE_SIZE);

  /* Metrics, ordered by what needs attention first — poor, then middling, then
     good, then anything with no standing at all. The name is the tiebreak, so
     two renders of one payload always agree (Hard Rule 6). Ordering by
     attention is why the collapsed view can show three rows and still be the
     useful three. */
  const metrics: Metric[] = useMemo(() => {
    const rows = (stats?.domain_scores ?? []).map(ds => {
      const polarity = metricPolarity(ds.domain);
      return { ...ds, polarity, standing: bandKey(ds.score, polarity) };
    });
    return rows.sort((a, b) => {
      const ra = a.standing ? STANDING_RANK[a.standing] : 3;
      const rb = b.standing ? STANDING_RANK[b.standing] : 3;
      return ra - rb || a.domain.localeCompare(b.domain);
    });
  }, [stats]);

  const standingCounts = useMemo(() => {
    const c = { good: 0, mid: 0, bad: 0, unknown: 0 };
    for (const m of metrics) c[m.standing ?? "unknown"] += 1;
    return c;
  }, [metrics]);

  return (
    <div>
      <PageHeader
        eyebrow="Assessments"
        title="Your Assessments"
        description="Real-time privacy intelligence across all assessed notices. Every number comes from the scoring pipeline — nothing is mocked."
        actions={
          <>
            <div className="flex items-center gap-1.5 text-[0.78rem] font-semibold text-[var(--verified)]">
              <StatusDot /> Live data
            </div>
            {/* Provenance moved off the top of the page and behind a control.
                Not removed — one gesture away (see SnapshotReference). */}
            {snapshotId && (
              <SnapshotReference snapshotId={snapshotId} frozenDate={snapshotDate} />
            )}
          </>
        }
      />

      {/* The latest report as an object, beside the numbers that describe the
          whole portfolio. Two columns, because they answer different questions:
          "what is the most recent thing" and "what does everything add up to". */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        {latest ? (
          <ReportCard
            organization={latest.organization?.name ?? "Organisation not recorded"}
            reportId={latest.notice_id}
            score={cardScore ?? undefined}
            scoreAbsenceReason="Not scored yet."
            meta={[
              { label: "Type", value: noticeTypeLabel(latest.notice_type) },
              ...(latest.effective_date ? [{ label: "Effective", value: latest.effective_date }] : []),
            ]}
          />
        ) : (
          <Card className="flex items-center justify-center p-8 text-center">
            <CardContent className="flex flex-col items-center gap-3 p-0">
              <p className="m-0 text-sm text-muted-foreground">No report yet.</p>
              <Button asChild size="sm"><Link to="/intake">Start Intake</Link></Button>
            </CardContent>
          </Card>
        )}

        <div className="flex flex-col gap-5">
          {/* Portfolio counts. Real values only — an absent stat shows an em
              dash, never a zero standing in for unknown. */}
          {stats && (
            <Card className="py-4">
              <CardContent className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
                <StatTile label="Assessments" value={stats.assessment_count} />
                <StatTile label="Findings"    value={stats.finding_count} />
                <StatTile label="High exposure"     value={stats.high_findings}   tone="bad" />
                <StatTile label="Elevated exposure" value={stats.medium_findings} tone="mid" />
              </CardContent>
            </Card>
          )}

          {/* Overall score — the BAND leads, the number follows (design-system §2).
              "Developing" is what a reader can act on; 71.7 is not. The figure is
              kept, never removed: it sits beside the band and in full lineage. */}
          <Card className="flex-1 py-4">
            <CardContent className="flex h-full flex-col gap-1.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Overall Privacy Intelligence
              </div>
              {overallScore != null ? (
                <>
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
                  </div>
                  <p className="m-0 text-xs text-muted-foreground">
                    benchmarked against your peer cohort · higher is better
                  </p>

                  {/* The space under the headline used to be empty with a
                      toggle stranded at the bottom. It now answers the question
                      the headline provokes — WHY is it Deficient — without
                      needing a click: the mix of standings, then the metrics
                      that need attention first. The full list is one click
                      further, in the same card. */}
                  {metrics.length > 0 && (
                    <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3" data-testid="score-breakdown">
                      <StandingMix counts={standingCounts} total={metrics.length} />

                      <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
                        {(breakdownOpen ? metrics : metrics.slice(0, 3)).map(m => (
                          <MetricRow key={m.object_type} metric={m} />
                        ))}
                      </ul>

                      {metrics.length > 3 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="-ml-2 w-fit"
                          aria-expanded={breakdownOpen}
                          aria-controls="score-breakdown"
                          onClick={() => setBreakdownOpen(o => !o)}
                          data-testid="toggle-breakdown"
                        >
                          {breakdownOpen
                            ? "Show fewer"
                            : `Show all ${metrics.length} metrics`}
                          <ChevronDown className={breakdownOpen
                            ? "rotate-180 transition-transform motion-reduce:transition-none"
                            : "transition-transform motion-reduce:transition-none"} />
                        </Button>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-sm text-muted-foreground">
                  No scores computed yet. Submit an assessment via Intake to see real scores.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex flex-col gap-5">

          {/* M-06/07/08: continuous-monitoring hero. Renders nothing at all while
              every monitoring endpoint is unpopulated — F07 surfacing rule. */}
          <MonitoringHero />

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
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Standing</th>
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Industry</th>
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Type</th>
                      <th className="px-6 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((a) => (
                      <tr key={a.notice_id} className="border-b last:border-0 hover:bg-muted/40 transition-colors">
                        <td className="px-6 py-3">
                          <div className="font-semibold">{a.organization?.name ?? "—"}</div>
                          {a.organization?.domain && (
                            <div className="text-xs text-muted-foreground">{a.organization.domain}</div>
                          )}
                        </td>
                        {/* Band leads, figure follows (design-system §2). An
                            unscored assessment says so in words — a dash in a
                            score column reads as a missing cell, not as a fact
                            about the report. */}
                        <td className="px-6 py-3">
                          {a.overall_score !== null && a.overall_score !== undefined ? (
                            <span className="flex items-baseline gap-2">
                              <span className="font-semibold" style={{ color: maturityBandColor(a.overall_score) }}>
                                {maturityBand(a.overall_score)}
                              </span>
                              <span className="font-data text-xs tabular-nums text-muted-foreground">
                                {a.overall_score.toFixed(1)}
                              </span>
                            </span>
                          ) : (
                            <span className="text-xs italic text-muted-foreground">Not scored yet</span>
                          )}
                        </td>
                        <td className="px-6 py-3 capitalize text-muted-foreground">{a.organization?.industry ?? "—"}</td>
                        <td className="px-6 py-3">
                          <Badge variant={a.notice_type === "live_assessment" ? "verified" : "provisional"}>
                            {noticeTypeLabel(a.notice_type)}
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

            {/* Pagination. The list used to render `slice(0, 20)` with nothing
                saying so — assessment 21 simply did not exist as far as the
                screen was concerned. The count below states the whole total, so
                the page can never imply the list is shorter than it is. */}
            {assessments.length > PAGE_SIZE && (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t px-6 py-3">
                <span className="text-xs text-muted-foreground" data-testid="pagination-status">
                  {firstRow}–{lastRow} of {assessments.length}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline" size="sm"
                    onClick={() => setPage(Math.max(0, safePage - 1))}
                    disabled={safePage === 0}
                    data-testid="page-prev"
                  >
                    Previous
                  </Button>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    Page {safePage + 1} of {pageCount}
                  </span>
                  <Button
                    variant="outline" size="sm"
                    onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}
                    disabled={safePage >= pageCount - 1}
                    data-testid="page-next"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>


    </div>
  );
}
