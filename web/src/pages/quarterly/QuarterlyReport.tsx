/**
 * F21 — Quarterly Global Privacy Intelligence Report · REAL UI (replaces the
 * F12 mock M-15–M-18).
 *
 * Public view: hero (corpus counts S4-001..004), indicator cards (DMI, AI) with
 * population_n small-print, top-gaps chips (Codex hover), enforcement theme
 * bars, methodology from the block, PDF download. BASELINE line wherever a
 * delta would appear. Suppressed metrics are simply ABSENT (never dashes).
 * Admin (role=admin): build (quarter picker), draft preview, anonymization-gate
 * panel, approve (permission-gated), archive list.
 */
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { statusLabel } from "../../lib/labels";
import { CodexTooltip } from "../../components/CodexTooltip";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../auth/AuthProvider";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

interface Metric { metric_id: string; value: number | null; value_label: string | null; population_n: number; formula_citation: string; }
interface Methodology {
  quarter: string; quarter_window?: string[]; intro?: string;
  corpus: { organizations: number | null; clauses_analyzed: number | null; industries_benchmarked: number | null; jurisdictions_covered: number | null };
  population_criteria?: string; formula_versions?: Record<string, string>;
  suppression_rule?: string; s4_002_note?: string; s4_018_note?: string; weighting?: string;
  baseline_note?: string; reproducible?: string;
}
interface Payload { quarter: string; status: string; snapshot_id: string; baseline: boolean; metrics: Metric[]; methodology: Methodology; }
/* A quarterly snapshot's status. Two facts a reader needs from it: what to call
   it, and whether the report is published.

   The label used to be an inline ternary reading `draft ? "Draft — gold
   watermark" : "Approved"`. Two things were wrong with that. The label named a
   PDF rendering detail — the watermark the renderer stamps on a draft — on a
   badge that is already gold, so it described its own colour and not the state.
   And the ternary meant every status that is not literally "draft" rendered as
   "Approved", which on this table is the difference between "nobody may see
   this" and "this is public". An unrecognised status must never inherit the
   safest-sounding label; it inherits the most cautious one. */
const STATUS_VARIANT: Record<string, "provisional" | "verified" | "secondary"> = {
  draft: "provisional",
  approved: "verified",
};

const STATUS_MEANING: Record<string, string> = {
  draft: "Built but not published. Only admins can open it, and its PDF carries a draft watermark.",
  approved: "Published. This is the quarter the public report serves.",
};

interface AdminSnapshot { id: string; quarter: string; status: string; gate_result: unknown; created_at: string; approved_at: string | null; }

// Public endpoint is unauthenticated — fetch without the auth client.
async function fetchPublic(path: string): Promise<Payload | null> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) return null;
  return res.json();
}

function parseList(label: string | null): Record<string, unknown>[] {
  try { return label ? JSON.parse(label) : []; } catch { return []; }
}

const BASELINE_LINE = "Baseline edition — trend deltas begin next quarter.";

export function QuarterlyReport() {
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";
  const [payload, setPayload] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPublic("/quarterly/latest").then(p => { setPayload(p); setLoading(false); });
  }, []);

  return (
    <div>
      <PageHeader eyebrow="Quarterly" title="Global Privacy Intelligence Report"
        description="The published, anonymized market briefing. Every statistic is drawn only from cohorts large enough that no company can be identified, and traces to a frozen snapshot." />
      {loading ? <Card className="rounded-lg border bg-card p-5 mb-5"><div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">Loading…</div></Card>
        : payload ? <PublicReport p={payload} /> : <Card className="rounded-lg border bg-card p-5 mb-5"><div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">No approved quarterly report has been published yet.</div></Card>}
      {isAdmin && <AdminPanel onPublished={() => fetchPublic("/quarterly/latest").then(setPayload)} />}
    </div>
  );
}

