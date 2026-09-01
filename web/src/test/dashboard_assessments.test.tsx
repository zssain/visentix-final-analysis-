/**
 * The assessments screen: the report card, and the paginated table.
 *
 * Two properties carry real risk here.
 *
 * 1. `overall_score` is a PORTFOLIO figure. Printing it on a card headed with
 *    one company's name attributes a number to a report that never produced it.
 * 2. The table used to render `slice(0, 20)` with nothing saying so, which is
 *    the same failure as the empty-state-on-error bug: the screen quietly
 *    reported less than the truth.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ReportCard } from "../components/ReportCard";

function renderCard(props: Partial<React.ComponentProps<typeof ReportCard>> = {}) {
  return render(
    <MemoryRouter>
      <ReportCard organization="3M" reportId="notice-1" score={62.3} {...props} />
    </MemoryRouter>
  );
}

describe("ReportCard", () => {
  it("leads with the band, keeps the figure beside it (AC-11)", () => {
    renderCard();
    expect(screen.getByText("Developing")).toBeInTheDocument();
    expect(screen.getByText(/62\.3/)).toBeInTheDocument();
  });

  it("names the organisation the report was prepared for", () => {
    renderCard({ organization: "3M" });
    expect(screen.getByRole("heading", { name: "3M" })).toBeInTheDocument();
  });

  it("opens that report, not a list", () => {
    renderCard({ reportId: "notice-42" });
    expect(screen.getByRole("link")).toHaveAttribute("href", "/reports/notice-42");
  });

  it("states WHY a score is absent instead of showing a dash or a zero", () => {
    renderCard({
      score: undefined,
      scoreAbsenceReason: "Score shown alongside covers every assessed organisation, not this one alone.",
    });
    expect(screen.queryByText(/0\.0/)).toBeNull();
    expect(screen.getByText(/covers every assessed organisation/i)).toBeInTheDocument();
  });

  it("a card with no score is never coloured as if it scored well", () => {
    const { container } = renderCard({ score: undefined, scoreAbsenceReason: "No score." });
    const card = container.querySelector(".report-card") as HTMLElement;
    // Neutral, not --standing-good: "we could not score this" must not look
    // better than a poor result.
    expect(card.style.getPropertyValue("--standing")).toBe("var(--muted-foreground)");
  });

  it("the gradient is driven by the score's own band, never a decorative hue", () => {
    const { container: bad } = renderCard({ score: 20 });
    expect((bad.querySelector(".report-card") as HTMLElement).style.getPropertyValue("--standing"))
      .toBe("var(--standing-bad)");
    const { container: good } = renderCard({ score: 88 });
    expect((good.querySelector(".report-card") as HTMLElement).style.getPropertyValue("--standing"))
      .toBe("var(--standing-good)");
  });

  it("tilt starts at rest, so a card that is never hovered is never skewed", () => {
    const { container } = renderCard();
    const card = container.querySelector(".report-card") as HTMLElement;
    expect(card.style.getPropertyValue("--tilt-x")).toBe("0deg");
    expect(card.style.getPropertyValue("--tilt-y")).toBe("0deg");
  });

  it("is reachable and activatable by keyboard — the tilt is pointer-only garnish", async () => {
    const user = userEvent.setup();
    renderCard();
    await user.tab();
    expect(screen.getByRole("link")).toHaveFocus();
  });
});

// ── Pagination arithmetic ─────────────────────────────────────

import { paginate } from "../lib/paginate";

describe("paginate — clamping is the whole job", () => {
  const items = Array.from({ length: 23 }, (_, i) => i);

  it("splits into pages and reports a human 'first–last of total' range", () => {
    expect(paginate(items, 0, 10)).toMatchObject({ page: 0, pageCount: 3, first: 1, last: 10 });
    expect(paginate(items, 2, 10)).toMatchObject({ page: 2, pageCount: 3, first: 21, last: 23 });
  });

  it("clamps a page beyond the end instead of rendering an empty table", () => {
    // The bug this exists for: an empty table on this screen is
    // indistinguishable from "you have no assessments".
    const p = paginate(items, 99, 10);
    expect(p.page).toBe(2);
    expect(p.rows).toHaveLength(3);
  });

  it("clamps a negative or nonsense page to the first", () => {
    expect(paginate(items, -4, 10).page).toBe(0);
    expect(paginate(items, Number.NaN, 10).page).toBe(0);
  });

  it("an empty list is one page reporting 0–0, never 1–0", () => {
    const p = paginate([], 0, 10);
    expect(p).toMatchObject({ pageCount: 1, first: 0, last: 0 });
    expect(p.rows).toEqual([]);
  });

  it("a list that exactly fills its pages does not add an empty one", () => {
    expect(paginate(Array.from({ length: 20 }, (_, i) => i), 0, 10).pageCount).toBe(2);
  });

  it("never drops a row: every item appears on exactly one page", () => {
    const seen = new Set<number>();
    const { pageCount } = paginate(items, 0, 10);
    for (let i = 0; i < pageCount; i++) {
      for (const row of paginate(items, i, 10).rows) {
        expect(seen.has(row)).toBe(false);
        seen.add(row);
      }
    }
    expect(seen.size).toBe(items.length);
  });
});
