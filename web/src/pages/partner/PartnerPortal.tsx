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
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "../../components/PageHeader";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { api, ApiError } from "../../lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { statusLabel } from "../../lib/labels";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
// Same gate language customers see — no special casing (F20).
/* Review status is a KIND, mapped once. It used to be a class interpolated off
   the raw enum ("pp-chip st-in_review"), so an unmapped status rendered an
   unstyled chip carrying the database's own word. */
const STATUS_VARIANT: Record<string, "provisional" | "verified" | "secondary" | "default"> = {
  draft: "provisional",
  in_review: "default",
  approved: "verified",
  revoked: "secondary",
  none: "secondary",
};

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
  <Badge variant={STATUS_VARIANT[status] ?? "secondary"} title={status === "draft" ? DRAFT_GATE_TEXT : statusLabel(status)}>
    {statusLabel(status)}
  </Badge>
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
          <div className="flex gap-2">
            {(["clients", "feed", "branding"] as const).map(t => (
              <Button key={t} type="button" size="sm" variant={tab === t ? "default" : "outline"} aria-pressed={tab === t}
                      onClick={() => { setTab(t); setSelectedWs(null); }}>
                {t === "clients" ? "Clients" : t === "feed" ? "Data Feed" : "Branding"}
              </Button>
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

  useEffect(() => {
    const initialLoad = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);
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
      <div className="mb-4 flex items-center justify-between">
        <span className="text-[0.86rem] font-semibold text-muted-foreground">{workspaces.length} client{workspaces.length === 1 ? "" : "s"}</span>
        <Button onClick={() => setModalOpen(true)}>+ New Client</Button>
      </div>
      {workspaces.length === 0 ? (
        <Card className="rounded-lg border bg-card px-5.5 py-5"><div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">No client workspaces yet. Create one to begin.</div></Card>
      ) : (
        <div className="grid gap-3.5 [grid-template-columns:repeat(auto-fill,minmax(240px,1fr))]">
          {workspaces.map(w => (
            <button key={w.id} className="rounded-lg border bg-card p-4 text-left hover:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50" onClick={() => onOpen(w)}>
              <div className="mb-2 font-sans text-base font-bold">{w.name}</div>
              <div className="mb-2">
                {w.latest_status ? <StatusChip status={w.latest_status.review_status} /> : <Badge variant="secondary">No assessment yet</Badge>}
              </div>
              <div className="text-[0.76rem] text-muted-foreground">{w.latest_status?.last_activity ? `Last activity ${w.latest_status.last_activity}` : "—"}</div>
            </button>
          ))}
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[color-mix(in_oklab,var(--primary)_35%,transparent)]" onClick={() => setModalOpen(false)}>
          <div className="w-[min(440px,92vw)] rounded-lg border bg-card p-6 shadow-lg" onClick={e => e.stopPropagation()}>
            <div className="mb-4 font-sans text-[1.1rem] font-bold">New Client</div>
            <label className="mb-3 block text-[0.8rem] font-semibold text-muted-foreground">Workspace name<input className="mt-1.5 block w-full rounded-md border bg-transparent px-3 py-2 text-[0.88rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={name} onChange={e => setName(e.target.value)} placeholder="Acme Retail" /></label>
            <label className="mb-3 block text-[0.8rem] font-semibold text-muted-foreground">Client organisation<input className="mt-1.5 block w-full rounded-md border bg-transparent px-3 py-2 text-[0.88rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={clientName} onChange={e => setClientName(e.target.value)} placeholder="Acme Retail Inc." /></label>
            <label className="mb-3 block text-[0.8rem] font-semibold text-muted-foreground">Industry
              <select className="mt-1.5 block w-full rounded-md border bg-transparent px-3 py-2 text-[0.88rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" value={industry} onChange={e => setIndustry(e.target.value)}>
                <option value="">— select —</option>
                {industries.map(i => <option key={i.id} value={i.id}>{i.label}</option>)}
              </select>
            </label>
            <div className="mt-4.5 flex justify-end gap-2">
              <Button onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button disabled={busy || !name.trim() || !clientName.trim()} onClick={create}>{busy ? "Creating…" : "Create"}</Button>
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
      <Button onClick={onBack}>← Clients</Button>
      <h2 className="my-3 mb-4.5 font-sans text-lg font-semibold">{ws.name}</h2>

      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <Card className="mb-1 font-sans text-[1.1rem] font-semibold">New assessment</Card>
        <div className="mb-3 flex gap-2">
          {(["url", "text", "upload"] as const).map(m => (
            <Button key={m} type="button" size="sm" variant={mode === m ? "default" : "outline"}
              className="rounded-full" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m === "url" ? "URL" : m === "text" ? "Paste text" : "Upload"}
            </Button>
          ))}
        </div>
        {mode === "url" && <input className="mt-1.5 block w-full rounded-md border bg-transparent px-3 py-2 text-[0.88rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" placeholder="https://client.example/privacy" value={urlVal} onChange={e => setUrlVal(e.target.value)} />}
        {mode === "text" && <textarea className="mt-1.5 block min-h-[120px] w-full resize-y rounded-md border bg-transparent px-3 py-2.5 font-data text-[0.84rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" placeholder="Paste the privacy notice text…" value={textVal} onChange={e => setTextVal(e.target.value)} />}
        {mode === "upload" && <input type="file" accept=".pdf,.docx,.txt" onChange={e => setFileVal(e.target.files?.[0] || null)} />}
        <Button style={{ marginTop: 12 }} disabled={busy} onClick={submit}>{busy ? "Submitting…" : "Run assessment"}</Button>
      </Card>

      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <Card className="mb-1 font-sans text-[1.1rem] font-semibold">Reports</Card>
        {!latest ? (
          <div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">No assessments yet for this client.</div>
        ) : (
          <div className="flex items-center gap-3 py-2.5">
            <span className="font-data text-[0.82rem] font-semibold">Assessment {latest.assessment_id.slice(0, 8)}</span>
            <StatusChip status={latest.review_status} />
            {latest.review_status === "approved" && latest.snapshot_id ? (
              <Button onClick={() => downloadBranded(latest.snapshot_id!)}>Download branded PDF</Button>
            ) : (
              <span className="text-[0.8rem] italic text-muted-foreground">Branded report available once approved.</span>
            )}
          </div>
        )}
        <div className="mt-2 border-t pt-2.5 text-[0.78rem] text-muted-foreground">Every client report is held for Visentix expert review — partners see the same gate as our direct customers.</div>
      </Card>
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
  useEffect(() => {
    const initialLoad = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);

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
      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <Card className="mb-1 font-sans text-[1.1rem] font-semibold">White-label data feed</Card>
        <Card className="mb-4 text-[0.82rem] leading-snug text-muted-foreground">
          Aggregate privacy intelligence by industry cohort. No organisation identities, cohort membership, or raw
          clause text is included; cohorts below the minimum sample are suppressed. Redistribution requires a data
          license agreement.
        </Card>
        <div className="mt-3 flex gap-2 [&>input]:mt-0 [&>input]:flex-1">
          <input className="mt-1.5 block w-full rounded-md border bg-transparent px-3 py-2 text-[0.88rem] shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50" placeholder="Key label (e.g. prod)" value={label} onChange={e => setLabel(e.target.value)} />
          <Button onClick={create}>Create API key</Button>
        </div>
        {freshKey && (
          <div className="mt-3.5 flex flex-wrap items-center gap-2.5 rounded-md border border-[color-mix(in_oklab,var(--provisional)_50%,transparent)] bg-[color-mix(in_oklab,var(--provisional)_12%,transparent)] p-3 [&_code]:rounded-sm [&_code]:bg-card [&_code]:px-2 [&_code]:py-1 [&_code]:font-data [&_code]:text-[0.82rem]">
            <strong>Copy this key now — it is shown only once:</strong>
            <code>{freshKey}</code>
            <Button onClick={() => { navigator.clipboard?.writeText(freshKey); showFlash("Key copied."); }}>Copy</Button>
            <Button onClick={() => setFreshKey(null)}>Done</Button>
          </div>
        )}
      </Card>

      <Card className="rounded-lg border bg-card px-5.5 py-5">
        <Card className="mb-1 font-sans text-[1.1rem] font-semibold">Keys</Card>
        {keys.length === 0 ? <div className="px-5 py-6 text-center text-[0.86rem] text-muted-foreground">No API keys yet.</div> : (
          <table className="w-full border-collapse [&_th]:border-b [&_th]:px-2.5 [&_th]:py-2 [&_th]:text-left [&_th]:text-[0.68rem] [&_th]:font-bold [&_th]:uppercase [&_th]:tracking-wider [&_th]:text-muted-foreground [&_td]:border-b [&_td]:p-2.5 [&_td]:align-middle [&_td]:text-[0.82rem] [&_tr:last-child_td]:border-b-0">
            <thead><tr><th>Label</th><th>Key</th><th>Last used</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {keys.map(k => (
                <tr key={k.api_key_id}>
                  <td>{k.label || <em>(unlabeled)</em>}</td>
                  <td className="font-data text-[0.8rem] tabular-nums">{k.masked}</td>
                  <td>{k.last_used_at || "never"}</td>
                  <td>{k.revoked ? <span >revoked</span> : <span >active</span>}</td>
                  <td>{!k.revoked && <Button onClick={() => revoke(k.api_key_id)}>Revoke</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

// ── Branding tab ─────────────────────────────────────────────
function BrandingTab({ showFlash }: { showFlash: (m: string) => void }) {
  const [color, setColor] = useState("var(--primary)");
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
    <Card className="rounded-lg border bg-card px-5.5 py-5">
      <Card className="mb-1 font-sans text-[1.1rem] font-semibold">Branding</Card>
      <Card className="mb-4 text-[0.82rem] leading-snug text-muted-foreground">Applied as a header band on branded reports. Branding never changes any number or wording in the report body, and a report keeps the branding it had when the Visentix expert approved it.</Card>
      <div className="mt-3 grid gap-5 md:grid-cols-2">
        <div>
          <label className="mb-3 block text-[0.8rem] font-semibold text-muted-foreground">Brand color<input type="color" className="mt-1.5 block h-[34px] w-[60px] rounded-md border" value={color} onChange={e => setColor(e.target.value)} /></label>
          <label className="mb-3 block text-[0.8rem] font-semibold text-muted-foreground">Logo (PNG/JPG, max 2 MB)
            <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={e => setLogo(e.target.files?.[0] || null)} />
          </label>
          <Button disabled={busy} onClick={save}>{busy ? "Saving…" : "Save branding"}</Button>
        </div>
        <div className="overflow-hidden rounded-md border" style={{ borderTop: `6px solid ${color}` }}>
          <div className="flex items-center gap-3 p-3">
            {logo ? <img src={URL.createObjectURL(logo)} alt="" style={{ maxHeight: 40 }} /> : <span style={{ color, fontWeight: 700 }}>Your logo</span>}
            <span className="ml-auto text-[0.72rem] text-muted-foreground">Delivered via Visentix</span>
          </div>
          <div className="border-t px-3 py-3 text-[0.82rem] text-muted-foreground">Report body — the same numbers as our product. Branding only adds this header.</div>
        </div>
      </div>
    </Card>
  );
}
