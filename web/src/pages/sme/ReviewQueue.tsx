import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";

interface ReviewItem {
  assessment_id: string;
  status: string;
  finding_reviews: Record<string, unknown>;
  approved_by: string;
}

export function ReviewQueue() {
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/review/queue")
      .then((data) => setQueue(Array.isArray(data) ? data : []))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) return;
        console.error("Failed to load queue:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>SME Review Queue</h1>
        <p>Assessments pending expert review and approval</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{queue.length}</div>
          <div className="stat-label">Pending Reviews</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "var(--warning)" }}>
            {queue.filter(q => q.status === "in_review").length}
          </div>
          <div className="stat-label">In Review</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "var(--accent)" }}>
            {queue.filter(q => q.status === "draft").length}
          </div>
          <div className="stat-label">New Drafts</div>
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div className="empty-state"><p>Loading queue...</p></div>
        ) : queue.length === 0 ? (
          <div className="empty-state">
            <h3>All caught up!</h3>
            <p>No assessments are pending review</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Assessment ID</th>
                <th>Status</th>
                <th>Findings Reviewed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((item) => (
                <tr key={item.assessment_id}>
                  <td style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>
                    {item.assessment_id?.slice(0, 16)}...
                  </td>
                  <td>
                    <span className={`badge ${item.status === "in_review" ? "badge-warning" : "badge-draft"}`}>
                      {item.status?.replace("_", " ")}
                    </span>
                  </td>
                  <td>{Object.keys(item.finding_reviews || {}).length} findings</td>
                  <td>
                    <button className="btn btn-accent btn-sm" style={{ marginRight: 8 }}>
                      Review
                    </button>
                    <button className="btn btn-outline btn-sm">Approve</button>
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
