/**
 * NewAssessment — submit a company's privacy notice URL for analysis.
 * Calls POST /assessments → redirects to report when ready.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function NewAssessment() {
  const { session } = useAuth();
  const navigate = useNavigate();

  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [orgName, setOrgName] = useState("");
  const [mode, setMode] = useState<"url" | "text">("url");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    setStatus("Submitting notice...");

    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
      const token = session?.access_token;
      if (!token) throw new Error("Not authenticated");

      const formData = new FormData();
      if (mode === "url") {
        formData.append("url", url);
      } else {
        formData.append("text", text);
      }
      if (orgName) formData.append("organization_name", orgName);

      setStatus("Fetching and analyzing notice...");

      const r = await fetch(`${apiBase}/assessments/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!r.ok) {
        const body = await r.text();
        throw new Error(`Failed (${r.status}): ${body.slice(0, 200)}`);
      }

      const data = await r.json();
      const assessmentId = data.assessment_id;

      setStatus(`Done! ${data.sections} sections, ${data.clauses} clauses classified. Redirecting to report...`);

      // Navigate to the report
      setTimeout(() => navigate(`/reports/${assessmentId}`), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setLoading(false);
      setStatus("");
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>New Privacy Assessment</h1>
        <p>Submit a company's privacy notice to analyze and benchmark</p>
      </div>

      <div className="card" style={{ padding: 32, maxWidth: 700 }}>
        {/* Mode selector */}
        <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
          <button
            className={`btn ${mode === "url" ? "btn-primary" : "btn-outline"} btn-sm`}
            onClick={() => setMode("url")} type="button"
          >Paste URL</button>
          <button
            className={`btn ${mode === "text" ? "btn-primary" : "btn-outline"} btn-sm`}
            onClick={() => setMode("text")} type="button"
          >Paste Text</button>
        </div>

        {error && <div className="login-error" style={{ marginBottom: 16 }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)", fontSize: "0.85rem" }}>
              Company / Organization Name
            </label>
            <input
              type="text" value={orgName} onChange={(e) => setOrgName(e.target.value)}
              placeholder="e.g. Stripe, PayPal, Acme Corp"
              style={{ width: "100%", padding: "10px 14px", border: "1.5px solid var(--border)", borderRadius: "var(--radius)" }}
            />
          </div>

          {mode === "url" ? (
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                Privacy Notice URL
              </label>
              <input
                type="url" value={url} onChange={(e) => setUrl(e.target.value)}
                placeholder="https://company.com/privacy"
                required
                style={{ width: "100%", padding: "10px 14px", border: "1.5px solid var(--border)", borderRadius: "var(--radius)" }}
              />
            </div>
          ) : (
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                Privacy Notice Text
              </label>
              <textarea
                value={text} onChange={(e) => setText(e.target.value)}
                placeholder="Paste the full privacy notice text here..."
                required rows={10}
                style={{ width: "100%", padding: "10px 14px", border: "1.5px solid var(--border)", borderRadius: "var(--radius)", resize: "vertical" }}
              />
            </div>
          )}

          <button className="btn btn-accent" type="submit" disabled={loading}
            style={{ width: "100%", padding: "14px", fontSize: "1rem", fontWeight: 700 }}>
            {loading ? status || "Analyzing..." : "Analyze Privacy Notice"}
          </button>
        </form>

        {loading && (
          <div style={{ marginTop: 20, textAlign: "center", color: "var(--text-secondary)" }}>
            <div style={{
              width: 32, height: 32, border: "3px solid var(--border)",
              borderTopColor: "var(--accent)", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", margin: "0 auto 8px",
            }} />
            <p>{status}</p>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}
      </div>
    </div>
  );
}
