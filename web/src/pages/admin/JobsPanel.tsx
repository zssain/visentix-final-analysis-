/**
 * F07 admin Jobs panel — table of scheduler jobs with enable toggle, cron, last
 * status chip, counts, and a Run-now button. Polls GET /admin/jobs every 5s while
 * any job is running. Shows a banner when alert delivery is suppressed pending
 * F-013 severity-threshold approval. Mirrors the fetch/error/empty conventions in
 * pages/customer.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";

interface JobRun {
  status: "running" | "succeeded" | "failed";
  items_processed: number;
  items_changed: number;
  started_at: string;
  finished_at: string | null;
  triggered_by: string;
}
interface Job {
  job_name: string;
  enabled: boolean;
  cron: string;
  last_run: JobRun | null;
}

const CHIP: Record<string, { bg: string; fg: string; label: string }> = {
  running: { bg: "var(--border)", fg: "var(--text-muted)", label: "running…" },
  succeeded: { bg: "rgba(20,138,120,0.1)", fg: "var(--teal)", label: "succeeded" },
  failed: { bg: "rgba(200,50,50,0.1)", fg: "var(--red)", label: "failed" },
  none: { bg: "var(--soft-white)", fg: "var(--text-muted)", label: "never run" },
};

export function JobsPanel() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suppressed, setSuppressed] = useState(0);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const timer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [j, s] = await Promise.all([
        api.get("/admin/jobs"),
        api.get("/admin/status").catch(() => null),
      ]);
      setJobs(j as Job[]);
      if (s) setSuppressed((s as { alerts_suppressed?: number }).alerts_suppressed ?? 0);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Poll every 5s while any job is running.
  useEffect(() => {
    const anyRunning = jobs?.some((j) => j.last_run?.status === "running");
    if (anyRunning && timer.current === null) {
      timer.current = window.setInterval(load, 5000);
    } else if (!anyRunning && timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
    return () => { if (timer.current !== null) { window.clearInterval(timer.current); timer.current = null; } };
  }, [jobs, load]);

  const runNow = async (name: string) => {
    setBusy((b) => ({ ...b, [name]: true }));
    try {
      await api.post(`/admin/jobs/${name}/run`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setBusy((b) => ({ ...b, [name]: false }));
    }
  };

  const toggle = async (name: string, enabled: boolean) => {
    // optimistic
    setJobs((js) => js?.map((j) => (j.job_name === name ? { ...j, enabled } : j)) ?? null);
    try {
      await api.post(`/admin/jobs/${name}/toggle`, { enabled });
    } catch {
      await load(); // revert to truth on failure
    }
  };

  return (
    <section className="card" style={{ padding: "20px 24px", marginTop: 20 }}>
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--navy)", marginBottom: 4 }}>
        Scheduled Jobs
      </h2>
      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 14 }}>
        Monitoring, regulator, and benchmark jobs. Toggle a job or run it now; the table
        refreshes automatically while a job is running.
      </p>

      {suppressed > 0 && (
        <div style={{
          background: "rgba(200,164,106,0.1)", border: "1px solid var(--gold)",
          borderRadius: "var(--radius)", padding: "10px 14px", marginBottom: 14,
          fontSize: "0.85rem", color: "#7a5c20", fontWeight: 600,
        }}>
          Alert delivery is paused pending severity-threshold approval — {suppressed} event
          {suppressed === 1 ? "" : "s"} held. See the SME review checklist.
        </div>
      )}

      {error && <p style={{ color: "var(--red)", fontSize: "0.85rem" }}>{error}</p>}
      {!jobs && !error && <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Loading…</p>}

      {jobs && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: "8px 6px" }}>Job</th>
              <th style={{ padding: "8px 6px" }}>Enabled</th>
              <th style={{ padding: "8px 6px" }}>Cron (UTC)</th>
              <th style={{ padding: "8px 6px" }}>Last run</th>
              <th style={{ padding: "8px 6px" }}>Counts</th>
              <th style={{ padding: "8px 6px" }}></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => {
              const c = CHIP[j.last_run?.status ?? "none"] ?? CHIP.none;
              return (
                <tr key={j.job_name} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "10px 6px", fontWeight: 600, color: "var(--navy)" }}>{j.job_name}</td>
                  <td style={{ padding: "10px 6px" }}>
                    <label style={{ cursor: "pointer" }}>
                      <input type="checkbox" checked={j.enabled}
                             onChange={(e) => toggle(j.job_name, e.target.checked)} />
                    </label>
                  </td>
                  <td style={{ padding: "10px 6px", fontFamily: "var(--font-data)", color: "var(--text-secondary)" }}>{j.cron}</td>
                  <td style={{ padding: "10px 6px" }}>
                    <span style={{ background: c.bg, color: c.fg, padding: "2px 9px",
                                   borderRadius: 20, fontSize: "0.72rem", fontWeight: 700 }}>
                      {c.label}
                    </span>
                  </td>
                  <td style={{ padding: "10px 6px", color: "var(--text-secondary)" }}>
                    {j.last_run ? `${j.last_run.items_processed} proc · ${j.last_run.items_changed} changed` : "—"}
                  </td>
                  <td style={{ padding: "10px 6px", textAlign: "right" }}>
                    <button className="btn btn-outline btn-sm" disabled={busy[j.job_name]}
                            onClick={() => runNow(j.job_name)} aria-busy={busy[j.job_name]}>
                      {busy[j.job_name] ? "Running…" : "Run now"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