// ── Public report ────────────────────────────────────────────
function PublicReport({ p }: { p: Payload }) {
  const m = p.methodology;
  const by = Object.fromEntries(p.metrics.map(x => [x.metric_id, x]));
  const dmi = by["S4-005"], ai = by["S4-006"];
  const gaps = parseList(by["GAPS"]?.value_label ?? null);
  const themes = parseList(by["S4-018"]?.value_label ?? null);
  const c = m.corpus;

  return (
    <div >
      {/* Hero */}
      <section className="rounded-lg border bg-card p-6 mb-5">
        <div className="font-sans text-[1.6rem] font-bold">{m.quarter}</div>
        <div className="flex flex-wrap gap-8 my-4.5">
          {c.organizations != null && <Stat n={c.organizations} label="organizations" />}
          {c.clauses_analyzed != null && <Stat n={c.clauses_analyzed} label="clauses analyzed" />}
          {c.industries_benchmarked != null && <Stat n={c.industries_benchmarked} label="industries benchmarked" />}
          {c.jurisdictions_covered != null && <Stat n={c.jurisdictions_covered} label="jurisdictions covered" />}
        </div>
        <div className="inline-block rounded-md border border-[color-mix(in_oklab,var(--provisional)_55%,transparent)] bg-[color-mix(in_oklab,var(--provisional)_12%,var(--card))] px-3 py-2 text-[0.82rem] text-[var(--provisional)]">{m.baseline_note || BASELINE_LINE}</div>
      </section>

      {/* Indicator cards */}
      {(dmi || ai) && (
        <Card className="rounded-lg border bg-card p-5 mb-5">
          <div className="font-sans text-[1.05rem] font-semibold mb-1.5">Intelligence indicators</div>
          <div className="flex flex-wrap gap-4.5">
            {dmi && <Indicator name="Disclosure Maturity Index" value={dmi.value} n={dmi.population_n} />}
            {ai && <Indicator name="AI Transparency Index" value={ai.value} n={ai.population_n} />}
          </div>
        </Card>
      )}

      {/* Top gaps */}
      {gaps.length > 0 && (
        <Card className="rounded-lg border bg-card p-5 mb-5">
          <div className="font-sans text-[1.05rem] font-semibold mb-1.5">Top disclosure gaps</div>
          <div className="text-[0.82rem] text-muted-foreground mb-3.5">Most frequent finding types across the corpus. Descriptive prevalence — not a verdict on any organisation.</div>
          <ol className="list-decimal pl-5.5">
            {gaps.map((g, i) => (
              <li className="grid grid-cols-[120px_1fr_48px] items-center gap-3 py-1.5" key={i}>
                <span className="text-[0.72rem]"><CodexTooltip code={String(g.code)} /></span>
                <span className="h-2 overflow-hidden rounded-sm bg-border"><span style={{ width: `${g.prevalence_pct}%` }} /></span>
                <span className="text-right font-data text-[0.82rem] font-bold tabular-nums">{String(g.prevalence_pct)}%</span>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {/* Enforcement themes */}
      {themes.length > 0 && (
        <Card className="rounded-lg border bg-card p-5 mb-5">
          <div className="font-sans text-[1.05rem] font-semibold mb-1.5">Enforcement theme shares</div>
          <div className="text-[0.82rem] text-muted-foreground mb-3.5">Share of resolved enforcement records by theme (resolved records only). Observed activity, not risk scores.</div>
          {themes.map((t, i) => (
            <div key={i} className="grid grid-cols-[160px_1fr_48px] items-center gap-3 py-1.5">
              <span className="text-[0.84rem] font-semibold">{String(t.theme)}</span>
              <span className="h-2 overflow-hidden rounded-sm bg-border"><span style={{ width: `${t.share_pct}%` }} /></span>
              <span className="text-right font-data text-[0.82rem] font-bold tabular-nums">{String(t.share_pct)}%</span>
            </div>
          ))}
        </Card>
      )}

      {/* Methodology */}
      <Card className="rounded-lg border bg-card p-5 mb-5">
        <div className="font-sans text-[1.05rem] font-semibold mb-1.5">Methodology</div>
        {m.intro && <p className="text-[0.82rem] text-muted-foreground mb-3.5">{m.intro}</p>}
        <div className="flex flex-col gap-0.5">
          {m.quarter_window && <MethRow k="Data window" v={m.quarter_window.join(" to ")} />}
          {c.organizations != null && <MethRow k="Organizations analyzed" v={String(c.organizations)} />}
          {c.clauses_analyzed != null && <MethRow k="Clauses analyzed" v={c.clauses_analyzed.toLocaleString()} />}
          {c.industries_benchmarked != null && <MethRow k="Industries benchmarked" v={String(c.industries_benchmarked)} />}
          {c.jurisdictions_covered != null && <MethRow k="Jurisdictions covered" v={String(c.jurisdictions_covered)} />}
          <MethRow k="Population criteria" v={m.population_criteria} />
          <MethRow k="Formula versions" v={m.formula_versions ? Object.entries(m.formula_versions).map(([k, v]) => `${k}:${v}`).join(", ") : undefined} />
          <MethRow k="Suppression rule" v={m.suppression_rule} />
          <MethRow k="Clause-count note" v={m.s4_002_note} />
          <MethRow k="Enforcement note" v={m.s4_018_note} />
          <MethRow k="Index weighting" v={m.weighting} />
          <MethRow k="Reproducibility" v={m.reproducible} />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <Button asChild><a href={`${API_BASE}/quarterly/${encodeURIComponent(p.quarter)}.pdf`} target="_blank" rel="noreferrer">Download PDF</a></Button>
        </div>
      </Card>
    </div>
  );
}

const Stat = ({ n, label }: { n: number; label: string }) => (
  <div className="flex flex-col"><div className="font-data text-[1.8rem] font-bold tabular-nums text-[var(--verified)]">{n.toLocaleString()}</div><div className="text-[0.76rem] text-muted-foreground">{label}</div></div>
);
const Indicator = ({ name, value, n }: { name: string; value: number | null; n: number }) => (
  <div className="rounded-md border px-5 py-4"><div className="font-data text-3xl font-bold tabular-nums">{value != null ? value.toFixed(1) : "—"}</div><div className="text-[0.82rem] font-semibold text-muted-foreground">{name}</div><div className="mt-0.5 text-[0.72rem] text-muted-foreground">based on {n} organisations</div></div>
);
const MethRow = ({ k, v }: { k: string; v?: string }) => v ? <div className="grid grid-cols-[32%_1fr] gap-3 border-b py-1.5 text-[0.82rem] [&>span:first-child]:font-semibold [&>span:first-child]:text-muted-foreground"><span>{k}</span><span>{v}</span></div> : null;

// ── Admin panel ──────────────────────────────────────────────
function AdminPanel({ onPublished }: { onPublished: () => void }) {
  const [quarter, setQuarter] = useState("2026-Q3");
  const [snapshots, setSnapshots] = useState<AdminSnapshot[]>([]);
  const [flash, showFlash] = useFlash();
  const [busy, setBusy] = useState(false);
  const [previewing, setPreviewing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setSnapshots(await api.get("/admin/quarterly")); } catch { /* ignore */ }
  }, []);
  useEffect(() => {
    const initialLoad = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);

  const build = async () => {
    setBusy(true);
    try {
      const out = await api.post("/admin/quarterly/build", { quarter });
      showFlash(out.gate_result?.passed ? `Built ${quarter} — anonymization gate PASSED (${out.metric_count} metrics).`
        : `Built ${quarter} — gate FAILED (${out.gate_result?.violations?.length} violations). Not approvable.`);
      load();
    } catch (e) { showFlash(e instanceof ApiError ? `Build failed: ${e.message}` : "Build failed."); }
    finally { setBusy(false); }
  };

  // The preview endpoint is admin-gated, so it needs the Authorization header —
  // a plain <a href> can't send it. Fetch the PDF as an authenticated blob and
  // open it in a tab the browser renders inline. window.open is called first,
  // inside the click gesture, so popup blockers don't kill it after the await.
  // NB: do NOT pass "noopener" — it makes window.open return null (and severs the
  // browsing context), so we could neither load the blob into the tab nor close it.
  const preview = async (id: string) => {
    const w = window.open("", "_blank");
    setPreviewing(id);
    try {
      const blob = await api.getBlob(`/admin/quarterly/${id}.pdf`);
      const url = URL.createObjectURL(blob);
      if (w) w.location.href = url; else window.location.assign(url);
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      if (w) w.close();
      showFlash(e instanceof ApiError ? `Preview failed: ${e.message}` : "Preview failed.");
    } finally {
      setPreviewing(null);
    }
  };

  const approve = async (id: string) => {
    try { await api.post(`/admin/quarterly/${id}/approve`, {}); showFlash("Approved & frozen — now public."); load(); onPublished(); }
    catch (e) { showFlash(e instanceof ApiError ? `Approve failed: ${e.message}` : "Approve failed."); }
  };

  return (
    <Card className="rounded-lg border-2 border-ring bg-card p-5 mb-5">
      <div className="font-sans text-[1.05rem] font-semibold mb-1.5">Admin · build &amp; publish</div>
      <FlashNotice message={flash} />
      <div className="my-3 flex flex-wrap gap-2.5">
        <input className="h-9 rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={quarter} onChange={e => setQuarter(e.target.value)} placeholder="2026-Q3" />
        <Button disabled={busy} onClick={build}>{busy ? "Building…" : "Build quarter"}</Button>
      </div>
      <table className="w-full border-collapse text-[0.84rem] [&_th]:border-b [&_th]:px-2.5 [&_th]:py-2 [&_th]:text-left [&_td]:border-b [&_td]:px-2.5 [&_td]:py-2 [&_td]:text-left">
        <thead><tr><th>Quarter</th><th>Status</th><th>Gate</th><th>Created</th><th></th></tr></thead>
        <tbody>
          {snapshots.map(s => {
            const gate = (s.gate_result && typeof s.gate_result === "object") ? s.gate_result as { passed?: boolean; violations?: unknown[] } : null;
            const passed = gate?.passed;
            /* Approve is offered ONLY for a draft whose gate actually passed.
               `passed` is undefined when no gate has run, and `&&` on an
               undefined renders nothing — correct, but by accident. Stated. */
            const canApprove = s.status === "draft" && passed === true;
            return (
              <tr key={s.id}>
                <td>{s.quarter}</td>
                <td>
                  {/* The status names the STATE, not how the PDF happens to be
                      decorated. "Draft — gold watermark" described the
                      watermark the renderer stamps on a draft — a rendering
                      detail, on a badge that is itself already gold, telling
                      the reader nothing about whether the report may be
                      published.
                      What matters is: a draft is not published; an approved
                      one is. That is what the label and its title say now. */}
                  <Badge
                    variant={STATUS_VARIANT[s.status] ?? "secondary"}
                    title={STATUS_MEANING[s.status] ?? "Status not recognised — this report is not published."}
                  >
                    {statusLabel(s.status)}
                  </Badge>
                </td>
                {/* Three states, not two: passed, failed, and NOT YET RUN.
                    An em dash for "no gate result" is indistinguishable from a
                    missing cell, and it used to sit in the same column as a
                    real verdict. */}
                <td>
                  {passed === true ? (
                    <span className="font-bold text-[var(--verified)]">Passed</span>
                  ) : passed === false ? (
                    <span className="font-bold text-[var(--standing-bad)]">
                      Failed · {gate?.violations?.length ?? 0}{" "}
                      {gate?.violations?.length === 1 ? "violation" : "violations"}
                    </span>
                  ) : (
                    <span className="italic text-muted-foreground">Not run</span>
                  )}
                </td>
                <td>{new Date(s.created_at).toLocaleString()}</td>
                <td>
                  <Button variant="outline" disabled={previewing === s.id} onClick={() => preview(s.id)}>{previewing === s.id ? "Opening…" : "Preview PDF"}</Button>
                  {canApprove && <Button onClick={() => approve(s.id)}>Approve</Button>}
                </td>
              </tr>
            );
          })}
          {snapshots.length === 0 && <tr><td colSpan={5} className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">No builds yet.</td></tr>}
        </tbody>
      </table>
    </Card>
  );
}
