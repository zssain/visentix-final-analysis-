/**
 * The findings table's expanded detail.
 *
 * Expanding a row used to open with a provenance ribbon, then the finding code,
 * the domain and the title again, then the exposure score and the confidence
 * again — four things the row the reader just clicked already showed — and put
 * the triggering clause LAST. The clause is the answer to "why did this fire",
 * which is the only reason to expand a row at all.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ExplainProvider } from "../report/explain/ExplainContext";
import { FindingsTable } from "../report/sections/FindingsTable";

const CONTENT = {
  findings: [
    {
      id: "AI-004", finding_code: "AI-004", domain: "ai_automated_decisions",
      severity: "high", score: 85, percentile: 91, confidence: "64%",
      advisor_lede: "The notice does not say how automated decisions are made.",
      advisor_body: "Peers in this cohort describe the logic and the opt-out.",
      evidence: [{ clause_id: "C-118", section_reference: "§7.2", excerpt: "We may use automated tools." }],
      lineage_refs: ["F-002"],
    },
  ],
  snapshot_id: "snap-1", date: "2026-06-18", cohort_size: 23, cohort_date: "2026-06-01",
};

function renderTable() {
  return render(<ExplainProvider><FindingsTable content={CONTENT} /></ExplainProvider>);
}

/** Render, then open the one finding. (The helper used to click without
 *  rendering, which fails as "no accessible roles" rather than as a missing
 *  render — worth the two lines to make the failure honest.) */
const expand = async () => {
  renderTable();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /expand finding AI-004/i }));
  return user;
};

describe("findings detail", () => {
  it("the row is the summary: code, domain, severity, score, confidence", () => {
    renderTable();
    expect(screen.getByText("AI & Automated Decisions")).toBeInTheDocument();
    expect(screen.getByText("85.0")).toBeInTheDocument();
    expect(screen.getByText("64%")).toBeInTheDocument();
  });

  it("leads the expansion with the clause that raised the finding", async () => {
    await expand();
    const panel = screen.getByText(/why this was raised/i).closest("td")!;
    expect(within(panel).getByText("§7.2")).toBeInTheDocument();
    expect(within(panel).getByText(/We may use automated tools\./)).toBeInTheDocument();

    // The clause must come before THE NOTE — comparing it against the heading
    // directly above it proves nothing, since moving the whole block keeps
    // their relative order. The note is the thing it has to precede.
    const evidence = within(panel).getByText(/why this was raised/i);
    const note = within(panel).getByText(/^the note$/i);
    expect(evidence.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("does not restate the score or the confidence the row already shows", async () => {
    await expand();
    // "85.0" is the row's Score cell; it must appear once, not twice.
    expect(screen.getAllByText("85.0")).toHaveLength(1);
    expect(screen.getAllByText("64%")).toHaveLength(1);
  });

  it("keeps the percentile — the one analyst figure the table has no column for", async () => {
    await expand();
    expect(screen.getByText(/91/)).toBeInTheDocument();
  });

  it("the disclosure control states what it does and what it controls", () => {
    renderTable();
    const btn = screen.getByRole("button", { name: /expand finding AI-004/i });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(btn).toHaveAttribute("aria-controls", "finding-detail-AI-004");
  });

  it("the control reports its new state after opening", async () => {
    await expand();
    expect(screen.getByRole("button", { name: /collapse finding AI-004/i }))
      .toHaveAttribute("aria-expanded", "true");
  });
});
