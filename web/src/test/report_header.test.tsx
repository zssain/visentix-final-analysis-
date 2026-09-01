/**
 * The bar above a report.
 *
 * Two properties carry real risk.
 *
 * 1. The breadcrumb must go to `/assessments`, not `/`. "/" is the ROLE-BASED
 *    home, so an admin following it lands on the Console and an SME on the
 *    Workbench while the crumb says Assessments — the exact bug this replaced.
 * 2. The report's own cover already carries the page's <h1>. A second one here
 *    would give the document two first-level headings.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ReportHeader } from "../pages/ReportHeader";

function renderHeader(over: Partial<React.ComponentProps<typeof ReportHeader>> = {}) {
  const props = {
    organization: "3M",
    generatedDate: "2026-06-18",
    isDraft: false,
    onDownload: vi.fn(),
    downloading: false,
    downloadError: null,
    ...over,
  };
  render(<MemoryRouter><ReportHeader {...props} /></MemoryRouter>);
  return props;
}

describe("ReportHeader", () => {
  it("names the organisation the report is about", () => {
    renderHeader({ organization: "3M" });
    expect(screen.getByText("3M")).toBeInTheDocument();
  });

  it("the breadcrumb goes to /assessments, never to the role-based home", () => {
    renderHeader();
    const crumb = screen.getByRole("navigation", { name: /breadcrumb/i });
    const link = within(crumb).getByRole("link", { name: "Assessments" });
    expect(link).toHaveAttribute("href", "/assessments");
    // "/" sends an admin to the Console and an SME to the Workbench.
    expect(link).not.toHaveAttribute("href", "/");
  });

  it("marks the current crumb, so the trail says where you are", () => {
    renderHeader();
    const crumb = screen.getByRole("navigation", { name: /breadcrumb/i });
    expect(within(crumb).getByText("Report")).toHaveAttribute("aria-current", "page");
  });

  it("adds no <h1> — the report's own cover carries the page heading", () => {
    renderHeader();
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
  });

  it("states the draft standing where it cannot be scrolled past", () => {
    renderHeader({ isDraft: true });
    expect(screen.getByText(/draft — pending review/i)).toBeInTheDocument();
  });

  it("says nothing about draft state when the report is approved", () => {
    renderHeader({ isDraft: false });
    expect(screen.queryByText(/draft/i)).toBeNull();
  });

  it("downloads on click, and reports being busy rather than going silent", async () => {
    const user = userEvent.setup();
    const { onDownload } = renderHeader();
    await user.click(screen.getByRole("button", { name: /download pdf/i }));
    expect(onDownload).toHaveBeenCalledOnce();

    renderHeader({ downloading: true });
    expect(screen.getByRole("button", { name: /downloading/i })).toBeDisabled();
  });

  it("a failed download is announced, not left to the console", () => {
    renderHeader({ downloadError: "Report PDF unavailable." });
    expect(screen.getByRole("alert")).toHaveTextContent("Report PDF unavailable.");
  });

  it("shows the stored date verbatim — never reformatted into a guess", () => {
    renderHeader({ generatedDate: "2026-06-18" });
    expect(screen.getByText("2026-06-18")).toBeInTheDocument();
  });
});
