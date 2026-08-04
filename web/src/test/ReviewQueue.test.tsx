/**
 * SME ReviewQueue (Workbench) tests — center panel is wired to REAL backend data.
 *
 * Mocks @/lib/api (the module ReviewQueue imports) so no network is hit. Asserts:
 *  - the queue loads from GET /review/queue
 *  - selecting an item loads its REAL finding (from GET /findings/, filtered by
 *    notice_id) — NOT the old hardcoded C-118 / PLACEHOLDER / 72.4 / 81% / 74th
 *  - Confirm → Record Decision POSTs to /review/finding/{aid}/{fid}
 *  - Submit Review POSTs to /review/{aid}/approve
 *  - metrics the API does not record render honest absence, not fabricated numbers
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mock the api module BEFORE importing the component ──
const mockGet = vi.fn();
const mockPost = vi.fn();
vi.mock("../lib/api", () => ({
  api: { get: (...a: unknown[]) => mockGet(...a), post: (...a: unknown[]) => mockPost(...a) },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) { super(message); this.status = status; }
  },
}));

import { ReviewQueue } from "../pages/sme/ReviewQueue";

const ASSESSMENT_ID = "notice-abc-123";

const QUEUE = [
  { assessment_id: ASSESSMENT_ID, status: "in_review", finding_reviews: {}, approved_by: "" },
];

const FINDINGS = [
  {
    finding_id: "RF-9001",
    finding_type_code: "TRK-007",
    severity: "high",
    score: 63,
    domain: "tracking",
    confidence_score: 88,
    notice_id: ASSESSMENT_ID,
  },
  // A finding from a DIFFERENT assessment — must be filtered out.
  {
    finding_id: "RF-0000",
    finding_type_code: "SH-002",
    severity: "medium",
    score: 40,
    domain: "data_sharing",
    confidence_score: 50,
    notice_id: "some-other-assessment",
  },
];

const CLAUSES = {
  assessment_id: ASSESSMENT_ID,
  flagged_domains: ["tracking"],
  clauses: [
    { clause_id: "CL-501", raw_text: "We use third-party analytics trackers across the site.", domain: "tracking" },
  ],
};

function routeGet(path: string) {
  if (path === "/review/queue") return Promise.resolve(QUEUE);
  if (path === "/findings/") return Promise.resolve(FINDINGS);
  if (path.endsWith("/clauses")) return Promise.resolve(CLAUSES);
  if (path === "/findings/codex") return Promise.resolve({ entries: [], count: 0 });
  if (path === "/admin/training-stats") return Promise.resolve({ confirmed: 1, edited: 0, dismissed: 0 });
  return Promise.resolve([]);
}

describe("SME ReviewQueue — wired to real backend", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockGet.mockImplementation((path: string) => routeGet(path));
    mockPost.mockResolvedValue({});
  });

  it("loads the queue from GET /review/queue", async () => {
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`)).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledWith("/review/queue");
  });

  it("selecting an item shows its REAL finding (not the old hardcoded placeholder)", async () => {
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`)).toBeInTheDocument());

    fireEvent.click(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`));

    await waitFor(() => expect(screen.getByTestId("finding-id")).toHaveTextContent("RF-9001"));
    // Real finding metrics from the API
    expect(screen.getByText("63")).toBeInTheDocument();
    expect(screen.getByText("88%")).toBeInTheDocument();
    // Real clause text (filtered to the finding's domain)
    expect(screen.getByText(/third-party analytics trackers/)).toBeInTheDocument();
    // findings endpoint queried
    expect(mockGet).toHaveBeenCalledWith("/findings/");
    // finding from a different assessment must NOT appear
    expect(screen.queryByText("RF-0000")).not.toBeInTheDocument();
  });

  it("renders NO fabricated literals from the old dead center panel", async () => {
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`)).toBeInTheDocument());
    fireEvent.click(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`));
    await waitFor(() => expect(screen.getByTestId("finding-id")).toHaveTextContent("RF-9001"));

    const html = document.body.innerHTML;
    for (const lit of ["C-118", "PLACEHOLDER_CLAUSE", "72.4", "81%", "74th", "Broad Sharing Language", "F-002"]) {
      expect(html).not.toContain(lit);
    }
  });

  it("Confirm → Record Decision POSTs to /review/finding/{aid}/{fid}", async () => {
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`)).toBeInTheDocument());
    fireEvent.click(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`));
    await waitFor(() => expect(screen.getByTestId("finding-id")).toHaveTextContent("RF-9001"));

    fireEvent.click(screen.getByText("✓ Confirm"));
    fireEvent.click(screen.getByText("Record Decision"));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        `/review/finding/${ASSESSMENT_ID}/RF-9001`,
        expect.objectContaining({ action: "confirm" }),
      ),
    );
  });

  it("Submit Review POSTs to /review/{aid}/approve", async () => {
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`)).toBeInTheDocument());
    fireEvent.click(screen.getByTestId(`queue-item-${ASSESSMENT_ID}`));
    await waitFor(() => expect(screen.getByTestId("finding-id")).toHaveTextContent("RF-9001"));

    fireEvent.click(screen.getByText("Submit Review"));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(`/review/${ASSESSMENT_ID}/approve`),
    );
  });

  it("shows honest empty state when the queue is empty", async () => {
    mockGet.mockImplementation((path: string) =>
      path === "/review/queue" ? Promise.resolve([]) : routeGet(path),
    );
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId("queue-empty")).toBeInTheDocument());
  });
});
