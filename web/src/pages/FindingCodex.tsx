/**
 * Finding Codex — real data from GET /findings/codex
 * No mock data. Fetches the finding_type catalog from Supabase.
 */
import { useState, useMemo, useEffect } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import "../components/furniture.css";

const DOMAINS = [
  "data_sharing", "tracking_cookies", "consumer_rights",
  "cross_border", "sensitive_data", "retention",
  "children_teens", "ai_automated_decisions", "other",
] as const;
type Domain = typeof DOMAINS[number];

function domainLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

interface CodexEntry {
  code: string;
  domain: string;
  title: string;
  default_severity: string;
  sme_authored: boolean;
  regulator_relevance: Record<string, number>;
  recommendations: { title: string; body_template: string; severity_bucket: string }[];
  legal_references: { framework: string; citation: string; title: string; summary: string; official_url: string; is_primary: boolean }[];
}

export function FindingCodex() {
  const [entries, setEntries] = useState<CodexEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeDomain, setActiveDomain] = useState<Domain | "all">("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get("/findings/codex")
      .then((data: { entries: CodexEntry[] }) => setEntries(data.entries || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() =>
    entries.filter(e =>
      (activeDomain === "all" || e.domain === activeDomain) &&
      (search === "" || e.code.toLowerCase().includes(search.toLowerCase()) ||
       e.title.toLowerCase().includes(search.toLowerCase()))
    ),
  [entries, activeDomain, search]);

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <PageHeader
        eyebrow="Codex"
        title="Finding Codex"
        description={`Definitions for all ${entries.length} finding codes from the database catalog — what each code means, the exposure it signals, and linked legal references.`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 24 }}>
        {/* Domain filter */}
        <div className="card" style={{ padding: "16px", alignSelf: "start" }}>
          <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: 12 }}>Filter by domain</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <button
              className={`btn btn-ghost btn-sm ${activeDomain === "all" ? "active" : ""}`}
              onClick={() => setActiveDomain("all")}
              style={{ textAlign: "left", fontWeight: activeDomain === "all" ? 700 : 400, color: activeDomain === "all" ? "var(--exec-blue)" : "var(--text-secondary)", borderLeft: activeDomain === "all" ? "3px solid var(--exec-blue)" : "3px solid transparent", paddingLeft: 12 }}
            >
              All domains
            </button>
            {DOMAINS.map(d => (
              <button
                key={d}
                className={`btn btn-ghost btn-sm ${activeDomain === d ? "active" : ""}`}
                onClick={() => setActiveDomain(activeDomain === d ? "all" : d)}
                style={{ textAlign: "left", fontWeight: activeDomain === d ? 700 : 400, color: activeDomain === d ? "var(--exec-blue)" : "var(--text-secondary)", borderLeft: activeDomain === d ? "3px solid var(--exec-blue)" : "3px solid transparent", paddingLeft: 12 }}
              >
                {domainLabel(d)}
              </button>
            ))}
          </div>
        </div>

        {/* Entries */}
        <div>
          <input
            type="text"
            placeholder={`Search ${filtered.length} finding codes...`}
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: "100%", padding: "10px 14px", border: "1px solid var(--border)", borderRadius: "var(--radius)", marginBottom: 16, fontSize: "0.88rem" }}
          />

          {loading ? (
            <div className="empty-state"><p>Loading codex from database...</p></div>
          ) : filtered.length === 0 ? (
            <div className="empty-state"><p>No finding codes found.</p></div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filtered.map(e => {
                const isOpen = expanded === e.code;
                return (
                  <div key={e.code} className="card" style={{ overflow: "hidden" }}>
                    <button
                      onClick={() => setExpanded(isOpen ? null : e.code)}
                      style={{
                        width: "100%", textAlign: "left", padding: "14px 18px",
                        display: "flex", alignItems: "center", gap: 12,
                        border: "none", background: "transparent", cursor: "pointer",
                      }}
                    >
                      <span style={{
                        background: "var(--navy)", color: "white",
                        fontFamily: "var(--font-data)", fontSize: "0.72rem", fontWeight: 700,
                        padding: "3px 8px", borderRadius: 4, flexShrink: 0,
                      }}>{e.code}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--navy)" }}>{e.title}</div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{domainLabel(e.domain)}</div>
                      </div>
                      <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{isOpen ? "↑" : "↓"}</span>
                    </button>

                    {isOpen && (
                      <div style={{ padding: "0 18px 18px", borderTop: "1px solid var(--border)" }}>
                        <div style={{ marginTop: 14 }}>
                          <div className="micro-label">Severity</div>
                          <span className={`badge badge-${e.default_severity}`} style={{ textTransform: "uppercase" }}>
                            {e.default_severity}
                          </span>
                          {!e.sme_authored && (
                            <span style={{ marginLeft: 8, fontSize: "0.72rem", color: "var(--text-muted)" }}>
                              (Pending SME review)
                            </span>
                          )}
                        </div>

                        {/* Regulator relevance */}
                        {Object.keys(e.regulator_relevance).length > 0 && (
                          <div style={{ marginTop: 12 }}>
                            <div className="micro-label">Regulator Relevance</div>
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                              {Object.entries(e.regulator_relevance).map(([reg, weight]) => (
                                <span key={reg} style={{
                                  padding: "2px 8px", borderRadius: 4,
                                  background: "var(--soft-white)", border: "1px solid var(--border)",
                                  fontSize: "0.75rem", fontWeight: 600, color: "var(--navy)",
                                }}>
                                  {reg}: {(weight as number).toFixed(1)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Legal references */}
                        {e.legal_references.length > 0 && (
                          <div style={{ marginTop: 12 }}>
                            <div className="micro-label">Legal References</div>
                            {e.legal_references.map((lr, i) => (
                              <div key={i} style={{ marginTop: 6, fontSize: "0.82rem" }}>
                                <span style={{ fontWeight: 700, color: "var(--navy)" }}>{lr.framework}</span>
                                {" · "}
                                <span>{lr.citation}</span>
                                {lr.is_primary && <span style={{ marginLeft: 6, padding: "1px 5px", borderRadius: 3, background: "var(--navy)", color: "white", fontSize: "0.62rem", fontWeight: 700 }}>PRIMARY</span>}
                                {lr.official_url && (
                                  <a href={lr.official_url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 8, fontSize: "0.75rem", color: "var(--exec-blue)" }}>
                                    Official source ↗
                                  </a>
                                )}
                                {lr.summary && <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 2 }}>{lr.summary}</div>}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Recommendations */}
                        {e.recommendations.length > 0 && (
                          <div style={{ marginTop: 12 }}>
                            <div className="micro-label">Recommendation</div>
                            <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: 4 }}>
                              {e.recommendations[0].body_template?.replace(/\{[^}]+\}/g, "[...]") ?? "See report."}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
