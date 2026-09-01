import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { PageHeader } from "../../components/PageHeader";
import { JobsPanel } from "./JobsPanel";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { StatusDot } from "@/components/StatusDot";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { domainLabel, humanize } from "../../lib/labels";

interface TrainingStats {
  total_labels: number;
  by_action: Record<string, number>;
  by_domain: Record<string, number>;
  by_month: Record<string, number>;
}

interface TriggerResult {
  run_id: string;
  requested: number;
  scored: number;
  failed: number;
  outcome: string;
  notices: { notice_id: string; status: string; snapshot_id?: string }[];
}

export function AdminConsole() {
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const [gateMode, setGateMode] = useState<"strict" | "instant_draft" | "client_reviews">("instant_draft");
  const [gateModeStatus, setGateModeStatus] = useState<string | null>(null);
  const [gateModeError, setGateModeError] = useState<string | null>(null);

  // ── M-14: batch re-assessment trigger ──
  const [batchOrg, setBatchOrg] = useState("");
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResult, setBatchResult] = useState<TriggerResult | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/admin/training-stats").catch(() => null),
      fetch((import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "")) + "/health").then(r => r.json()).catch(() => null),
      // M-13: read the REAL gate mode from the backend (platform_setting-backed).
      api.get("/review/gate-mode").catch(() => null),
    ]).then(([s, h, g]) => {
      setStats(s as TrainingStats);
      setHealth(h as Record<string, unknown>);
      const mode = (g as { mode?: string } | null)?.mode;
      if (mode === "strict" || mode === "instant_draft" || mode === "client_reviews") {
        setGateMode(mode);
      }
    }).finally(() => setLoading(false));
  }, []);

  // M-13: persist gate-mode changes to the real endpoint; reflect honest failure.
  const handleGateModeChange = async (mode: "strict" | "instant_draft" | "client_reviews") => {
    const prev = gateMode;
    setGateMode(mode);
    setGateModeError(null);
    try {
      await api.post("/review/gate-mode", { mode });
      setGateModeStatus(`Gate mode updated to ${humanize(mode)}`);
      setTimeout(() => setGateModeStatus(null), 4000);
    } catch {
      setGateMode(prev); // roll back the optimistic switch
      setGateModeError("Could not save the gate mode. The change was not applied.");
    }
  };

  // M-14: trigger a real batch re-assessment run.
  const handleTriggerBatch = async () => {
    const org = batchOrg.trim();
    if (!org) return;
    setBatchRunning(true);
    setBatchError(null);
    setBatchResult(null);
    try {
      const res = await api.post("/admin/trigger-assessment", { org_id: org });
      setBatchResult(res as TriggerResult);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Batch run failed.";
      setBatchError(msg || "Batch run failed.");
    } finally {
      setBatchRunning(false);
    }
  };

  const rowCounts = (health?.row_counts ?? {}) as Record<string, number>;

  const actualStats = {
    total_labels: stats?.total_labels ?? 0,
    by_action: {
      confirm: stats?.by_action?.confirm ?? 0,
      edit: stats?.by_action?.edit ?? 0,
      dismiss: stats?.by_action?.dismiss ?? 0,
    },
    by_domain: stats?.by_domain ?? {},
    by_month: stats?.by_month ?? {},
  };

  return (
    <div>
      {/* No provenance ribbon here — the ribbon means "reproducible snapshot" and
          nothing on the admin console is a snapshot. Keep its meaning exact. */}
      <PageHeader
        eyebrow="Admin"
        title="Admin Console"
        description="System health, database record counts, the gate-mode policy that controls when customers see drafts, batch operations, and training-label statistics."
        actions={
          <Badge variant={health ? "verified" : "standing-bad"} className="gap-1.5">
            <StatusDot state={health ? "live" : "stopped"} />
            {health ? "System active" : "API offline"}
          </Badge>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-2">

        {/* ── LEFT COLUMN ── */}
        <div className="flex flex-col gap-6">
          
          {/* System Health */}
          <Card>
            <CardHeader>
              <CardTitle>System Health</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center gap-2">
                  <StatusDot state={health ? "live" : "stopped"} />
                  <div className={cn("font-data text-xl font-bold",
                    health ? "text-[var(--standing-good)]" : "text-[var(--standing-bad)]")}>
                    {health ? "Healthy" : "Offline"}
                  </div>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">API Status</div>
              </div>

              <div className="rounded-lg border bg-muted/40 p-4">
                <div className="flex items-center gap-2">
                  <StatusDot state={health?.ollama === "ok" ? "live" : "stopped"} />
                  <div className={cn("font-data text-xl font-bold",
                    health?.ollama === "ok" ? "text-[var(--standing-good)]" : "text-[var(--standing-bad)]")}>
                    {health?.ollama === "ok" ? "Connected" : "Offline"}
                  </div>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">Ollama (LLM)</div>
              </div>
            </CardContent>
          </Card>

          {/* Database Overview */}
          <Card className="gap-0 overflow-hidden py-0">
            <CardHeader className="border-b bg-muted/40 py-4">
              <CardTitle className="text-base">Database Overview</CardTitle>
              <CardDescription>Live record counts fetched from Supabase</CardDescription>
            </CardHeader>
            <div className="max-h-95 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Table</TableHead>
                    <TableHead className="text-right">Row Count</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(rowCounts).length > 0 ? (
                    Object.entries(rowCounts).map(([table, count]) => (
                      <TableRow key={table}>
                        <TableCell className="font-medium capitalize">{humanize(table)}</TableCell>
                        <TableCell className="text-right font-data tabular-nums font-semibold">
                          {typeof count === "number" ? count.toLocaleString() : count}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={2} className="py-6 text-center text-muted-foreground">
                        No inventory data available.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>

        </div>

        {/* ── RIGHT COLUMN ── */}
        <div className="flex flex-col gap-6">

          {/* Gate Mode Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Global Gate Mode</CardTitle>
              <CardDescription>Configure customer access permission tiers for draft assessments.</CardDescription>
            </CardHeader>
            <CardContent>

            {gateModeStatus && (
              <Alert className="mb-4 flex items-center justify-between gap-3">
                <AlertDescription>{gateModeStatus}</AlertDescription>
                <Button variant="ghost" size="icon" className="size-6 shrink-0"
                  onClick={() => setGateModeStatus(null)} aria-label="Dismiss">
                  <X />
                </Button>
              </Alert>
            )}

            {gateModeError && (
              <Alert variant="destructive" className="mb-4 flex items-center justify-between gap-3">
                <AlertDescription>{gateModeError}</AlertDescription>
                <Button variant="ghost" size="icon" className="size-6 shrink-0"
                  onClick={() => setGateModeError(null)} aria-label="Dismiss">
                  <X />
                </Button>
              </Alert>
            )}

            <div role="radiogroup" aria-label="Gate mode" className="flex flex-col gap-3">
              {[
                { id: "instant_draft", title: "Instant Draft (Default)",
                  /* Names the consequence, not the colour: an admin picking a
                     gate mode needs to know the customer sees an unreviewed
                     draft and that it is marked as one. Which colour the mark
                     is happens to be gold today and is not the decision. */
                  desc: "Customers see the report as soon as it is built, marked as an unreviewed draft." },
                { id: "strict", title: "Strict Mode",
                  desc: "Customers view nothing until approved by an SME reviewer." },
                { id: "client_reviews", title: "Client Reviews",
                  desc: "Clients can inspect the draft and leave feedback/comments." },
              ].map(mode => (
                <label
                  key={mode.id}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors",
                    gateMode === mode.id ? "border-ring bg-accent/50" : "hover:bg-accent/30"
                  )}
                >
                  <input
                    type="radio"
                    name="gateMode"
                    value={mode.id}
                    checked={gateMode === mode.id}
                    onChange={() => handleGateModeChange(mode.id as "strict" | "instant_draft" | "client_reviews")}
                    className="mt-1 accent-[var(--primary)]"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      {mode.title}
                      {gateMode === mode.id && <Badge className="text-[10px] uppercase">Active</Badge>}
                    </div>
                    <div className="mt-0.5 text-sm text-muted-foreground">{mode.desc}</div>
                  </div>
                </label>
              ))}
            </div>
            </CardContent>
          </Card>

          {/* System Operations — M-14: real batch re-assessment trigger */}
          <Card>
            <CardHeader>
              <CardTitle>System Operations</CardTitle>
              <CardDescription>
                Re-run the scoring pipeline over every stored notice for an organization.
                Each run writes new snapshots and returns a run identifier for the audit trail.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={batchOrg}
                  onChange={e => setBatchOrg(e.target.value)}
                  placeholder="Organization ID"
                  aria-label="Organization ID"
                />
                <Button onClick={handleTriggerBatch} disabled={batchRunning || !batchOrg.trim()}>
                  {batchRunning ? "Running…" : "Run assessment batch"}
                </Button>
              </div>

              {batchError && (
                <Alert variant="destructive"><AlertDescription>{batchError}</AlertDescription></Alert>
              )}

              {batchResult && (
                <Alert>
                  <AlertDescription>
                    {/* Run id is machinery: the OUTCOME leads, the truncated id
                        follows as a reference (DDR-011). */}
                    <span className="font-semibold">{batchResult.outcome}</span>
                    <span className="ml-1.5 font-data text-muted-foreground">
                      run {batchResult.run_id.slice(0, 8)}
                    </span>
                    <span className="mt-1 block font-data tabular-nums text-muted-foreground">
                      {batchResult.scored} scored · {batchResult.failed} failed · {batchResult.requested} requested
                    </span>
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Training stats */}
          <Card>
            <CardHeader>
              <CardTitle>Training Label Stats</CardTitle>
              <CardDescription>
                Audit labels captured from SME review queue confirmations and overrides.
              </CardDescription>
            </CardHeader>
            <CardContent>
            {loading ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-2 w-full" />
                <div className="grid grid-cols-3 gap-3">
                  {[0,1,2].map(i => <Skeleton key={i} className="h-16" />)}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm font-semibold text-muted-foreground">Total Labels</span>
                  <span className="font-data text-3xl font-bold tabular-nums">
                    <AnimatedNumber value={actualStats.total_labels} />
                  </span>
                </div>

                {/* Part-to-whole: one stacked bar, not three charts. Colours name
                    the ACTION taken, not a standing — a dismissal is not "bad". */}
                <div
                  className="flex h-2 overflow-hidden rounded-full bg-border"
                  role="img"
                  aria-label={`${actualStats.by_action.confirm} confirmed, ${actualStats.by_action.edit} edited, ${actualStats.by_action.dismiss} dismissed`}
                >
                  <div style={{ width: `${(actualStats.by_action.confirm / (actualStats.total_labels || 1)) * 100}%`, background: "var(--chart-3)" }} />
                  <div style={{ width: `${(actualStats.by_action.edit / (actualStats.total_labels || 1)) * 100}%`, background: "var(--chart-1)" }} />
                  <div style={{ width: `${(actualStats.by_action.dismiss / (actualStats.total_labels || 1)) * 100}%`, background: "var(--muted-foreground)" }} />
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Confirmed", value: actualStats.by_action.confirm, dot: "var(--chart-3)" },
                    { label: "Edited",    value: actualStats.by_action.edit,    dot: "var(--chart-1)" },
                    { label: "Dismissed", value: actualStats.by_action.dismiss, dot: "var(--muted-foreground)" },
                  ].map(a => (
                    <div key={a.label} className="rounded-lg border bg-muted/40 p-3">
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <span className="size-2 rounded-full" style={{ background: a.dot }} aria-hidden="true" />
                        {a.label}
                      </div>
                      <div className="font-data text-xl font-bold tabular-nums">
                        <AnimatedNumber value={a.value} />
                      </div>
                    </div>
                  ))}
                </div>

                <div>
                  <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Breakdown by Domain
                  </div>
                  <div className="flex flex-col gap-2.5">
                    {Object.entries(actualStats.by_domain).map(([domain, count]) => {
                      const pct = (count / (actualStats.total_labels || 1)) * 100;
                      return (
                        <div key={domain}>
                          <div className="mb-1 flex justify-between text-sm text-muted-foreground">
                            <span className="capitalize">{domainLabel(domain)}</span>
                            <span className="font-data font-semibold tabular-nums">{count}</span>
                          </div>
                          <div className="h-1 overflow-hidden rounded-sm bg-border">
                            <div
                              className="h-full rounded-sm transition-[width] duration-700 ease-out motion-reduce:transition-none"
                              style={{ width: `${pct}%`, background: "var(--chart-3)" }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Labels Collected Over Time
                  </div>
                  <dl className="flex flex-col gap-1.5 text-sm">
                    {Object.entries(actualStats.by_month).map(([month, count]) => (
                      <div key={month} className="flex justify-between">
                        <dt className="text-muted-foreground">{month}</dt>
                        <dd className="font-data font-semibold tabular-nums">
                          {count} label{count !== 1 ? "s" : ""}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>
            )}
            </CardContent>
          </Card>

        </div>

      </div>

      <JobsPanel />

    </div>
  );
}
