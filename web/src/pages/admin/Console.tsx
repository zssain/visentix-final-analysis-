import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";

interface TrainingStats {
  total_labels: number;
  by_action: Record<string, number>;
  by_domain: Record<string, number>;
  by_month: Record<string, number>;
}

export function AdminConsole() {
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/admin/training-stats").catch(() => null),
      fetch("http://localhost:8000/health").then(r => r.json()).catch(() => null),
    ]).then(([s, h]) => {
      setStats(s as TrainingStats);
      setHealth(h as Record<string, unknown>);
    }).finally(() => setLoading(false));
  }, []);

  const rowCounts = (health?.row_counts ?? {}) as Record<string, number>;

  return (
    <div>
      <div className="page-header">
        <h1>Admin Console</h1>
        <p>System operations, training stats, and data overview</p>
      </div>

      {/* System health */}
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12, color: "var(--primary)" }}>
        System Health
      </h2>
      <div className="stats-grid" style={{ marginBottom: 32 }}>
        <div className="stat-card">
          <div className="stat-value" style={{ color: health ? "var(--success)" : "var(--danger)" }}>
            {health ? "Healthy" : "..."}
          </div>
          <div className="stat-label">API Status</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{rowCounts.organization ?? "..."}</div>
          <div className="stat-label">Organizations</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{rowCounts.disclosure_clause ?? "..."}</div>
          <div className="stat-label">Clauses</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{rowCounts.risk_finding ?? "..."}</div>
          <div className="stat-label">Risk Findings</div>
        </div>
      </div>

      {/* Training stats */}
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12, color: "var(--primary)" }}>
        Training Label Stats
      </h2>
      {loading ? (
        <div className="card" style={{ padding: 40, textAlign: "center" }}>Loading...</div>
      ) : stats ? (
        <div className="stats-grid" style={{ marginBottom: 32 }}>
          <div className="stat-card">
            <div className="stat-value">{stats.total_labels}</div>
            <div className="stat-label">Total Labels</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--success)" }}>{stats.by_action?.confirm ?? 0}</div>
            <div className="stat-label">Confirmed</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--accent)" }}>{stats.by_action?.edit ?? 0}</div>
            <div className="stat-label">Edited</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--danger)" }}>{stats.by_action?.dismiss ?? 0}</div>
            <div className="stat-label">Dismissed</div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 24 }}>No training stats available yet.</div>
      )}

      {/* Data overview */}
      <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 12, color: "var(--primary)" }}>
        Database Overview
      </h2>
      <div className="card" style={{ overflow: "hidden" }}>
        <table>
          <thead>
            <tr><th>Table</th><th style={{ textAlign: "right" }}>Row Count</th></tr>
          </thead>
          <tbody>
            {Object.entries(rowCounts).map(([table, count]) => (
              <tr key={table}>
                <td>{table.replace(/_/g, " ")}</td>
                <td style={{ textAlign: "right", fontWeight: 600, fontFamily: "monospace" }}>
                  {typeof count === "number" ? count.toLocaleString() : count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
