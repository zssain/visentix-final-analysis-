/**
 * SME Workbench tests — the review gate must not be able to fail open.
 *
 * These cover the four defects the rewrite fixed, so none of them can return:
 *  1. findings loaded per-assessment, never a platform-wide top-200 list
 *  2. the clause shown is the finding's real citation, or explicit absence
 *  3. de-identification goes to the server; no local "redacted" claim
 *  4. Approve is refused while any finding is undecided
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

const AID = "notice-abc-123";
const QUEUE = [{
  assessment_id: AID, status: "in_review", finding_reviews: {},
  organization_name: "Acme Retail", organization_domain: "acme.example",
  industry: "retail", source_label: "https://acme.example/legal/privacy-policy",
  captured_at: "2026-06-18", total_findings: 2, decided_findings: 0,
}];

/** Two findings: one cited, one with no linked clause. Neither is decided. */
const FINDINGS = {
  assessment_id: AID,
  status: "in_review",
  findings: [
    {
      finding_id: "RF-9001", finding_type_code: "TRK-007", severity: "high",
      score: 63, domain: "tracking_cookies", confidence_score: 0.88,
      benchmark_deviation_score: 12,
      evidence: [{ clause_id: "CL-501", text: "We use third-party analytics trackers.", domain: "tracking_cookies" }],
      decision: null,
    },
    {
      finding_id: "RF-9002", finding_type_code: "RT-003", severity: "moderate",
      score: 41, domain: "retention", confidence_score: 0.6,
      benchmark_deviation_score: null,
      evidence: [],
      decision: null,
    },
  ],
  reviewed_count: 0, total_count: 2, all_reviewed: false,
};

function routeGet(path: string) {
  if (path === "/review/queue") return Promise.resolve(QUEUE);
  if (path === `/review/${AID}/findings`) return Promise.resolve(FINDINGS);
  if (path === "/admin/training-stats") return Promise.resolve({ confirmed: 1, edited: 0, dismissed: 0 });
  if (path === "/review/exemplars") return Promise.resolve([]);
  return Promise.resolve([]);
}

async function openAssessment() {
  render(<ReviewQueue />);
  await waitFor(() => expect(screen.getByTestId(`queue-item-${AID}`)).toBeInTheDocument());
  fireEvent.click(screen.getByTestId(`queue-item-${AID}`));
  await waitFor(() => expect(screen.getByTestId("finding-severity")).toBeInTheDocument());
}

