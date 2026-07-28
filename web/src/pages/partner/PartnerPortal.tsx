/**
 * F20 — Partner Portal · REAL UI (replaces the F11 mock M-19–M-22).
 *
 * partner_admin-gated. Clients tab (workspace cards + New Client modal with
 * fetched industry taxonomy) → Client view (three-mode intake reusing the F01
 * pattern; report list with the SAME gate language customers see) → Feed tab
 * (API-key create/copy-once/revoke, permitted-use, last-access) → Branding
 * (logo upload 2 MB cap + color, preview). Numbers are never partner-editable;
 * branded PDF renders our numbers with the partner header.
 */
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { api, ApiError } from "../../lib/api";
import "../../components/furniture.css";
import "./partner.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
// Same gate language customers see — no special casing (F20).
const DRAFT_GATE_TEXT = "pending Visentix expert review";

interface Industry { id: string; label: string; }
interface LatestStatus { assessment_id: string; snapshot_id: string | null; review_status: string; last_activity: string | null; }
interface Workspace { id: string; partner_id: string; client_org_id: string; name: string; created_at: string; latest_status: LatestStatus | null; }
interface ApiKey { api_key_id: string; label: string; masked: string; created_at: string; last_used_at: string | null; revoked: boolean; }

function authToken(): string {
  try { return JSON.parse(localStorage.getItem("visentix-auth-session") || "{}").access_token || ""; }
  catch { return ""; }
}

const StatusChip = ({ status }: { status: string }) => (
  <span className={`pp-chip st-${status}`} title={status === "draft" ? DRAFT_GATE_TEXT : status}>
    {status === "draft" ? DRAFT_GATE_TEXT : status.replace(/_/g, " ")}
  </span>
);

