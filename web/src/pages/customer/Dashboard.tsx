import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";

interface Assessment {
  notice_id: string;
  organization_id: string;
  notice_type: string;
  effective_date: string;
  content_hash: string;
}

export function CustomerDashboard() {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/assessments/")
      .then((data) => {
        setAssessments(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) return;
        setError("Failed to load assessments");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>Privacy Assessments</h1>
        <p>Your organization's privacy intelligence assessments</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{assessments.length}</div>
          <div className="stat-label">Total Assessments</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "var(--success)" }}>
            {assessments.filter(a => a.notice_type === "live_assessment").length}
          </div>
          <div className="stat-label">Live Assessments</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "var(--accent)" }}>
            {assessments.filter(a => a.notice_type !== "live_assessment").length}
          </div>
          <div className="stat-label">Corpus Notices</div>
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div className="empty-state"><p>Loading assessments...</p></div>
        ) : error ? (
          <div className="empty-state"><h3>{error}</h3></div>
        ) : assessments.length === 0 ? (
          <div className="empty-state">
            <h3>No assessments yet</h3>
            <p>Submit a privacy notice to get started</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Notice ID</th>
                <th>Type</th>
                <th>Effective Date</th>
                <th>Content Hash</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => (
                <tr key={a.notice_id}>
                  <td style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>
                    {a.notice_id?.slice(0, 12)}...
                  </td>
                  <td>
                    <span className={`badge ${a.notice_type === "live_assessment" ? "badge-success" : "badge-moderate"}`}>
                      {a.notice_type?.replace("_", " ")}
                    </span>
                  </td>
                  <td>{a.effective_date || "—"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {a.content_hash?.slice(0, 16)}...
                  </td>
                  <td>
                    <button className="btn btn-outline btn-sm">View Report</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
