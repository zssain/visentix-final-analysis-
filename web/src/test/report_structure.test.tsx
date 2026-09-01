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
import { ReportRail, activeIndexFor, partAnchor, railEntries } from "../report/ReportRail";
import { REPORT_PARTS, hasSubheadings, type PresentPart } from "../report/sectionGroups";

/** REPORT_PARTS as if every block in the payload were present. */
const ALL: PresentPart[] = REPORT_PARTS.map(part => ({
  part,
  blocks: part.blocks.map(n => ({ n, title: `Block ${n}` })),
}));

describe("report contents map", () => {
  it("lists exactly the parts it is given, in order, with their numbers", () => {
    const parts = ALL.filter(p => p.part.headed !== false);
    render(<ReportContents parts={parts} />);
    const items = within(screen.getByTestId("report-contents"))
      .getAllByRole("link")
      .filter(a => a.getAttribute("href")!.startsWith("#part-"));
    expect(items).toHaveLength(parts.length);
    items.forEach((el, i) => {
      expect(el).toHaveTextContent(parts[i].part.title);
      expect(el).toHaveAttribute("href", `#part-${parts[i].part.n ?? "appendix"}`);
    });
  });

  it("renders nothing at all when no part is present — never an empty shell", () => {
    const { container } = render(<ReportContents parts={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("omits a part the payload does not carry", () => {
    const parts = ALL.filter(p => p.part.headed !== false && p.part.n !== 4);
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
    render(<ReportContents parts={ALL} />);
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

  it("is present from the first frame — 'where am I' never waits on a scroll", () => {
    // It used to reveal itself only after the contents card scrolled away, so
    // the one aid for orientation was missing for exactly as long as the reader
    // was still deciding where to go.
    render(<ReportRail parts={ALL} />);
    expect(screen.getByTestId("report-rail")).not.toHaveAttribute("aria-hidden");
  });

  it("renders one entry per part, each pointing at that part's anchor", () => {
    render(<ReportRail parts={ALL} />);
    const links = within(screen.getByTestId("report-rail"))
      .getAllByRole("link")
      .filter(a => a.getAttribute("href")!.startsWith("#part-"));
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

describe("sub-sections in the contents", () => {
  it("lists a part's blocks only where the document prints their headings", () => {
    render(<ReportContents parts={ALL} />);
    const nav = screen.getByTestId("report-contents");
    const subs = within(nav).getAllByRole("link")
      .filter(a => a.getAttribute("href")!.startsWith("#section-"));

    // Sub-entries exist only under parts holding more than one block. A part
    // with one block hides that block's heading — the part heading already
    // named it — so a sub-entry there would point at nothing visible.
    const expected = ALL.filter(hasSubheadings).flatMap(p => p.blocks);
    expect(subs).toHaveLength(expected.length);
    expect(subs.length).toBeGreaterThan(0);
    subs.forEach((el, i) => {
      expect(el).toHaveAttribute("href", `#section-${expected[i].n}`);
    });
  });

  it("a one-block part gets no sub-entries", () => {
    // "What We Found" is section 6 alone.
    const single = ALL.find(p => p.part.n === 4)!;
    expect(single.blocks).toHaveLength(1);
    expect(hasSubheadings(single)).toBe(false);
  });

  it("the cover gets none either — it prints no part heading at all", () => {
    const cover = ALL.find(p => p.part.headed === false)!;
    expect(hasSubheadings(cover)).toBe(false);
  });

  it("the rail tracks sub-sections as their own rows", () => {
    const rows = railEntries(ALL);
    const subs = rows.filter(r => r.sub);
    expect(subs.length).toBe(ALL.filter(hasSubheadings).flatMap(p => p.blocks).length);
    // Each sub-row sits after its part, never before it.
    for (const p of ALL.filter(hasSubheadings)) {
      const partIdx = rows.findIndex(r => r.anchor === `part-${p.part.n ?? "appendix"}`);
      for (const b of p.blocks) {
        expect(rows.findIndex(r => r.anchor === `section-${b.n}`)).toBeGreaterThan(partIdx);
      }
    }
  });

  it("every rail anchor is unique — no two rows scroll to one place", () => {
    const anchors = railEntries(ALL).map(r => r.anchor);
    expect(new Set(anchors).size).toBe(anchors.length);
  });
});
