/**
 * ARCH-001A — intake filter controls (industry + state privacy laws).
 * Both are now checkbox dropdowns (MultiSelectDropdown). Mocks ../../lib/api and
 * react-router-dom so no network/router is needed. Asserts:
 *  - options load from GET /config/intake-options (real vocabulary)
 *  - blank filters show the honest-degradation note
 *  - multi-select round-trips and clears the note
 *  - submit sends comma-separated industry + jurisdictions in the FormData
 */
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { expect, it, vi, beforeEach } from "vitest";

const mockGet = vi.fn();
const mockPostForm = vi.fn();
vi.mock("../lib/api", () => ({
  api: {
    get: (...a: unknown[]) => mockGet(...a),
    postForm: (...a: unknown[]) => mockPostForm(...a),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
}));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));

import { Intake } from "../pages/customer/Intake";

const OPTIONS = {
  industries: [
    { value: "retail", label: "Retail", industry_id: "IND-01" },
    { value: "healthcare", label: "Healthcare", industry_id: "IND-04" },
  ],
  jurisdictions: [
    { value: "US-CA", label: "California (CCPA / CPRA)" },
    { value: "US-CO", label: "Colorado (CPA)" },
  ],
  unknown_industry: "unknown",
};

beforeEach(() => {
  mockGet.mockReset();
  mockPostForm.mockReset();
  mockGet.mockImplementation((path: string) => {
    if (path === "/config/intake-options") return Promise.resolve(OPTIONS);
    // status poll → complete immediately (avoids open timers)
    return Promise.resolve({ status: "complete", stage: "complete",
      assessment_id: "n1", result: { assessment_id: "n1", status: "scored" } });
  });
  mockPostForm.mockResolvedValue({ assessment_id: "job-1", status: "queued" });
});

// Open a dropdown by clicking its trigger button (found via the root test-id).
const openDropdown = (testId: string) =>
  fireEvent.click(within(screen.getByTestId(testId)).getByRole("button"));

it("loads real options and shows the honest-degradation note when blank", async () => {
  render(<Intake />);
  await waitFor(() => expect(mockGet).toHaveBeenCalledWith("/config/intake-options"));
  // industry options render from the real vocabulary (once the menu is open)
  openDropdown("intake-industry");
  expect(await screen.findByRole("option", { name: "Retail" })).toBeTruthy();
  // jurisdiction options render from the real vocabulary
  openDropdown("intake-jurisdictions");
  expect(screen.getByRole("option", { name: "California (CCPA / CPRA)" })).toBeTruthy();
  // blank → honest note
  expect(screen.getByTestId("intake-filters-note")).toBeTruthy();
});

it("multi-select round-trips and submit sends industry + jurisdictions", async () => {
  // Keep the status poll pending so no post-submit state update fires after the
  // assertion (we're only verifying the submit payload here, not the poll loop).
  mockGet.mockImplementation((path: string) =>
    path === "/config/intake-options" ? Promise.resolve(OPTIONS) : new Promise(() => {}));
  render(<Intake />);
  await waitFor(() => expect(screen.getByTestId("intake-industry")).toBeTruthy());

  // choose an industry (checkbox dropdown)
  openDropdown("intake-industry");
  fireEvent.click(screen.getByRole("option", { name: "Retail" }));
  // toggle two jurisdictions
  openDropdown("intake-jurisdictions");
  fireEvent.click(screen.getByRole("option", { name: "California (CCPA / CPRA)" }));
  fireEvent.click(screen.getByRole("option", { name: "Colorado (CPA)" }));
  // note disappears once a filter is set
  expect(screen.queryByTestId("intake-filters-note")).toBeNull();

  // enter a URL and submit
  fireEvent.change(screen.getByLabelText("Privacy Notice URL"), {
    target: { value: "https://example.com/privacy" },
  });
  fireEvent.click(screen.getByText("Analyse Notice"));

  await waitFor(() => expect(mockPostForm).toHaveBeenCalled());
  const fd = mockPostForm.mock.calls[0][1] as FormData;
  expect(fd.get("industry")).toBe("retail");
  expect(fd.get("jurisdictions")).toBe("US-CA,US-CO");
  expect(mockPostForm.mock.calls[0][0]).toBe("/assessments/async");
});
