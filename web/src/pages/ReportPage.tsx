/**
 * ReportPage — fetches GET /reports/{assessmentId} and renders <ReportView>.
 * Displays stored payload ONLY — never recomputes scores in the browser.
 * Shows DRAFT banner when payload carries it (gate_mode/status).
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { ReportView } from "../report/ReportView";
import type { ReportPayload } from "../report/types";

export function ReportPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  if (!assessmentId) return null;
  // key remount resets loading/error per assessment — no sync setState in the
  // fetch effect needed (audit 2026-07-16, same pattern as VendorDueDiligence).
  return <ReportLoader key={assessmentId} assessmentId={assessmentId} />;
}

function ReportLoader({ assessmentId }: { assessmentId: string }) {
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  useEffect(() => {
    api.get(`/reports/${assessmentId}`)
      .then((data) => {
        setReport(data as ReportPayload);
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          if (err.status === 403) {
            setError({ status: 403, message: "You do not have permission to view this report." });
          } else if (err.status === 404) {
            setError({ status: 404, message: "Report not found." });
          } else {
            setError({ status: err.status, message: "Failed to load report." });
          }
        } else {
          setError({ status: 500, message: "An unexpected error occurred." });
        }
      })
      .finally(() => setLoading(false));
  }, [assessmentId]);

  // Loading state
  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>
          <div style={{
            width: 40, height: 40, border: "3px solid var(--border)",
            borderTopColor: "var(--exec-blue)", borderRadius: "50%",
            animation: "spin 0.8s linear infinite", margin: "0 auto 12px",
          }} />
          <p>Loading report…</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div style={{ textAlign: "center", padding: "60px 24px" }}>
        <h2 style={{ color: error.status === 403 ? "var(--red)" : "var(--text-secondary)" }}>
          {error.status === 403 ? "403 — Not Permitted" : error.status === 404 ? "404 — Not Found" : "Error"}
        </h2>
        <p style={{ color: "var(--text-muted)", marginTop: 8 }}>{error.message}</p>
        <Link to="/" className="btn btn-primary" style={{ marginTop: 24, display: "inline-flex" }}>
          Back to Assessments
        </Link>
      </div>
    );
  }

  // No data
  if (!report) {
    return (
      <div style={{ textAlign: "center", padding: "60px 24px" }}>
        <p style={{ color: "var(--text-muted)" }}>No report data available.</p>
        <Link to="/" className="btn btn-outline" style={{ marginTop: 16, display: "inline-flex" }}>
          Back to Assessments
        </Link>
      </div>
    );
  }

  // Render the report — same ReportView used by Playwright PDF renderer
  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 16 }}>
        <Link to="/" style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
          ← Back to Assessments
        </Link>
        <a
          href={`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/reports/${assessmentId}/pdf`}
          className="btn btn-outline btn-sm"
          target="_blank"
          rel="noopener noreferrer"
        >
          Download PDF
        </a>
      </div>

      <ReportView report={report} />
    </div>
  );
}
