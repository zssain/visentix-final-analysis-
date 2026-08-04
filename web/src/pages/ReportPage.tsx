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
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // The PDF endpoint is role-gated, so a bare <a href> (which can't carry the
  // Authorization header) 401s. Fetch the PDF as an authenticated blob via
  // api.getBlob (sends the JWT), then trigger a programmatic download — same
  // idiom as QuarterlyReport / PartnerPortal. Loading + honest error surfacing.
  const downloadPdf = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const blob = await api.getBlob(`/reports/${assessmentId}/pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${assessmentId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof ApiError) {
        setDownloadError(
          err.status === 403
            ? "You do not have permission to download this report."
            : err.status === 404
              ? "Report PDF not found."
              : "Could not download the report. Please try again.",
        );
      } else {
        setDownloadError("Could not download the report. Please try again.");
      }
    } finally {
      setDownloading(false);
    }
  };

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
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={downloadPdf}
          disabled={downloading}
        >
          {downloading ? "Downloading…" : "Download PDF"}
        </button>
        {downloadError && (
          <span role="alert" style={{ color: "var(--red)", fontSize: "0.85rem" }}>
            {downloadError}
          </span>
        )}
      </div>

      <ReportView report={report} />
    </div>
  );
}
