/**
 * ARCH-001A — intake filter controls (industry + state privacy laws).
 * Both are now checkbox dropdowns (MultiSelectDropdown). Mocks ../../lib/api and
 * react-router-dom so no network/router is needed. Asserts:
 *  - options load from GET /config/intake-options (real vocabulary)
 *  - blank filters show the honest-degradation note
 *  - multi-select round-trips and clears the note
 *  - submit sends comma-separated industry + jurisdictions in the FormData
 */
import { createElement } from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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
// Router is stubbed rather than mounted: this is a unit test of the intake form,
// and the page now renders a <Link> in its hand-off confirmation.
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  MemoryRouter: ({ children }: { children?: unknown }) => children,
  Link: ({ to, children, ...rest }: { to: string; children?: unknown }) =>
    createElement("a", { href: to, ...rest }, children as never),
}));

import { Intake } from "../pages/customer/Intake";
import { IntakeJobsProvider } from "../jobs/IntakeJobsProvider";

/** Intake now hands submitted jobs to the app-shell tracker, so it renders
 *  inside the provider, as it does in the app. */
function renderIntake() {
  return render(
    <IntakeJobsProvider>
      <Intake />
    </IntakeJobsProvider>,
  );
}

const OPTIONS = {
  industries: [
    { value: "retail", label: "Retail", industry_id: "IND-01" },
    { value: "healthcare", label: "Healthcare", industry_id: "IND-04" },
  ],
  jurisdictions: [
    { value: "US-CA", label: "California (CCPA / CPRA)" },
    { value: "US-CO", label: "Colorado (CPA)" },
  ],
  organization_sizes: [{ value: "medium", label: "Medium" }],
  public_private: [{ value: "private", label: "Private" }],
  geographies: [{ value: "us", label: "United States" }],
  state_footprint: [
    { value: "US-CA", label: "California" },
    { value: "US-CO", label: "Colorado" },
  ],
  data_categories: [{ value: "financial", label: "Financial information" }],
  business_practices: [{ value: "targeted_advertising", label: "Targeted advertising" }],
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

/* Open a dropdown. The testid now sits on the trigger button itself (Radix),
   not on a wrapper around it, and Radix opens on pointerdown — a plain click
   leaves the menu closed. */
const openDropdown = (testId: string) => {
  fireEvent.pointerDown(screen.getByTestId(testId), { button: 0, ctrlKey: false, pointerType: "mouse" });
};

it("loads real options and shows the honest-degradation note when blank", async () => {
  renderIntake();
  await waitFor(() => expect(mockGet).toHaveBeenCalledWith("/config/intake-options"));
  // industry options render from the real vocabulary (once the menu is open)
  openDropdown("intake-industry");
  expect(await screen.findByRole("menuitemcheckbox", { name: "Retail" })).toBeTruthy();
  // jurisdiction options render from the real vocabulary
  openDropdown("intake-selected-laws");
  expect(screen.getByRole("menuitemcheckbox", { name: "California (CCPA / CPRA)" })).toBeTruthy();
  // blank → honest note
  expect(screen.getByTestId("intake-filters-note")).toBeTruthy();
});

it("keeps footprint distinct from selected laws and submits the reviewed scope", async () => {
  // Keep the status poll pending so no post-submit state update fires after the
  // assertion (we're only verifying the submit payload here, not the poll loop).
  mockGet.mockImplementation((path: string) =>
    path === "/config/intake-options" ? Promise.resolve(OPTIONS) : new Promise(() => {}));
  renderIntake();
  await waitFor(() => expect(screen.getByTestId("intake-industry")).toBeTruthy());

  // choose an industry (checkbox dropdown)
  openDropdown("intake-industry");
  fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Retail" }));
  // Factual footprint and requested legal scope are separate fields.
  openDropdown("intake-footprint");
  fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "California" }));
  openDropdown("intake-selected-laws");
  fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "California (CCPA / CPRA)" }));
  fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Colorado (CPA)" }));
  // note disappears once a filter is set
  expect(screen.queryByTestId("intake-filters-note")).toBeNull();

  // enter a URL and submit
  fireEvent.change(screen.getByLabelText("Privacy Notice URL"), {
    target: { value: "https://example.com/privacy" },
  });
  fireEvent.click(screen.getByText("Review scope"));
  expect(screen.getByTestId("intake-review")).toBeTruthy();
  fireEvent.click(screen.getByText("Confirm and analyse"));

  await waitFor(() => expect(mockPostForm).toHaveBeenCalled());
  const fd = mockPostForm.mock.calls[0][1] as FormData;
  expect(fd.get("industry")).toBe("retail");
  expect(fd.get("state_footprint")).toBe("US-CA");
  expect(fd.get("selected_laws")).toBe("US-CA,US-CO");
  expect(fd.get("jurisdictions")).toBeNull();
  expect(mockPostForm.mock.calls[0][0]).toBe("/assessments/async");
});