describe("SME Workbench — the gate cannot fail open", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockGet.mockImplementation((path: string) => routeGet(path));
    mockPost.mockResolvedValue({});
  });

  it("loads the queue from GET /review/queue", async () => {
    render(<ReviewQueue />);
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith("/review/queue"));
    expect(await screen.findByTestId(`queue-item-${AID}`)).toBeInTheDocument();
  });

  it("loads findings PER ASSESSMENT — never the platform-wide /findings/ list", async () => {
    await openAssessment();
    expect(mockGet).toHaveBeenCalledWith(`/review/${AID}/findings`);
    // The old code fetched every org's top-200 findings and filtered client-side,
    // which silently hid findings outside that global cut.
    expect(mockGet).not.toHaveBeenCalledWith("/findings/");
  });

  it("shows the finding's REAL cited clause, by id", async () => {
    await openAssessment();
    const cited = await screen.findByTestId("cited-clause");
    expect(cited).toHaveTextContent("third-party analytics trackers");
    expect(cited).toHaveTextContent("CL-501");
  });

  it("states absence when a finding has no linked clause — never a substitute", async () => {
    await openAssessment();
    fireEvent.click(screen.getByText("Next →"));
    expect(await screen.findByTestId("no-evidence")).toBeInTheDocument();
    expect(screen.queryByTestId("cited-clause")).toBeNull();
  });

  it("blocks Approve while findings are undecided, and says why", async () => {
    await openAssessment();
    expect(screen.getByTestId("approve-btn")).toBeDisabled();
    expect(screen.getByTestId("approve-blocked")).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalledWith(`/review/${AID}/approve`);
  });

  it("enables Approve only when the SERVER reports every finding decided", async () => {
    mockGet.mockImplementation((path: string) =>
      path === `/review/${AID}/findings`
        ? Promise.resolve({ ...FINDINGS, reviewed_count: 2, all_reviewed: true,
            findings: FINDINGS.findings.map(f => ({ ...f, decision: "confirm" })) })
        : routeGet(path));
    await openAssessment();
    expect(screen.getByTestId("approve-btn")).toBeEnabled();
    expect(screen.queryByTestId("approve-blocked")).toBeNull();
  });

  it("a decision POSTs to /review/finding/{aid}/{fid} and re-reads server state", async () => {
    await openAssessment();
    fireEvent.click(screen.getByText("Confirm"));
    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      `/review/finding/${AID}/RF-9001`, expect.objectContaining({ action: "confirm" })));
    // Progress is never inferred client-side — it is re-read from the server.
    await waitFor(() => expect(
      mockGet.mock.calls.filter(c => c[0] === `/review/${AID}/findings`).length,
    ).toBeGreaterThan(1));
  });

  it("surfaces a server refusal instead of reporting success", async () => {
    mockPost.mockRejectedValueOnce(Object.assign(new Error("2 finding(s) still need a decision"), { status: 409 }));
    mockGet.mockImplementation((path: string) =>
      path === `/review/${AID}/findings`
        ? Promise.resolve({ ...FINDINGS, reviewed_count: 2, all_reviewed: true })
        : routeGet(path));
    await openAssessment();
    fireEvent.click(screen.getByTestId("approve-btn"));
    const banner = await screen.findByTestId("workbench-banner");
    expect(banner).toHaveTextContent(/Not approved/i);
  });

  it("has no local-only redaction claim anywhere", async () => {
    await openAssessment();
    // The old UI announced "✓ All PII replaced with [REDACTED]" while calling no
    // endpoint at all. Nothing may claim data was cleaned from the client.
    expect(screen.queryByText(/All PII replaced/i)).toBeNull();
    expect(screen.queryByText(/Replace all with/i)).toBeNull();
  });

  it("de-identification drives the real server endpoints", async () => {
    const EX = [{ id: "ex-1", domain: "retention", clause_text: "Contact jane@acme.com", sme_cleaned: false }];
    mockGet.mockImplementation((path: string) =>
      path === "/review/exemplars" ? Promise.resolve(EX) : routeGet(path));
    render(<ReviewQueue />);
    fireEvent.click(screen.getByText("Exemplar de-identification"));
    fireEvent.click(await screen.findByTestId("exemplar-ex-1"));
    fireEvent.click(await screen.findByTestId("exemplar-clean"));
    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/review/exemplar/ex-1/clean", expect.objectContaining({ cleaned_text: expect.any(String) })));
  });

  it("names the ORGANIZATION in the queue, not a bare UUID", async () => {
    render(<ReviewQueue />);
    const row = await screen.findByTestId(`queue-item-${AID}`);
    expect(row).toHaveTextContent("Acme Retail");
    expect(row).toHaveTextContent("0/2 findings decided");
    // The id stays reachable (title attribute) but must not be the label.
    expect(row).toHaveAttribute("title", expect.stringContaining(AID));
    expect(row.textContent).not.toContain(AID);
  });

  it("states honest absence when a queue row has no organization recorded", async () => {
    mockGet.mockImplementation((path: string) =>
      path === "/review/queue"
        ? Promise.resolve([{ assessment_id: AID, status: "draft", finding_reviews: {} }])
        : routeGet(path));
    render(<ReviewQueue />);
    const row = await screen.findByTestId(`queue-item-${AID}`);
    expect(row).toHaveTextContent(/Organization not recorded/i);
    expect(row).toHaveTextContent(/No findings recorded/i);
  });

  it("shows honest empty state when the queue is empty", async () => {
    mockGet.mockImplementation((path: string) =>
      path === "/review/queue" ? Promise.resolve([]) : routeGet(path));
    render(<ReviewQueue />);
    expect(await screen.findByTestId("queue-empty")).toBeInTheDocument();
  });
});