export function PartnerPortal() {
  const [tab, setTab] = useState<"clients" | "feed" | "branding">("clients");
  const [flash, showFlash] = useFlash();
  const [selectedWs, setSelectedWs] = useState<Workspace | null>(null);

  return (
    <div>
      <PageHeader
        eyebrow="Partner"
        title="Partner Workspace"
        description="Deliver Visentix intelligence under your brand. Client workspaces run the same pipeline — every assessment is held for Visentix expert review before it can be shared, and branded reports carry the same numbers as our own."
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            {(["clients", "feed", "branding"] as const).map(t => (
              <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`}
                      onClick={() => { setTab(t); setSelectedWs(null); }}>
                {t === "clients" ? "Clients" : t === "feed" ? "Data Feed" : "Branding"}
              </button>
            ))}
          </div>
        }
      />
      <FlashNotice message={flash} />
      {tab === "clients" && !selectedWs && <ClientsTab onOpen={setSelectedWs} showFlash={showFlash} />}
      {tab === "clients" && selectedWs && <ClientView ws={selectedWs} onBack={() => setSelectedWs(null)} showFlash={showFlash} />}
      {tab === "feed" && <FeedTab showFlash={showFlash} />}
      {tab === "branding" && <BrandingTab showFlash={showFlash} />}
    </div>
  );
}

// ── Clients tab ──────────────────────────────────────────────
function ClientsTab({ onOpen, showFlash }: { onOpen: (w: Workspace) => void; showFlash: (m: string) => void }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [clientName, setClientName] = useState("");
  const [industry, setIndustry] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setWorkspaces(await api.get("/partner/workspaces")); }
    catch (e) { if (e instanceof ApiError && e.status === 403) showFlash("Partner access required."); }
  }, [showFlash]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/partner/industries").then(setIndustries).catch(() => setIndustries([])); }, []);

  const create = async () => {
    setBusy(true);
    try {
      await api.post("/partner/workspaces", { name, client_org: { name: clientName, industry: industry || undefined } });
      setModalOpen(false); setName(""); setClientName(""); setIndustry("");
      showFlash("Client workspace created."); load();
    } catch (e) { showFlash(e instanceof ApiError ? `Could not create: ${e.message}` : "Create failed."); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <div className="pp-toolbar">
        <span className="pp-count">{workspaces.length} client{workspaces.length === 1 ? "" : "s"}</span>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)}>+ New Client</button>
      </div>
      {workspaces.length === 0 ? (
        <div className="pp-card"><div className="pp-empty">No client workspaces yet. Create one to begin.</div></div>
      ) : (
        <div className="pp-cards">
          {workspaces.map(w => (
            <button key={w.id} className="pp-client-card" onClick={() => onOpen(w)}>
              <div className="pp-client-name">{w.name}</div>
              <div className="pp-client-meta">
                {w.latest_status ? <StatusChip status={w.latest_status.review_status} /> : <span className="pp-chip st-none">no assessment yet</span>}
              </div>
              <div className="pp-client-activity">{w.latest_status?.last_activity ? `Last activity ${w.latest_status.last_activity}` : "—"}</div>
            </button>
          ))}
        </div>
      )}

      {modalOpen && (
        <div className="pp-modal-backdrop" onClick={() => setModalOpen(false)}>
          <div className="pp-modal" onClick={e => e.stopPropagation()}>
            <div className="pp-modal-title">New Client</div>
            <label className="pp-label">Workspace name<input className="pp-input" value={name} onChange={e => setName(e.target.value)} placeholder="Acme Retail" /></label>
            <label className="pp-label">Client organisation<input className="pp-input" value={clientName} onChange={e => setClientName(e.target.value)} placeholder="Acme Retail Inc." /></label>
            <label className="pp-label">Industry
              <select className="pp-input" value={industry} onChange={e => setIndustry(e.target.value)}>
                <option value="">— select —</option>
                {industries.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
              </select>
            </label>
            <div className="pp-modal-actions">
              <button className="btn" onClick={() => setModalOpen(false)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !name.trim() || !clientName.trim()} onClick={create}>{busy ? "Creating…" : "Create"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Client view (intake + report list) ───────────────────────
type Mode = "url" | "text" | "upload";
function ClientView({ ws, onBack, showFlash }: { ws: Workspace; onBack: () => void; showFlash: (m: string) => void }) {
  const [mode, setMode] = useState<Mode>("url");
  const [urlVal, setUrlVal] = useState("");
  const [textVal, setTextVal] = useState("");
  const [fileVal, setFileVal] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState<LatestStatus | null>(ws.latest_status);

  const refresh = useCallback(async () => {
    try {
      const list: Workspace[] = await api.get("/partner/workspaces");
      const me = list.find(w => w.id === ws.id);
      if (me) setLatest(me.latest_status);
    } catch { /* ignore */ }
  }, [ws.id]);

  const submit = async () => {
    if (mode === "url" && !urlVal.trim()) return;
    if (mode === "text" && !textVal.trim()) return;
    if (mode === "upload" && !fileVal) return;
    setBusy(true);
    try {
      const fd = new FormData();
      if (mode === "url") fd.append("url", urlVal);
      else if (mode === "text") fd.append("text", textVal);
      else if (fileVal) fd.append("file", fileVal, fileVal.name);
      await api.postForm(`/partner/workspaces/${ws.id}/assessments`, fd);
      showFlash("Assessment submitted — held for Visentix expert review before it can be shared.");
      setUrlVal(""); setTextVal(""); setFileVal(null); refresh();
    } catch (e) { showFlash(e instanceof ApiError ? `Submit failed: ${e.message}` : "Submit failed."); }
    finally { setBusy(false); }
  };

  const downloadBranded = async (snapshotId: string) => {
    try {
      const res = await fetch(`${API_BASE}/partner/reports/${snapshotId}.pdf`, {
        headers: { Authorization: `Bearer ${authToken()}` },
      });
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = u; a.download = `report-${snapshotId.slice(0, 8)}.pdf`; a.click();
      URL.revokeObjectURL(u);
    } catch { showFlash("Could not download the branded report."); }
  };

  return (
    <div>
      <button className="btn" onClick={onBack}>← Clients</button>
      <h2 className="pp-view-title">{ws.name}</h2>

      <section className="pp-card">
        <div className="pp-card-title">New assessment</div>
        <div className="pp-modes">
          {(["url", "text", "upload"] as const).map(m => (
            <button key={m} className={`pp-mode ${mode === m ? "on" : ""}`} onClick={() => setMode(m)}>
              {m === "url" ? "URL" : m === "text" ? "Paste text" : "Upload"}
            </button>
          ))}
        </div>
        {mode === "url" && <input className="pp-input" placeholder="https://client.example/privacy" value={urlVal} onChange={e => setUrlVal(e.target.value)} />}
        {mode === "text" && <textarea className="pp-textarea" placeholder="Paste the privacy notice text…" value={textVal} onChange={e => setTextVal(e.target.value)} />}
        {mode === "upload" && <input type="file" accept=".pdf,.docx,.txt" onChange={e => setFileVal(e.target.files?.[0] || null)} />}
        <button className="btn btn-primary" style={{ marginTop: 12 }} disabled={busy} onClick={submit}>{busy ? "Submitting…" : "Run assessment"}</button>
      </section>

      <section className="pp-card">
        <div className="pp-card-title">Reports</div>
        {!latest ? (
          <div className="pp-empty">No assessments yet for this client.</div>
        ) : (
          <div className="pp-report-row">
            <span className="pp-report-id">Assessment {latest.assessment_id.slice(0, 8)}</span>
            <StatusChip status={latest.review_status} />
            {latest.review_status === "approved" && latest.snapshot_id ? (
              <button className="btn" onClick={() => downloadBranded(latest.snapshot_id!)}>Download branded PDF</button>
            ) : (
              <span className="pp-report-note">Branded report available once approved.</span>
            )}
          </div>
        )}
        <div className="pp-gate-note">Every client report is held for Visentix expert review — partners see the same gate as our direct customers.</div>
      </section>
    </div>
  );
}

// ── Feed tab (API keys + permitted-use + access) ─────────────
function FeedTab({ showFlash }: { showFlash: (m: string) => void }) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [label, setLabel] = useState("");
  const [freshKey, setFreshKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setKeys(await api.get("/partner/api-keys")); } catch { /* ignore */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      const res = await api.post("/partner/api-keys", { label });
      setFreshKey(res.api_key); setLabel(""); load();
    } catch { showFlash("Could not create key."); }
  };
  const revoke = async (id: string) => {
    try { await api.del(`/partner/api-keys/${id}`); showFlash("Key revoked — effective immediately."); load(); }
    catch { showFlash("Revoke failed."); }
  };

  return (
    <div>
      <section className="pp-card">
        <div className="pp-card-title">White-label data feed</div>
        <div className="pp-card-sub">
          Aggregate privacy intelligence by industry cohort. No organisation identities, cohort membership, or raw
          clause text is included; cohorts below the minimum sample are suppressed. Redistribution requires a data
          license agreement.
        </div>
        <div className="pp-key-create">
          <input className="pp-input" placeholder="Key label (e.g. prod)" value={label} onChange={e => setLabel(e.target.value)} />
          <button className="btn btn-primary" onClick={create}>Create API key</button>
        </div>
        {freshKey && (
          <div className="pp-fresh-key">
            <strong>Copy this key now — it is shown only once:</strong>
            <code>{freshKey}</code>
            <button className="btn" onClick={() => { navigator.clipboard?.writeText(freshKey); showFlash("Key copied."); }}>Copy</button>
            <button className="btn" onClick={() => setFreshKey(null)}>Done</button>
          </div>
        )}
      </section>

      <section className="pp-card">
        <div className="pp-card-title">Keys</div>
        {keys.length === 0 ? <div className="pp-empty">No API keys yet.</div> : (
          <table className="pp-keys">
            <thead><tr><th>Label</th><th>Key</th><th>Last used</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {keys.map(k => (
                <tr key={k.api_key_id}>
                  <td>{k.label || <em>(unlabeled)</em>}</td>
                  <td className="pp-mono">{k.masked}</td>
                  <td>{k.last_used_at || "never"}</td>
                  <td>{k.revoked ? <span className="pp-chip st-revoked">revoked</span> : <span className="pp-chip st-approved">active</span>}</td>
                  <td>{!k.revoked && <button className="btn" onClick={() => revoke(k.api_key_id)}>Revoke</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

// ── Branding tab ─────────────────────────────────────────────
function BrandingTab({ showFlash }: { showFlash: (m: string) => void }) {
  const [color, setColor] = useState("#0f3460");
  const [logo, setLogo] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("brand_color", color);
      if (logo) fd.append("logo", logo, logo.name);
      await api.putForm("/partner/branding", fd);
      showFlash("Branding saved. Existing approved reports keep the branding they were approved with.");
    } catch (e) { showFlash(e instanceof ApiError ? `Save failed: ${e.message}` : "Save failed."); }
    finally { setBusy(false); }
  };

  return (
    <section className="pp-card">
      <div className="pp-card-title">Branding</div>
      <div className="pp-card-sub">Applied as a header band on branded reports. Branding never changes any number or wording in the report body, and a report keeps the branding it had when the Visentix expert approved it.</div>
      <div className="pp-branding-grid">
        <div>
          <label className="pp-label">Brand color<input type="color" className="pp-color" value={color} onChange={e => setColor(e.target.value)} /></label>
          <label className="pp-label">Logo (PNG/JPG, max 2 MB)
            <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={e => setLogo(e.target.files?.[0] || null)} />
          </label>
          <button className="btn btn-primary" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save branding"}</button>
        </div>
        <div className="pp-preview" style={{ borderTop: `6px solid ${color}` }}>
          <div className="pp-preview-band">
            {logo ? <img src={URL.createObjectURL(logo)} alt="" style={{ maxHeight: 40 }} /> : <span style={{ color, fontWeight: 700 }}>Your logo</span>}
            <span className="pp-preview-tag">Delivered via Visentix</span>
          </div>
          <div className="pp-preview-body">Report body — the same numbers as our product. Branding only adds this header.</div>
        </div>
      </div>
    </section>
  );
}
