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

describe("heading typeface is one rule across the product", () => {
  it("the page title wears the display face", () => {
    renderHeader();
    expect(screen.getByRole("heading", { level: 1 })).toHaveClass("font-display");
  });

  it("a card title wears the same face — it was the one heading on the UI sans", () => {
    render(<Card><CardHeader><CardTitle>Active Assessments</CardTitle></CardHeader></Card>);
    expect(screen.getByText("Active Assessments")).toHaveClass("font-display");
  });

  it("the eyebrow is a LABEL, so it stays on the UI sans", () => {
    renderHeader();
    // Display for headings, sans for labels and body. An eyebrow in the display
    // face would make the label read as a second, smaller heading.
    expect(screen.getByText("Assessments")).toHaveClass("font-sans");
  });
});
