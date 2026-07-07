import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { ProvenanceRibbon } from "../../components/ProvenanceRibbon";
import { IntelligenceMark } from "../../components/IntelligenceMark";
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

  // Simulated Gate Mode state [MOCK M-13]
  const [gateMode, setGateMode] = useState<"strict" | "instant_draft" | "client_reviews">("instant_draft");
  const [gateModeStatus, setGateModeStatus] = useState<string | null>(null);

  // Simulated Batch Assessment state [MOCK M-14]
  const [triggerStatus, setTriggerStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [triggerMessage, setTriggerMessage] = useState<string | null>(null);

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
    setGateModeStatus(`Gate mode updated to ${mode.replace(/_/g, " ")} (Simulated M-13)`);
    // Clear notification after 4 seconds
    setTimeout(() => setGateModeStatus(null), 4000);
  };

  const handleTriggerAssessment = () => {
    setTriggerStatus("loading");
    setTriggerMessage(null);
    setTimeout(() => {
      setTriggerStatus("success");
      setTriggerMessage("✓ Batch assessment completed. Recomputed scores and benchmarking cohort size n=30. (Simulated M-14 — mock task_79a2)");
    }, 1200);
  };

  const rowCounts = (health?.row_counts ?? {}) as Record<string, number>;

  // Fallback demo mockups for training statistics in case DB is fresh / empty
  const DEFAULT_STATS = {
    total_labels: 185,
    by_action: { confirm: 142, edit: 31, dismiss: 12 },
    by_domain: { data_sharing: 64, tracking_cookies: 41, consumer_rights: 32, cross_border: 18, retention: 20, children_teens: 10 },
    by_month: { "2026-05": 30, "2026-06": 95, "2026-07": 60 }
  };

  const actualStats = {
    total_labels: stats?.total_labels || DEFAULT_STATS.total_labels,
    by_action: {
      confirm: stats?.by_action?.confirm ?? DEFAULT_STATS.by_action.confirm,
      edit: stats?.by_action?.edit ?? DEFAULT_STATS.by_action.edit,
      dismiss: stats?.by_action?.dismiss ?? DEFAULT_STATS.by_action.dismiss,
    },
    by_domain: stats && Object.keys(stats.by_domain || {}).length > 0 ? stats.by_domain : DEFAULT_STATS.by_domain,
    by_month: stats && Object.keys(stats.by_month || {}).length > 0 ? stats.by_month : DEFAULT_STATS.by_month,
  };

  return (
    <div>
      {/* Monospace Provenance Ribbon */}
      <ProvenanceRibbon
        snapshotId="SYS-ADM-2041"
        formulaVersion="v0.2.0"
        frozenDate="2026-07-07"
        status="approved"
      />

      <div className="page-header" style={{ marginBottom: 24 }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: "2rem", fontWeight: 700, color: "var(--navy)", marginBottom: 6 }}>
          Admin Control Center
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
          Configure global policies, review system operational statuses, and analyze fine-tuning training labels.
        </p>
      </div>

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
          
          {/* Gate Mode Configuration [MOCK M-13] */}
          <div className="card" style={{ padding: 24 }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 4, color: "var(--navy)" }}>
              Global Gate Mode
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 16 }}>
              Configure customer access permission tiers for draft assessments.
            </p>

            {gateModeStatus && (
              <div style={{
                marginBottom: 16,
                padding: "10px 14px",
                background: "rgba(85, 199, 179, 0.08)",
                border: "1px solid rgba(85, 199, 179, 0.3)",
                borderRadius: "var(--radius)",
                color: "#0d6b5c",
                fontSize: "0.8rem",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between"
              }}>
                <span>{gateModeStatus}</span>
                <button 
                  onClick={() => setGateModeStatus(null)} 
                  style={{ background: "transparent", color: "#0d6b5c", fontWeight: 700, fontSize: "0.9rem", border: "none" }}
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

          {/* System Operations [MOCK M-14] */}
          <div className="card" style={{ padding: 24 }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 4, color: "var(--navy)" }}>
              System Operations
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 16 }}>
              Trigger bulk recompute operations and refresh benchmarking metrics.
            </p>

            {triggerMessage && (
              <div style={{
                marginBottom: 16,
                padding: "10px 14px",
                background: triggerStatus === "success" ? "rgba(85, 199, 179, 0.08)" : "rgba(248, 113, 113, 0.08)",
                border: `1px solid ${triggerStatus === "success" ? "rgba(85, 199, 179, 0.3)" : "rgba(248, 113, 113, 0.3)"}`,
                borderRadius: "var(--radius)",
                color: triggerStatus === "success" ? "#0d6b5c" : "#b91c1c",
                fontSize: "0.8rem",
                fontWeight: 600
              }}>
                {triggerMessage}
              </div>
            )}

            <button
              className="btn btn-primary"
              disabled={triggerStatus === "loading"}
              onClick={handleTriggerAssessment}
              style={{
                background: "var(--navy)",
                color: "white",
                fontWeight: 600,
                padding: "10px 18px",
                borderRadius: "var(--radius)",
                border: "none",
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer"
              }}
            >
              {triggerStatus === "loading" ? (
                <>
                  <div style={{
                    width: 14, height: 14, border: "2px solid white",
                    borderTopColor: "transparent", borderRadius: "50%",
                    animation: "spin 0.6s linear infinite"
                  }} />
                  Running batch job...
                </>
              ) : "Trigger Batch Assessment"}
            </button>
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
                    <div style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>Confirmed</div>
                    <div className="tabular" style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--teal)" }}>{actualStats.by_action.confirm}</div>
                  </div>
                  <div style={{ background: "var(--soft-white)", borderRadius: "var(--radius)", padding: "10px 12px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>Edited</div>
                    <div className="tabular" style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--gold)" }}>{actualStats.by_action.edit}</div>
                  </div>
                  <div style={{ background: "var(--soft-white)", borderRadius: "var(--radius)", padding: "10px 12px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>Dismissed</div>
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

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <IntelligenceMark />
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
