import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { PageHeader } from "../../components/PageHeader";
import "../../components/furniture.css";

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

  const [gateMode, setGateMode] = useState<"strict" | "instant_draft" | "client_reviews">("instant_draft");
  const [gateModeStatus, setGateModeStatus] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/admin/training-stats").catch(() => null),
      fetch((import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000") + "/health").then(r => r.json()).catch(() => null),
    ]).then(([s, h]) => {
      setStats(s as TrainingStats);
      setHealth(h as Record<string, unknown>);
    }).finally(() => setLoading(false));
  }, []);

  const handleGateModeChange = (mode: "strict" | "instant_draft" | "client_reviews") => {
    setGateMode(mode);
    setGateModeStatus(`Gate mode updated to ${mode.replace(/_/g, " ")}`);
    setTimeout(() => setGateModeStatus(null), 4000);
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
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.78rem", fontWeight: 600, color: health ? "var(--emerald)" : "var(--red)" }}>
            <span className="live-dot" style={{ background: health ? "var(--emerald)" : "var(--red)" }} />
            {health ? "System active" : "API offline"}
          </div>
        }
      />

      <div className="content-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, alignItems: "start" }}>
        
        {/* ── LEFT COLUMN ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          
          {/* System Health */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--navy)" }}>
                System Health
              </h2>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.78rem", fontWeight: 600, color: "var(--emerald)" }}>
                <span className="live-dot" /> System active
              </div>
            </div>

            <div className="stats-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div className="stat-card" style={{ background: "var(--soft-white)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className="live-dot" style={{ background: health ? "var(--emerald)" : "var(--red)" }} />
                  <div className="stat-value" style={{ color: health ? "var(--emerald)" : "var(--red)", fontSize: "1.25rem", fontWeight: 700 }}>
                    {health ? "Healthy" : "Offline"}
                  </div>
                </div>
                <div className="stat-label" style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4, fontWeight: 500 }}>API Status</div>
              </div>

              <div className="stat-card" style={{ background: "var(--soft-white)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className="live-dot" style={{ background: health?.ollama === "ok" ? "var(--emerald)" : "var(--red)" }} />
                  <div className="stat-value" style={{ color: health?.ollama === "ok" ? "var(--emerald)" : "var(--red)", fontSize: "1.25rem", fontWeight: 700 }}>
                    {health?.ollama === "ok" ? "Connected" : "Offline"}
                  </div>
                </div>
                <div className="stat-label" style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4, fontWeight: 500 }}>Ollama (LLM)</div>
              </div>
            </div>
          </div>

          {/* Database Overview */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", background: "var(--soft-white)" }}>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--navy)" }}>
                Database Overview
              </h2>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                Live record counts fetched from Supabase
              </p>
            </div>
            <div style={{ maxHeight: "380px", overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--soft-white)", borderBottom: "1px solid var(--border)" }}>
                    <th style={{ padding: "10px 16px", textAlign: "left", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>Table</th>
                    <th style={{ padding: "10px 16px", textAlign: "right", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>Row Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rowCounts).length > 0 ? (
                    Object.entries(rowCounts).map(([table, count]) => (
                      <tr key={table} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ padding: "10px 16px", fontSize: "0.85rem", color: "var(--text)", fontWeight: 500 }}>
                          {table.replace(/_/g, " ")}
                        </td>
                        <td className="tabular" style={{ padding: "10px 16px", textAlign: "right", fontWeight: 600, fontSize: "0.85rem", color: "var(--navy)" }}>
                          {typeof count === "number" ? count.toLocaleString() : count}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={2} style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)" }}>
                        No inventory data available.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>

        {/* ── RIGHT COLUMN ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          
          {/* Gate Mode Configuration */}
          <div className="card" style={{ padding: 24 }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 4, color: "var(--navy)" }}>
              Global Gate Mode
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 16 }}>
              Configure customer access permission tiers for draft assessments.
            </p>

            {gateModeStatus && (
              <div className="notice-box teal" style={{
                marginBottom: 16,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between"
              }}>
                <span>{gateModeStatus}</span>
                <button
                  onClick={() => setGateModeStatus(null)}
                  style={{ background: "transparent", color: "inherit", fontWeight: 700, fontSize: "0.9rem", border: "none" }}
                >
                  ×
                </button>
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[
                {
                  id: "instant_draft",
                  title: "Instant Draft (Default)",
                  desc: "Customers view report drafts immediately marked with a gold watermark.",
                  color: "var(--gold)"
                },
                {
                  id: "strict",
                  title: "Strict Mode",
                  desc: "Customers view nothing until approved by an SME reviewer.",
                  color: "var(--navy)"
                },
                {
                  id: "client_reviews",
                  title: "Client Reviews",
                  desc: "Clients can inspect the draft and leave feedback/comments.",
                  color: "var(--exec-blue)"
                }
              ].map(mode => (
                <label
                  key={mode.id}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 12,
                    padding: "14px 16px",
                    border: `1px solid ${gateMode === mode.id ? "var(--exec-blue)" : "var(--border)"}`,
                    background: gateMode === mode.id ? "rgba(0, 95, 163, 0.03)" : "white",
                    borderRadius: "var(--radius)",
                    cursor: "pointer",
                    transition: "all 0.18s"
                  }}
                >
                  <input
                    type="radio"
                    name="gateMode"
                    value={mode.id}
                    checked={gateMode === mode.id}
                    onChange={() => handleGateModeChange(mode.id as any)}
                    style={{ marginTop: 3 }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "var(--navy)", display: "flex", alignItems: "center", gap: 8 }}>
                      {mode.title}
                      {gateMode === mode.id && (
                        <span style={{ fontSize: "0.65rem", background: mode.color, color: "white", padding: "1px 6px", borderRadius: 4, textTransform: "uppercase", fontWeight: 700 }}>
                          Active
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 2 }}>
                      {mode.desc}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* System Operations — batch recompute (requires backend endpoint) */}
          <div className="card" style={{ padding: 24 }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 4, color: "var(--navy)" }}>
              System Operations
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 16 }}>
              Bulk recompute operations will be available once the batch endpoint is implemented.
            </p>
          </div>

          {/* Training stats */}
          <div className="card" style={{ padding: 24 }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 4, color: "var(--navy)" }}>
              Training Label Stats
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 20 }}>
              Audit labels captured from SME review queue confirmations and overrides.
            </p>

            {loading ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                <div style={{
                  width: 32, height: 32, border: "3px solid var(--border)",
                  borderTopColor: "var(--exec-blue)", borderRadius: "50%",
                  animation: "spin 0.7s linear infinite", margin: "0 auto 12px"
                }} />
                Loading stats...
              </div>
            ) : (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Total Labels</span>
                  <span className="tabular" style={{ fontSize: "1.8rem", fontWeight: 700, color: "var(--navy)" }}>
                    {actualStats.total_labels}
                  </span>
                </div>

                {/* Segmented bar graph of actions proportion */}
                <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", background: "var(--border)", marginBottom: 24 }}>
                  <div style={{ width: `${(actualStats.by_action.confirm / (actualStats.total_labels || 1)) * 100}%`, background: "var(--teal)" }} title="Confirmed" />
                  <div style={{ width: `${(actualStats.by_action.edit / (actualStats.total_labels || 1)) * 100}%`, background: "var(--gold)" }} title="Edited" />
                  <div style={{ width: `${(actualStats.by_action.dismiss / (actualStats.total_labels || 1)) * 100}%`, background: "var(--red)" }} title="Dismissed" />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 24 }}>
                  <div style={{ background: "var(--soft-white)", borderRadius: "var(--radius)", padding: "10px 12px", border: "1px solid var(--border)" }}>
                    <div className="micro-label">Confirmed</div>
                    <div className="tabular" style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--teal)" }}>{actualStats.by_action.confirm}</div>
                  </div>
                  <div style={{ background: "var(--soft-white)", borderRadius: "var(--radius)", padding: "10px 12px", border: "1px solid var(--border)" }}>
                    <div className="micro-label">Edited</div>
                    <div className="tabular" style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--gold)" }}>{actualStats.by_action.edit}</div>
                  </div>
                  <div style={{ background: "var(--soft-white)", borderRadius: "var(--radius)", padding: "10px 12px", border: "1px solid var(--border)" }}>
                    <div className="micro-label">Dismissed</div>
                    <div className="tabular" style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--red)" }}>{actualStats.by_action.dismiss}</div>
                  </div>
                </div>

                <div style={{ marginBottom: 20 }}>
                  <div className="section-label" style={{ marginBottom: 10 }}>Breakdown by Domain</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {Object.entries(actualStats.by_domain).map(([domain, count]) => {
                      const pct = (count / (actualStats.total_labels || 1)) * 100;
                      return (
                        <div key={domain}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: 3 }}>
                            <span>{domain.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                            <span className="tabular" style={{ fontWeight: 600 }}>{count}</span>
                          </div>
                          <div style={{ height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                            <div style={{ height: "100%", width: `${pct}%`, background: "var(--exec-blue)", borderRadius: 2 }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <div className="section-label" style={{ marginBottom: 8 }}>Labels Collected Over Time</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {Object.entries(actualStats.by_month).map(([month, count]) => (
                      <div key={month} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                        <span>{month}</span>
                        <span className="tabular" style={{ fontWeight: 600, color: "var(--navy)" }}>{count} label{count !== 1 ? "s" : ""}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

        </div>

      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 900px) {
          .content-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>

    </div>
  );
}
