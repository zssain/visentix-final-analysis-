/**
 * Report structure — the contents map and the part headings.
 *
 * The property worth guarding is not that a contents list renders. It is that
 * the contents list can never promise a part this snapshot does not carry: a
 * reader who was forwarded the report uses it to decide whether the thing they
 * were sent it for is in here, and a link to an absent section answers that
 * question wrongly.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReportContents } from "../report/ReportContents";
import { REPORT_PARTS } from "../report/sectionGroups";

describe("report contents map", () => {
  it("lists exactly the parts it is given, in order, with their numbers", () => {
    const parts = REPORT_PARTS.filter(p => p.headed !== false);
    render(<ReportContents parts={parts} />);
    const items = within(screen.getByTestId("report-contents")).getAllByRole("link");
    expect(items).toHaveLength(parts.length);
    items.forEach((el, i) => {
      expect(el).toHaveTextContent(parts[i].title);
      expect(el).toHaveAttribute("href", `#part-${parts[i].n ?? "appendix"}`);
    });
  });

  it("renders nothing at all when no part is present — never an empty shell", () => {
    const { container } = render(<ReportContents parts={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("omits a part the payload does not carry", () => {
    const parts = REPORT_PARTS.filter(p => p.headed !== false && p.n !== 4);
    render(<ReportContents parts={parts} />);
    const nav = screen.getByTestId("report-contents");
    expect(within(nav).queryByText("What We Found")).toBeNull();
    expect(within(nav).getByText("Where You Stand")).toBeInTheDocument();
  });

  it("every part anchor is unique — two entries must never scroll to one place", () => {
    const parts = REPORT_PARTS.filter(p => p.headed !== false);
    const hrefs = parts.map(p => `#part-${p.n ?? "appendix"}`);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});
