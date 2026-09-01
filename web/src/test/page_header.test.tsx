/**
 * PageHeader — content and typography.
 *
 * The header is a plain panel again: no sticky collapse, so there is no state
 * machine to guard. What is worth pinning down is the heading rule, because it
 * is the thing that drifted — every heading in the product wears the display
 * face, and a card title on the UI sans was what made the set look unplanned.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PageHeader } from "../components/PageHeader";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

function renderHeader() {
  return render(
    <PageHeader
      eyebrow="Assessments"
      title="Your Assessments"
      description="One sentence about the screen."
      actions={<button>Do the thing</button>}
    />
  );
}

describe("PageHeader", () => {
  it("renders identity, description and actions", () => {
    renderHeader();
    expect(screen.getByRole("heading", { level: 1, name: "Your Assessments" })).toBeInTheDocument();
    expect(screen.getByText("Assessments")).toBeInTheDocument();
    expect(screen.getByText("One sentence about the screen.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Do the thing" })).toBeInTheDocument();
  });

  it("the title is the page's h1 — one per screen, and it is the title", () => {
    renderHeader();
    const h1s = screen.getAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
    expect(h1s[0]).toHaveTextContent("Your Assessments");
  });

  it("every decorative layer is hidden from assistive tech", () => {
    const { container } = renderHeader();
    // The wash, the eyebrow mark and the hairline carry no meaning; each must
    // opt out rather than be read as an unlabelled element.
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThanOrEqual(3);
  });
});

describe("the serif is the report's voice, not the app's", () => {
  it("the page title is on the UI sans", () => {
    renderHeader();
    // The display serif briefly ran across the whole product. It made every
    // screen look like a document it is not, and a serif page title outweighed
    // the content it introduces.
    expect(screen.getByRole("heading", { level: 1 })).toHaveClass("font-sans");
    expect(screen.getByRole("heading", { level: 1 })).not.toHaveClass("font-display");
  });

  it("a card title is on the UI sans too", () => {
    render(<Card><CardHeader><CardTitle>Active Assessments</CardTitle></CardHeader></Card>);
    expect(screen.getByText("Active Assessments")).toHaveClass("font-sans");
    expect(screen.getByText("Active Assessments")).not.toHaveClass("font-display");
  });

  it("no application screen wears the display face", () => {
    // The report keeps it — that artifact's editorial voice is the point, and
    // AdvisorNote's Fraunces lede is DDR-002. Everything else is chrome.
    const src = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), "../components/PageHeader.tsx"), "utf-8");
    expect(src).not.toMatch(/className="[^"]*font-display/);
  });
});
