/**
 * F11 — White-Label Partner Portal · UI (built against mocks, M-19–M-22).
 *
 * Product 3 surface: a partner delivers Visentix intelligence under its own
 * brand. This page is UI-only ahead of the tenancy/metering backend — client
 * workspaces, branding controls, API-key metering, anonymized feed catalog, and
 * the report-template picker all render from ./mockData.
 *
 * Guardrail posture (F11): partner scope isolation (a partner sees only its own
 * workspaces, DIR-005 — mocked here as a single partner's data), usage-limit
 * quota states surfaced, feeds below minimum sample suppressed (DIR-006) with
 * confidence metadata on every feed. No provenance ribbon — nothing here is a
 * reproducible snapshot (keeps the ribbon's meaning exact, per the Admin note).
 */
import { useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import {
  CONTRACT, WORKSPACES, BRANDING, API_KEYS, API_SURFACES,
  FEEDS, TEMPLATES,
} from "./mockData";
import "../../components/furniture.css";
import "./partner.css";

/* Meter color by usage ratio → drives the quota-caution / limit-reached states. */
function meterColor(ratio: number): string {
  if (ratio >= 1) return "var(--red)";     // usage-limit reached
  if (ratio >= 0.85) return "var(--gold)"; // caution — approaching limit
  return "var(--teal)";
}

function pct(used: number, limit: number): number {
  return limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
}

export function PartnerPortal() {
  const [selectedTemplate, setSelectedTemplate] = useState("assessment");
  const [flash, setFlash] = useState<string | null>(null);

  // Mock actions — UI affordances ahead of the backend. Register intent, no state change.
  const mockAction = (msg: string) => {
    setFlash(msg);
    setTimeout(() => setFlash(null), 4000);
  };

  const apiRatio = CONTRACT.apiCallsUsed / CONTRACT.apiCallLimit;

  return (
    <div>
      <PageHeader
        eyebrow="Partner"
        title="Partner Portal"
        description="Manage client workspaces, apply your branding, meter API usage against your contract, and pull anonymized intelligence feeds — all under your brand."
        actions={
          <div style={{ textAlign: "right" }}>
            <div style={{ fontWeight: 700, color: "var(--navy)" }}>{CONTRACT.partnerName}</div>
            <div style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>{CONTRACT.tier}</div>
          </div>
        }
      />

      {flash && (
        <div style={{
          background: "rgba(0,95,163,0.08)", border: "1px solid rgba(0,95,163,0.25)",
          color: "var(--exec-blue)", borderRadius: "var(--radius)", padding: "10px 16px",
          fontSize: "0.84rem", marginBottom: 20,
        }} role="status">{flash}</div>
      )}

      <div className="pp-grid">
        {/* ── Contract & usage ─────────────────────────────────────────── */}
        <section className="pp-card">
          <div className="pp-card-title">Contract & Usage</div>
          <div className="pp-card-sub">Billing period ends {CONTRACT.periodEnds}.</div>
          <div className="pp-usage">
            <div className="pp-usage-cell">
              <div className="k">{WORKSPACES.length}<span style={{ color: "var(--text-muted)", fontSize: "1rem" }}> / {CONTRACT.workspaceLimit}</span></div>
              <span className="l">Client workspaces</span>
              <div className="pp-meter"><span style={{ width: `${pct(WORKSPACES.length, CONTRACT.workspaceLimit)}%`, background: meterColor(WORKSPACES.length / CONTRACT.workspaceLimit) }} /></div>
            </div>
            <div className="pp-usage-cell">
              <div className="k">{CONTRACT.apiCallsUsed.toLocaleString()}</div>
              <span className="l">API calls / {CONTRACT.apiCallLimit.toLocaleString()}</span>
              <div className="pp-meter"><span style={{ width: `${pct(CONTRACT.apiCallsUsed, CONTRACT.apiCallLimit)}%`, background: meterColor(apiRatio) }} /></div>
              {apiRatio >= 0.85 && (
                <div className="pp-quota-note" style={{ color: meterColor(apiRatio) }}>
                  {apiRatio >= 1 ? "Quota reached — calls are being rejected." : `Approaching quota — ${Math.round((1 - apiRatio) * 100)}% remaining.`}
                </div>
              )}
            </div>
            <div className="pp-usage-cell">
              <div className="k">{API_KEYS.filter(k => k.status === "active").length}</div>
              <span className="l">Active API keys</span>
            </div>
          </div>
        </section>

        {/* ── Client workspaces ────────────────────────────────────────── */}
        <section className="pp-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div className="pp-card-title">Client Workspaces</div>
              <div className="pp-card-sub">You see only your own clients (scope-isolated per contract).</div>
            </div>
            <button
              className="btn btn-primary"
              disabled={WORKSPACES.length >= CONTRACT.workspaceLimit}
              onClick={() => mockAction("New workspace — wired to the tenancy backend in a later pass (M-19).")}
            >+ New workspace</button>
          </div>
          <div>
            {WORKSPACES.map(ws => (
              <div key={ws.id} className="pp-ws-row">
                <span className="pp-ws-name">{ws.clientName}</span>
                <span className="pp-ws-meta">{ws.industry}</span>
                <span className="pp-ws-meta"><span className="pp-num">{ws.assessments}</span> assessments</span>
                {ws.branded ? <span className="pp-pill branded">Branded</span> : <span className="pp-pill" style={{ color: "var(--text-muted)" }}>Default brand</span>}
                <span className={`pp-pill ${ws.status}`}>{ws.status}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Branding controls + live preview ─────────────────────────── */}
        <section className="pp-card">
          <div className="pp-card-title">Branding</div>
          <div className="pp-card-sub">Applied to every branded report and export for your clients.</div>
          <div className="pp-brand">
            <div>
              <div className="pp-logo-drop" onClick={() => mockAction("Logo upload — asset store wired later (M-22).")} role="button" tabIndex={0}
                onKeyDown={e => e.key === "Enter" && mockAction("Logo upload — asset store wired later (M-22).")}>
                Drop logo or click to upload · current: <b>{BRANDING.logoLabel}</b>
              </div>
              <div style={{ marginTop: 14 }}>
                <div className="pp-swatch-row">
                  <span className="pp-swatch" style={{ background: BRANDING.primary }} />
                  <div><div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--navy)" }}>Primary</div><div className="pp-key-mono" style={{ fontSize: "0.74rem" }}>{BRANDING.primary}</div></div>
                </div>
                <div className="pp-swatch-row">
                  <span className="pp-swatch" style={{ background: BRANDING.accent }} />
                  <div><div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--navy)" }}>Accent</div><div className="pp-key-mono" style={{ fontSize: "0.74rem" }}>{BRANDING.accent}</div></div>
                </div>
              </div>
            </div>
            {/* Live preview: the same report furniture under the partner's palette */}
            <div>
              <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: 8 }}>Report preview</div>
              <div className="pp-preview">
                <div className="pp-preview-head" style={{ background: BRANDING.primary }}>
                  <span className="pp-preview-logo">{BRANDING.logoLabel}</span>
                  <span style={{ fontSize: "0.68rem", opacity: 0.85 }}>Privacy Intelligence Report</span>
                </div>
                <div className="pp-preview-body">
                  <div className="pp-preview-bar" style={{ width: "70%", background: BRANDING.accent }} />
                  <div className="pp-preview-bar" style={{ width: "45%", background: "var(--border)" }} />
                  <div className="pp-preview-bar" style={{ width: "60%", background: "var(--border)" }} />
                </div>
                <div className="pp-preview-foot">{BRANDING.reportFooter}</div>
              </div>
            </div>
          </div>
        </section>

        {/* ── API keys ─────────────────────────────────────────────────── */}
        <section className="pp-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div className="pp-card-title">API Keys & Usage</div>
              <div className="pp-card-sub">Per-key rate and usage limits enforced by contract. Expired keys are rejected.</div>
            </div>
            <button className="btn btn-primary" onClick={() => mockAction("Create key — issuance wired to the metering backend later (M-20).")}>+ Create key</button>
          </div>
          <table className="pp-keys">
            <thead>
              <tr><th>Label</th><th>Key</th><th>Scope</th><th>Rate</th><th>Usage</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {API_KEYS.map(k => {
                const ratio = k.callLimit > 0 ? k.callsThisPeriod / k.callLimit : 0;
                return (
                  <tr key={k.id} style={{ opacity: k.status === "expired" ? 0.6 : 1 }}>
                    <td style={{ fontWeight: 600, color: "var(--navy)" }}>{k.label}</td>
                    <td className="pp-key-mono">{k.maskedKey}</td>
                    <td>{k.scope}</td>
                    <td className="pp-key-mono">{k.rateLimit}</td>
                    <td style={{ minWidth: 130 }}>
                      <div style={{ fontFamily: "var(--font-data)", fontVariantNumeric: "tabular-nums", fontSize: "0.78rem" }}>
                        {k.callsThisPeriod.toLocaleString()} / {k.callLimit.toLocaleString()}
                      </div>
                      <div className="pp-meter" style={{ marginTop: 4 }}><span style={{ width: `${pct(k.callsThisPeriod, k.callLimit)}%`, background: meterColor(ratio) }} /></div>
                    </td>
                    <td><span className={`pp-pill ${k.status}`}>{k.status}</span></td>
                    <td>
                      {k.status === "active" && (
                        <button className="btn" style={{ fontSize: "0.74rem", padding: "4px 10px" }}
                          onClick={() => mockAction(`Revoke ${k.label} — wired later (M-20).`)}>Revoke</button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="pp-card-sub" style={{ marginTop: 14, marginBottom: 0 }}>
            <b style={{ color: "var(--navy)" }}>Intelligence API suite</b> — every payload carries VCI, formula_version, and explainability refs where permitted:
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {API_SURFACES.map(s => (
                <span key={s.name} title={s.desc} style={{ fontSize: "0.72rem", padding: "3px 10px", borderRadius: 999, background: "var(--soft-white)", border: "1px solid var(--border)", color: "var(--navy)", fontWeight: 600 }}>{s.name}</span>
              ))}
            </div>
          </div>
        </section>

        {/* ── Anonymized feeds ─────────────────────────────────────────── */}
        <section className="pp-card">
          <div className="pp-card-title">Anonymized Intelligence Feeds</div>
          <div className="pp-card-sub">Aggregated, de-identified datasets. Every feed carries confidence metadata; feeds below the minimum sample are suppressed, not shown at low confidence.</div>
          <div className="pp-feeds">
            {FEEDS.map(f => (
              <div key={f.datasetId} className={`pp-feed ${f.suppressed ? "suppressed" : ""}`}>
                <div className="pp-feed-id">{f.datasetId}</div>
                <div className="pp-feed-name">{f.name}</div>
                {f.suppressed ? (
                  <div className="pp-feed-meta" style={{ color: "var(--text-secondary)" }}>
                    <span><b style={{ color: "var(--gold)" }}>Suppressed</b> — cohort below minimum sample (n={f.cohortN}). Withheld rather than published at low confidence.</span>
                  </div>
                ) : (
                  <div className="pp-feed-meta">
                    <span><b>Schema</b> {f.schemaVersion} · <b>Refreshed</b> {f.refreshDate}</span>
                    <span><b>Cohort</b> n={f.cohortN} · <b>VCI</b> {f.vci}</span>
                    <span><b>Permitted use</b> {f.permittedUse}</span>
                    <button className="btn" style={{ marginTop: 8, fontSize: "0.74rem", padding: "5px 12px", alignSelf: "start" }}
                      onClick={() => mockAction(`Pull ${f.datasetId} — feed API wired later (M-21).`)}>Pull feed</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ── Report templates ─────────────────────────────────────────── */}
        <section className="pp-card">
          <div className="pp-card-title">Report Templates</div>
          <div className="pp-card-sub">Same intelligence, rendered to the format each client needs. Selected template applies your branding above.</div>
          <div className="pp-templates">
            {TEMPLATES.map(t => (
              <button
                key={t.id}
                className={`pp-template ${selectedTemplate === t.id ? "selected" : ""}`}
                aria-pressed={selectedTemplate === t.id}
                onClick={() => setSelectedTemplate(t.id)}
              >
                <div className="pp-template-name">{t.name}</div>
                <div className="pp-template-desc">{t.desc}</div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
