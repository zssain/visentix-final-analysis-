/**
 * F07 Notifications settings card (/monitor). Email + webhook inputs + a
 * test-send button (honest success/fail toast). Org-scoped: uses the caller's
 * own organizationId. Mirrors the fetch/error conventions of the surrounding page.
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../../auth/AuthProvider";

interface Settings {
  email_to: string | null;
  webhook_url: string | null;
  min_severity: string | null;
  webhook_configured: boolean;
}

export function NotificationsCard() {
  const { profile } = useAuth();
  const orgId = profile?.organizationId ?? null;
  const [email, setEmail] = useState("");
  const [webhook, setWebhook] = useState("");
  const [saved, setSaved] = useState(false);
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const s = (await api.get(`/orgs/${orgId}/notifications`)) as Settings;
      setEmail(s.email_to ?? "");
      setWebhook(s.webhook_url ?? "");
    } catch { /* honest empty defaults */ }
  }, [orgId]);

  useEffect(() => { load(); }, [load]);

  if (!orgId) return null;

  const save = async () => {
    setBusy(true); setToast(null);
    try {
      await api.put(`/orgs/${orgId}/notifications`, {
        email_to: email || null, webhook_url: webhook || null,
      });
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setToast({ ok: false, msg: e instanceof Error ? e.message : "Save failed" });
    } finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true); setToast(null);
    try {
      const r = (await api.post(`/orgs/${orgId}/notifications/test`)) as { ok: boolean; result?: unknown };
      // Honest: delivery may be suppressed while F-013 thresholds are unset.
      const suppressed = JSON.stringify(r.result ?? "").includes("suppressed_no_threshold");
      setToast({ ok: r.ok, msg: !r.ok ? "No channel configured"
        : suppressed ? "Sent through pipeline — delivery is paused pending threshold approval"
        : "Test delivered" });
    } catch (e) {
      setToast({ ok: false, msg: e instanceof Error ? e.message : "Test failed" });
    } finally { setBusy(false); }
  };

  return (
    <div className="card" style={{ padding: 20, marginTop: 16 }} data-testid="notifications-card">
      <div className="card-title" style={{ marginBottom: 4 }}>Notifications</div>
      <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 12 }}>
        Get monitoring updates by email or webhook. Delivery starts once severity thresholds are approved.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)" }}>
          Email
          <input type="email" value={email} placeholder="alerts@yourcompany.com"
                 onChange={(e) => setEmail(e.target.value)}
                 style={{ width: "100%", marginTop: 4, border: "1.5px solid var(--border)",
                          borderRadius: "var(--radius)", padding: "8px 12px", fontSize: "0.88rem" }} />
        </label>
        <label style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)" }}>
          Webhook URL
          <input type="url" value={webhook} placeholder="https://your-endpoint.example/hook"
                 onChange={(e) => setWebhook(e.target.value)}
                 style={{ width: "100%", marginTop: 4, border: "1.5px solid var(--border)",
                          borderRadius: "var(--radius)", padding: "8px 12px", fontSize: "0.88rem" }} />
        </label>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 4 }}>
          <button className="btn btn-primary btn-sm" onClick={save} disabled={busy}>
            {saved ? "Saved ✓" : "Save"}
          </button>
          <button className="btn btn-outline btn-sm" onClick={test} disabled={busy}>Send test</button>
          {toast && (
            <span style={{ fontSize: "0.8rem", color: toast.ok ? "var(--teal)" : "var(--red)" }}>
              {toast.msg}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
