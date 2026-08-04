/**
 * ReportPage "Download PDF" tests (FE-001).
 *
 * The PDF endpoint is role-gated, so the download must carry the JWT. A bare
 * <a href> can't — the button must go through api.getBlob (which sends the auth
 * header). These tests assert:
 *   - clicking Download calls api.getBlob with the "/reports/{id}/pdf" path
 *   - a rejected getBlob (401/500) surfaces an honest error state, not a crash
 *
 * Mocks ../lib/api (getBlob) and the ReportView component (unit-focused on the
 * download control). jsdom lacks URL.createObjectURL / revokeObjectURL, so we
 * stub them below.
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mock the api module BEFORE importing the component ──
const mockGet = vi.fn();
const mockGetBlob = vi.fn();
vi.mock("../lib/api", () => ({
  api: {
    get: (...a: unknown[]) => mockGet(...a),
    getBlob: (...a: unknown[]) => mockGetBlob(...a),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
}));

// ReportView is heavy and irrelevant to the download control — stub it.
vi.mock("../report/ReportView", () => ({
  ReportView: () => <div data-testid="report-view-stub" />,
}));

import { ReportPage } from "../pages/ReportPage";
import { ApiError } from "../lib/api";

const ASSESSMENT_ID = "rp-download-001";
const PDF_PATH = `/reports/${ASSESSMENT_ID}/pdf`;

// jsdom has no object-URL support — stub it so createObjectURL/revokeObjectURL
// don't throw.
beforeEach(() => {
  mockGet.mockReset();
  mockGetBlob.mockReset();
  // GET /reports/{id} loads the report payload so the page renders the button.
  mockGet.mockResolvedValue({ assessment_id: ASSESSMENT_ID, sections: [] });
  URL.createObjectURL = vi.fn(() => "blob:stub-url");
  URL.revokeObjectURL = vi.fn();
});

// ReportPage reads assessmentId from useParams; drive that through a Route.
import { Routes, Route } from "react-router-dom";
function renderRouted() {
  return render(
    <MemoryRouter initialEntries={[`/reports/${ASSESSMENT_ID}`]}>
      <Routes>
        <Route path="/reports/:assessmentId" element={<ReportPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ReportPage — authenticated PDF download (FE-001)", () => {
  it("clicking Download calls api.getBlob with the JWT-carrying /reports/{id}/pdf path", async () => {
    mockGetBlob.mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    renderRouted();

    const btn = await screen.findByRole("button", { name: /download pdf/i });
    fireEvent.click(btn);

    await waitFor(() => expect(mockGetBlob).toHaveBeenCalledWith(PDF_PATH));
    // Blob was turned into an object URL for the programmatic download.
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("surfaces an error state (does not crash) when getBlob rejects with 401", async () => {
    mockGetBlob.mockRejectedValue(new ApiError(401, "Session expired"));
    renderRouted();

    const btn = await screen.findByRole("button", { name: /download pdf/i });
    fireEvent.click(btn);

    // An honest error is shown — not a silent no-op.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/could not download|permission/i);
    // The button recovers (re-enabled), the component did not crash.
    expect(screen.getByRole("button", { name: /download pdf/i })).not.toBeDisabled();
  });

  it("surfaces an error state when getBlob rejects with 500", async () => {
    mockGetBlob.mockRejectedValue(new ApiError(500, "boom"));
    renderRouted();

    const btn = await screen.findByRole("button", { name: /download pdf/i });
    fireEvent.click(btn);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/could not download/i);
  });

  it("shows a 403 permission message when getBlob rejects with 403", async () => {
    mockGetBlob.mockRejectedValue(new ApiError(403, "Forbidden"));
    renderRouted();

    const btn = await screen.findByRole("button", { name: /download pdf/i });
    fireEvent.click(btn);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/permission/i);
  });
});
