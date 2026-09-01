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
import { ReportRail, activeIndexFor, partAnchor } from "../report/ReportRail";
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

describe("the index numbers the document, not the headed subset", () => {
  it("starts at 1 — the cover is part 1 even though it prints no part heading", () => {
    render(<ReportContents parts={REPORT_PARTS} />);
    const items = within(screen.getByTestId("report-contents")).getAllByRole("link");
    // The regression: filtering to `headed !== false` dropped the cover, so the
    // index opened at "2. Executive Summary" and told the reader either that
    // part 1 was missing or that the index was wrong.
    expect(items[0]).toHaveTextContent("1");
    expect(items[0]).toHaveTextContent("Cover & Scope");
    expect(items[0]).toHaveAttribute("href", "#part-1");
  });

  it("the cover part still gets an anchor to link to", () => {
    const cover = REPORT_PARTS.find(p => p.headed === false)!;
    expect(partAnchor(cover)).toBe("part-1");
  });
});

describe("pinned rail — which part am I reading", () => {
  it("the active part is the LAST heading that passed the reading line", () => {
    // Heading tops relative to the viewport; negative means scrolled past.
    expect(activeIndexFor([-800, -400, -50, 300, 900], 140)).toBe(2);
  });

  it("a long part stays active while its heading is far above the fold", () => {
    // The nearest-heading rule would pick index 0 here (|−900| vs |1200|) and
    // flip the reader back to the previous part mid-section.
    expect(activeIndexFor([-900, 1200], 140)).toBe(0);
    expect(activeIndexFor([-900, 100], 140)).toBe(1);
  });

  it("nothing scrolled yet means the first part, never a blank rail", () => {
    expect(activeIndexFor([200, 900, 1600], 140)).toBe(0);
  });

  it("a part missing from the DOM (Infinity) never becomes active", () => {
    expect(activeIndexFor([-500, Number.POSITIVE_INFINITY, -100], 140)).toBe(2);
  });

  it("renders one entry per part, each pointing at that part's anchor", () => {
    render(<ReportRail parts={REPORT_PARTS} />);
    const links = within(screen.getByTestId("report-rail")).getAllByRole("link");
    expect(links).toHaveLength(REPORT_PARTS.length);
    links.forEach((el, i) => {
      expect(el).toHaveAttribute("href", `#${partAnchor(REPORT_PARTS[i])}`);
    });
  });

  it("renders nothing when there are no parts", () => {
    const { container } = render(<ReportRail parts={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
