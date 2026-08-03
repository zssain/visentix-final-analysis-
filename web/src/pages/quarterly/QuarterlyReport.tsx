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
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { CodexTooltip } from "../../components/CodexTooltip";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../auth/AuthProvider";
import "./quarterly.css";
import "../../components/furniture.css";

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
      {loading ? <div className="qr-card"><div className="qr-empty">Loading…</div></div>
        : payload ? <PublicReport p={payload} /> : <div className="qr-card"><div className="qr-empty">No approved quarterly report has been published yet.</div></div>}
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
    <div className="qr-report">
      {/* Hero */}
      <section className="qr-hero">
        <div className="qr-hero-quarter">{m.quarter}</div>
        <div className="qr-corpus">
          {c.organizations != null && <Stat n={c.organizations} label="organizations" />}
          {c.clauses_analyzed != null && <Stat n={c.clauses_analyzed} label="clauses analyzed" />}
          {c.industries_benchmarked != null && <Stat n={c.industries_benchmarked} label="industries benchmarked" />}
          {c.jurisdictions_covered != null && <Stat n={c.jurisdictions_covered} label="jurisdictions covered" />}
        </div>
        <div className="qr-baseline">{m.baseline_note || BASELINE_LINE}</div>
      </section>

      {/* Indicator cards */}
      {(dmi || ai) && (
        <section className="qr-card">
          <div className="qr-h">Intelligence indicators</div>
          <div className="qr-indicators">
            {dmi && <Indicator name="Disclosure Maturity Index" value={dmi.value} n={dmi.population_n} />}
            {ai && <Indicator name="AI Transparency Index" value={ai.value} n={ai.population_n} />}
          </div>
        </section>
      )}

      {/* Top gaps */}
      {gaps.length > 0 && (
        <section className="qr-card">
          <div className="qr-h">Top disclosure gaps</div>
          <div className="qr-sub">Most frequent finding types across the corpus. Descriptive prevalence — not a verdict on any organisation.</div>
          <ol className="qr-gaps">
            {gaps.map((g, i) => (
              <li key={i}>
                <span className="qr-chip"><CodexTooltip code={String(g.code)} /></span>
                <span className="qr-bar"><span style={{ width: `${g.prevalence_pct}%` }} /></span>
                <span className="qr-pct">{String(g.prevalence_pct)}%</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Enforcement themes */}
      {themes.length > 0 && (
        <section className="qr-card">
          <div className="qr-h">Enforcement theme shares</div>
          <div className="qr-sub">Share of resolved enforcement records by theme (resolved records only). Observed activity, not risk scores.</div>
          {themes.map((t, i) => (
            <div key={i} className="qr-theme">
              <span className="qr-theme-label">{String(t.theme)}</span>
              <span className="qr-bar"><span style={{ width: `${t.share_pct}%` }} /></span>
              <span className="qr-pct">{String(t.share_pct)}%</span>
            </div>
          ))}
        </section>
      )}

      {/* Methodology */}
      <section className="qr-card">
        <div className="qr-h">Methodology</div>
        {m.intro && <p className="qr-sub">{m.intro}</p>}
        <div className="qr-meth">
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
        <div className="qr-actions">
          <a className="btn btn-primary" href={`${API_BASE}/quarterly/${encodeURIComponent(p.quarter)}.pdf`} target="_blank" rel="noreferrer">Download PDF</a>
          <IntelligenceMark />
        </div>
      </section>
    </div>
  );
}

const Stat = ({ n, label }: { n: number; label: string }) => (
  <div className="qr-stat"><div className="qr-stat-n">{n.toLocaleString()}</div><div className="qr-stat-l">{label}</div></div>
);
const Indicator = ({ name, value, n }: { name: string; value: number | null; n: number }) => (
  <div className="qr-ind"><div className="qr-ind-v">{value != null ? value.toFixed(1) : "—"}</div><div className="qr-ind-n">{name}</div><div className="qr-ind-pop">based on {n} organisations</div></div>
);
const MethRow = ({ k, v }: { k: string; v?: string }) => v ? <div className="qr-meth-row"><span>{k}</span><span>{v}</span></div> : null;

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
  useEffect(() => { load(); }, [load]);

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
  const preview = async (id: string) => {
    const w = window.open("", "_blank", "noopener,noreferrer");
    setPreviewing(id);
    try {
      const blob = await api.getBlob(`/admin/quarterly/${id}.pdf`);
      const url = URL.createObjectURL(blob);
      if (w) w.location.href = url; else window.location.href = url;
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
    <section className="qr-card qr-admin">
      <div className="qr-h">Admin · build &amp; publish</div>
      <FlashNotice message={flash} />
      <div className="qr-build">
        <input className="qr-input" value={quarter} onChange={e => setQuarter(e.target.value)} placeholder="2026-Q3" />
        <button className="btn btn-primary" disabled={busy} onClick={build}>{busy ? "Building…" : "Build quarter"}</button>
      </div>
      <table className="qr-admin-table">
        <thead><tr><th>Quarter</th><th>Status</th><th>Gate</th><th>Created</th><th></th></tr></thead>
        <tbody>
          {snapshots.map(s => {
            const gate = (s.gate_result && typeof s.gate_result === "object") ? s.gate_result as { passed?: boolean; violations?: unknown[] } : null;
            const passed = gate?.passed;
            return (
              <tr key={s.id}>
                <td>{s.quarter}</td>
                <td><span className={`qr-status st-${s.status}`}>{s.status === "draft" ? "draft (gold watermark)" : "approved"}</span></td>
                <td>{passed === true ? <span className="qr-gate ok">passed</span> : passed === false ? <span className="qr-gate bad" title={JSON.stringify(gate?.violations)}>failed · {gate?.violations?.length} violations</span> : "—"}</td>
                <td>{new Date(s.created_at).toLocaleString()}</td>
                <td>
                  <button className="btn" disabled={previewing === s.id} onClick={() => preview(s.id)}>{previewing === s.id ? "Opening…" : "Preview PDF"}</button>
                  {s.status === "draft" && passed && <button className="btn btn-primary" onClick={() => approve(s.id)}>Approve</button>}
                </td>
              </tr>
            );
          })}
          {snapshots.length === 0 && <tr><td colSpan={5} className="qr-empty">No builds yet.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
